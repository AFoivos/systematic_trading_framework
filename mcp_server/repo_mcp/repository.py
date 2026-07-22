from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import re
import shutil
import subprocess
import threading
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from .config import ServerConfig
from .runtime import OperationBudget, get_runtime
from .scan_policy import (
    DEFAULT_SOURCE_GLOBS,
    TOP_LEVEL_EXCLUDED_ROOTS,
    RepositoryScanPolicy,
    as_posix_relative,
)
from .security import PathSecurityError, is_probably_text, normalize_repo_path, read_text_limited, resolve_repo_path, to_repo_relative


RG_OUTPUT_LIMIT_BYTES = 4_000_000
RG_STDERR_LIMIT_BYTES = 64_000
DEFAULT_RG_ROOTS = ("src", "tests", "config", "scripts", "docs")
DEFAULT_RG_EXCLUDE_GLOBS = (
    "!**/.git/**",
    "!**/node_modules/**",
    "!**/__pycache__/**",
    "!**/*pycache*/**",
    "!**/.venv/**",
    "!**/.venv*/**",
    "!**/venv/**",
    "!**/venv*/**",
    "!**/env/**",
    "!**/.pytest_cache/**",
    "!**/.mypy_cache/**",
    "!**/.ruff_cache/**",
    "!**/htmlcov/**",
    "!**/dist/**",
    "!**/build/**",
    "!**/site-packages/**",
    "!**/.ipynb_checkpoints/**",
    "!**/.env",
    "!**/.env.*",
    "!**/*.pem",
    "!**/*.key",
    "!**/*.p12",
    "!**/*.pfx",
    "!**/credentials.json",
    "!**/secrets.json",
    "!**/id_rsa",
    "!**/id_ed25519",
)


def _bounded_limit(value: int | None, default: int, maximum: int) -> int:
    return max(0, min(default if value is None else int(value), maximum))


def _fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _safe_walk(config: ServerConfig, root: Path, policy: RepositoryScanPolicy) -> Iterator[Path]:
    """Yield stable file paths while pruning excluded and escaping directories."""
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name.casefold(), reverse=True)
        except OSError:
            continue
        for item in children:
            try:
                relative = to_repo_relative(config.repo_root, item)
                if item.is_symlink():
                    resolved = item.resolve()
                    if resolved != config.repo_root and config.repo_root not in resolved.parents:
                        continue
                    if item.is_dir():
                        continue
                if item.is_dir():
                    if not policy.should_skip_directory(relative):
                        stack.append(item)
                elif item.is_file() and not policy.should_skip_file(relative, allow_included_type=policy.matches_include(relative)):
                    yield item
            except (OSError, ValueError):
                continue


def _root_policy(
    config: ServerConfig,
    root: str,
    *,
    include_globs: list[str] | None = None,
    exclude_globs: list[str] | None = None,
) -> tuple[Path, RepositoryScanPolicy, str]:
    search_root = resolve_repo_path(config.repo_root, root)
    if not search_root.is_dir():
        raise NotADirectoryError(root)
    relative = to_repo_relative(config.repo_root, search_root) if search_root != config.repo_root else "."
    parts = PurePosixPath(as_posix_relative(relative)).parts
    return search_root, RepositoryScanPolicy(
        exclude_globs=tuple(exclude_globs or ()),
        include_globs=tuple(include_globs or ()),
        allow_explicit_top_level_root=bool(parts and parts[0] in TOP_LEVEL_EXCLUDED_ROOTS),
    ), relative


def _read_text_window(path: Path, start_line: int, max_lines: int, max_bytes: int) -> tuple[bytes, int, int, bool]:
    """Read only the requested byte/line window, never materialising a whole file."""
    if max_lines <= 0 or max_bytes <= 0:
        return b"", start_line, start_line - 1, path.stat().st_size > 0
    payload = bytearray()
    line_number = 1
    last_line = start_line - 1
    end_requested_line = start_line + max_lines - 1
    truncated = False
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(8192)
            if not chunk:
                break
            offset = 0
            while offset < len(chunk):
                newline = chunk.find(b"\n", offset)
                end = len(chunk) if newline < 0 else newline + 1
                segment = chunk[offset:end]
                if line_number > end_requested_line:
                    truncated = True
                    break
                if line_number >= start_line:
                    remaining = max_bytes - len(payload)
                    if remaining <= 0:
                        truncated = True
                        break
                    payload.extend(segment[:remaining])
                    last_line = line_number
                    if len(segment) > remaining:
                        truncated = True
                        break
                if newline >= 0:
                    line_number += 1
                offset = end
            if truncated:
                break
    return bytes(payload), start_line, last_line, truncated


def _read_file_record(
    config: ServerConfig,
    requested_path: str,
    start_line: int,
    max_lines: int,
    max_bytes: int,
    *,
    block_sensitive: bool = True,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "path": as_posix_relative(requested_path),
        "content": "",
        "size_bytes": None,
        "returned_bytes": 0,
        "truncated": False,
        "start_line": start_line,
        "end_line": start_line - 1,
        # Kept for compatibility: this is the hash of returned content, never the full file.
        "sha256": None,
        "returned_content_sha256": None,
        "is_binary": False,
        "error": None,
    }
    try:
        path = resolve_repo_path(config.repo_root, requested_path)
        relative = to_repo_relative(config.repo_root, path)
        base["path"] = relative
        if block_sensitive and RepositoryScanPolicy().is_sensitive(relative):
            base["error"] = "Sensitive paths are not returned by bulk readers"
            return base
        if not path.exists():
            base["error"] = "Path does not exist"
            return base
        if not path.is_file():
            base["error"] = "Path is not a file"
            return base
        base["size_bytes"] = path.stat().st_size
        if max_bytes <= 0:
            base["truncated"] = bool(base["size_bytes"])
            return base
        if not is_probably_text(path):
            base["is_binary"] = True
            base["error"] = "Binary content is not returned"
            return base
        raw, returned_start, end_line, truncated = _read_text_window(path, start_line, max_lines, max_bytes)
        content = raw.decode("utf-8", errors="replace")
        digest = hashlib.sha256(raw).hexdigest()
        base.update(
            {
                "content": content,
                "returned_bytes": len(raw),
                "truncated": truncated,
                "start_line": returned_start,
                "end_line": end_line,
                "sha256": digest,
                "returned_content_sha256": digest,
            }
        )
    except (OSError, PathSecurityError, ValueError) as exc:
        base["error"] = f"{type(exc).__name__}: {exc}"
    return base


def list_directory(config: ServerConfig, path: str = ".", recursive: bool = False, max_entries: int | None = None) -> dict[str, Any]:
    directory = resolve_repo_path(config.repo_root, path)
    if not directory.exists():
        raise FileNotFoundError(path)
    if not directory.is_dir():
        raise NotADirectoryError(path)
    limit = _bounded_limit(max_entries, config.max_tree_entries, config.max_tree_entries)
    root_rel = to_repo_relative(config.repo_root, directory) if directory != config.repo_root else "."
    _, policy, _ = _root_policy(config, root_rel)
    entries: list[dict[str, Any]] = []
    truncated = False
    if recursive:
        stack = [directory]
        while stack and not truncated:
            current = stack.pop()
            try:
                children = sorted(current.iterdir(), key=lambda item: item.name.casefold(), reverse=True)
            except OSError:
                continue
            for item in children:
                if len(entries) >= limit:
                    truncated = True
                    break
                try:
                    rel = to_repo_relative(config.repo_root, item)
                    if item.is_symlink() and (item.is_dir() or config.repo_root not in item.resolve().parents):
                        continue
                    if item.is_dir():
                        if policy.should_skip_directory(rel):
                            continue
                        entries.append({"path": rel, "type": "directory", "size_bytes": None})
                        stack.append(item)
                    elif item.is_file() and not policy.should_skip_file(rel, allow_included_type=policy.matches_include(rel)):
                        entries.append({"path": rel, "type": "file", "size_bytes": item.stat().st_size})
                except OSError:
                    continue
    else:
        for item in sorted(directory.iterdir(), key=lambda item: item.name.casefold()):
            if len(entries) >= limit:
                truncated = True
                break
            try:
                entries.append({"path": to_repo_relative(config.repo_root, item), "type": "directory" if item.is_dir() else "file", "size_bytes": item.stat().st_size if item.is_file() else None})
            except OSError:
                continue
    return {"root": root_rel, "entries": entries, "truncated": truncated}


def read_file(config: ServerConfig, path: str, start_line: int | None = None, max_lines: int | None = None, max_bytes: int | None = None) -> dict[str, Any]:
    file_path = resolve_repo_path(config.repo_root, path)
    if not file_path.exists():
        raise FileNotFoundError(path)
    if not file_path.is_file():
        raise IsADirectoryError(path)
    byte_limit = _bounded_limit(max_bytes, config.max_read_bytes, config.max_read_bytes)
    text, byte_truncated = read_text_limited(file_path, byte_limit)
    lines = text.splitlines()
    start = max((start_line or 1) - 1, 0)
    selected = lines[start:]
    line_truncated = False
    if max_lines is not None:
        selected = selected[: max(max_lines, 0)]
        line_truncated = start + len(selected) < len(lines) or byte_truncated
    returned_text = "\n".join(selected)
    full_sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest() if not byte_truncated else None
    return {"path": to_repo_relative(config.repo_root, file_path), "size_bytes": file_path.stat().st_size, "start_line": start + 1, "line_count": len(selected), "total_lines": len(lines), "truncated": byte_truncated or line_truncated, "text": returned_text, "sha256": full_sha256, "returned_content_sha256": hashlib.sha256(returned_text.encode("utf-8")).hexdigest()}


def read_files(config: ServerConfig, paths: list[str], start_line: int | None = None, max_lines_per_file: int = 500, max_bytes_per_file: int = 100_000, total_max_bytes: int = 1_000_000) -> dict[str, Any]:
    if len(paths) > 1_000:
        raise ValueError("paths may contain at most 1000 items")
    per_file_limit = _bounded_limit(max_bytes_per_file, 100_000, config.max_read_bytes)
    total_limit = _bounded_limit(total_max_bytes, 1_000_000, max(config.max_read_bytes * 10, 1_000_000))
    line_limit = max(0, min(int(max_lines_per_file), 10_000))
    line_start = max(1, int(start_line or 1))
    remaining = total_limit
    files: list[dict[str, Any]] = []
    any_truncated = False
    for requested_path in paths:
        record = _read_file_record(config, str(requested_path), line_start, line_limit, min(per_file_limit, remaining))
        files.append(record)
        remaining -= int(record["returned_bytes"])
        any_truncated = any_truncated or bool(record["truncated"])
        if remaining <= 0 and len(files) < len(paths):
            any_truncated = True
    return {"files": files, "total_returned_bytes": total_limit - remaining, "truncated": any_truncated}


def stat_files(config: ServerConfig, paths: list[str], include_git_status: bool = False) -> dict[str, Any]:
    if len(paths) > 1_000:
        raise ValueError("paths may contain at most 1000 items")
    items: list[dict[str, Any]] = []
    valid_paths: list[str] = []
    for requested_path in paths:
        item: dict[str, Any] = {"path": as_posix_relative(str(requested_path)), "exists": False, "is_file": False, "is_directory": False, "size_bytes": None, "modified_time": None, "extension": "", "is_binary": False, "is_symlink": False, "git_status": None, "error": None}
        try:
            normalized = normalize_repo_path(str(requested_path))
            raw_path = config.repo_root / normalized
            path = resolve_repo_path(config.repo_root, normalized)
            relative = to_repo_relative(config.repo_root, path)
            item.update({"path": relative, "is_symlink": raw_path.is_symlink(), "exists": path.exists()})
            valid_paths.append(relative)
            if path.exists():
                stat = path.stat()
                item.update({"is_file": path.is_file(), "is_directory": path.is_dir(), "size_bytes": stat.st_size if path.is_file() else None, "modified_time": stat.st_mtime, "extension": path.suffix.lower(), "is_binary": path.is_file() and not is_probably_text(path)})
        except (OSError, PathSecurityError, ValueError) as exc:
            item["error"] = f"{type(exc).__name__}: {exc}"
        items.append(item)
    git_error = None
    if include_git_status and valid_paths:
        from .git_tools import git_status_map

        statuses, git_error = git_status_map(config, valid_paths)
        for item in items:
            item["git_status"] = statuses.get(item["path"])
    return {"items": items, "git_error": git_error}


def read_project_tree(config: ServerConfig, max_depth: int = 4, include_files: bool = True, max_entries: int | None = None) -> dict[str, Any]:
    limit = _bounded_limit(max_entries, config.max_tree_entries, config.max_tree_entries)
    depth_limit = max(0, min(int(max_depth), 20))
    entries: list[dict[str, Any]] = []
    stack = [(config.repo_root, 0)]
    policy = RepositoryScanPolicy()
    truncated = False
    while stack:
        directory, depth = stack.pop()
        if depth >= depth_limit:
            continue
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name.casefold(), reverse=True)
        except OSError:
            continue
        for item in children:
            if len(entries) >= limit:
                truncated = True
                break
            try:
                rel = to_repo_relative(config.repo_root, item)
                item_depth = len(PurePosixPath(rel).parts)
                if item.is_symlink() and (item.is_dir() or config.repo_root not in item.resolve().parents):
                    continue
                if item.is_dir():
                    if policy.should_skip_directory(rel):
                        continue
                    entries.append({"path": rel, "type": "directory", "depth": item_depth})
                    stack.append((item, item_depth))
                elif include_files and not policy.should_skip_file(rel, allow_included_type=policy.matches_include(rel)):
                    entries.append({"path": rel, "type": "file", "depth": item_depth})
            except OSError:
                continue
        if truncated:
            break
    return {"root": ".", "max_depth": depth_limit, "entries": entries, "truncated": truncated}


def search_files(config: ServerConfig, pattern: str, root: str = ".", max_results: int | None = None) -> dict[str, Any]:
    search_root, policy, _ = _root_policy(config, root, include_globs=[pattern])
    limit = _bounded_limit(max_results, config.max_search_results, config.max_search_results)
    results: list[dict[str, Any]] = []
    for item in _safe_walk(config, search_root, policy):
        if len(results) >= limit:
            break
        rel = to_repo_relative(config.repo_root, item)
        if fnmatch.fnmatch(item.name, pattern) or fnmatch.fnmatch(rel, pattern):
            results.append({"path": rel, "type": "file"})
    return {"pattern": pattern, "results": results, "truncated": len(results) >= limit}


def _initial_walk_state(config: ServerConfig, roots: list[str]) -> tuple[dict[str, Any], RepositoryScanPolicy]:
    root_relatives: list[str] = []
    allow_top = False
    for root in roots:
        _, policy, relative = _root_policy(config, root, include_globs=[])
        root_relatives.append(relative)
        allow_top = allow_top or policy.allow_explicit_top_level_root
    stack = [{"directory": root, "after": None} for root in reversed(root_relatives)]
    return {"stack": stack, "current_path": None, "next_line": 1}, RepositoryScanPolicy(allow_explicit_top_level_root=allow_top)


def _next_walk_file(config: ServerConfig, state: dict[str, Any], policy: RepositoryScanPolicy, include: list[str], budget: OperationBudget) -> str | None:
    stack = state["stack"]
    while stack and not budget.exhausted:
        frame = stack[-1]
        directory_rel = str(frame["directory"])
        directory = resolve_repo_path(config.repo_root, directory_rel)
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name.casefold())
        except OSError:
            stack.pop()
            continue
        after = frame.get("after")
        child = next((item for item in children if after is None or item.name.casefold() > str(after).casefold()), None)
        if child is None:
            stack.pop()
            continue
        frame["after"] = child.name
        try:
            rel = to_repo_relative(config.repo_root, child)
            if child.is_symlink():
                resolved = child.resolve()
                if resolved != config.repo_root and config.repo_root not in resolved.parents:
                    continue
                if child.is_dir():
                    continue
            if child.is_dir():
                if not policy.should_skip_directory(rel):
                    stack.append({"directory": rel, "after": None})
                continue
            include_type = policy.matches_include(rel, include)
            if child.is_file() and include_type and not policy.should_skip_file(rel, allow_included_type=include_type):
                return rel
        except (OSError, ValueError):
            continue
    return None


def _search_file(config: ServerConfig, relative: str, query: str, context: int, start_line: int, budget: OperationBudget, remaining_results: int) -> tuple[list[dict[str, Any]], int, bool]:
    try:
        # relative was produced by the safe index/walker in this request, so a
        # costly resolve() per source file is unnecessary on Windows.
        path = config.repo_root.joinpath(*PurePosixPath(relative).parts)
        if not is_probably_text(path):
            return [], 1, True
        text, _ = read_text_limited(path, min(config.max_read_bytes, 1_000_000))
    except OSError:
        return [], 1, True
    lines = text.splitlines()
    needle = query.casefold()
    items: list[dict[str, Any]] = []
    for line_number in range(max(1, start_line), len(lines) + 1):
        if budget.exhausted:
            return items, line_number, False
        line = lines[line_number - 1]
        if needle not in line.casefold():
            continue
        before = max(line_number - context - 1, 0)
        after = min(line_number + context, len(lines))
        items.append({"path": relative, "line": line_number, "match": line, "context": "\n".join(lines[before:after])})
        if len(items) >= remaining_results:
            return items, line_number + 1, False
    return items, 1, True


def _drain_limited(stream: Any, limit: int, target: bytearray, truncated: list[bool]) -> None:
    try:
        while chunk := stream.read(64 * 1024):
            remaining = max(0, limit - len(target))
            if remaining:
                target.extend(chunk[:remaining])
            if len(chunk) > remaining:
                truncated[0] = True
    finally:
        stream.close()


def _default_source_paths(runtime: Any, include: list[str], exclude: list[str]) -> list[str]:
    policy = RepositoryScanPolicy(exclude_globs=tuple(exclude), include_globs=tuple(include))
    return [path for path in runtime.source_index.paths() if policy.matches_include(path) and not policy.should_skip_file(path, allow_included_type=True)]


def _ordered_paths_fingerprint(paths: list[str]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _rg_default_source_candidates(config: ServerConfig, query: str, budget: OperationBudget, source_paths: list[str]) -> list[str] | None:
    """Return bounded, sorted matching source paths, or None for Python fallback."""
    executable = shutil.which("rg")
    if not executable or budget.remaining_ms < 50:
        return None
    roots = [root for root in DEFAULT_RG_ROOTS if (config.repo_root / root).is_dir()]
    if not roots:
        return []
    args = [executable, "--files-with-matches", "--no-ignore", "--hidden", "--fixed-strings", "--ignore-case", "--no-messages", "--path-separator", "/", "--sort", "path"]
    for glob in DEFAULT_SOURCE_GLOBS:
        args.extend(["-g", glob])
    for glob in DEFAULT_RG_EXCLUDE_GLOBS:
        args.extend(["-g", glob])
    stdout, stderr = bytearray(), bytearray()
    stdout_truncated, stderr_truncated = [False], [False]
    try:
        process = subprocess.Popen(args + ["--", query, *roots], cwd=config.repo_root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    except OSError:
        return None
    out_thread = threading.Thread(target=_drain_limited, args=(process.stdout, RG_OUTPUT_LIMIT_BYTES, stdout, stdout_truncated), daemon=True)
    err_thread = threading.Thread(target=_drain_limited, args=(process.stderr, RG_STDERR_LIMIT_BYTES, stderr, stderr_truncated), daemon=True)
    out_thread.start()
    err_thread.start()
    timed_out = False
    try:
        process.wait(timeout=max(0.05, budget.remaining_ms / 1000))
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        process.wait()
    out_thread.join(timeout=1)
    err_thread.join(timeout=1)
    if timed_out or stdout_truncated[0] or stderr_truncated[0] or process.returncode not in {0, 1}:
        return None
    if process.returncode == 1:
        return []
    allowed_paths = set(source_paths)
    candidates = {as_posix_relative(line) for line in stdout.decode("utf-8", errors="replace").splitlines()}
    return sorted((path for path in candidates if path in allowed_paths), key=str.casefold)


def search_source(
    config: ServerConfig,
    query: str,
    roots: list[str] | None = None,
    include_globs: list[str] | None = None,
    exclude_globs: list[str] | None = None,
    max_results: int = 100,
    context_lines: int = 1,
    time_budget_ms: int = 3_000,
    cursor: str | None = None,
) -> dict[str, Any]:
    if not query:
        raise ValueError("query must not be empty")
    include = list(include_globs or DEFAULT_SOURCE_GLOBS)
    exclude = list(exclude_globs or [])
    limit = max(1, min(int(max_results), config.max_search_results))
    context = max(0, min(int(context_lines), 20))
    budget = OperationBudget(max(1, min(int(time_budget_ms), 30_000)))
    normalized_roots = None if roots is None else [as_posix_relative(root or ".") or "." for root in roots]
    fingerprint = _fingerprint({"query": query, "roots": normalized_roots, "include": include, "exclude": exclude, "context": context})
    runtime = get_runtime(config.repo_root)
    state = runtime.cursors.read(cursor, "search_source", fingerprint) if cursor else None
    items: list[dict[str, Any]] = []
    scanned_files = 0

    if normalized_roots is None:
        if state and state.get("mode") == "index_build" and int(state["build_revision"]) != runtime.source_index.build_revision:
            raise ValueError("Invalid or stale continuation cursor")
        if runtime.source_index.ready:
            runtime.cache_hits += 1
        else:
            runtime.cache_misses += 1
        if not runtime.source_index.ensure_ready(budget):
            next_cursor = runtime.cursors.create("search_source", fingerprint, {"mode": "index_build", "build_revision": runtime.source_index.build_revision})
            return {"status": "partial", "items": [], "next_cursor": next_cursor, "truncated": True, "elapsed_ms": budget.elapsed_ms, "scanned_files": 0, "skipped_paths": []}
        if state and state.get("mode") == "index_build":
            state = None
        if state and (state.get("mode") not in {"index", "rg"} or int(state.get("generation", -1)) != runtime.source_index.generation):
            raise ValueError("Invalid or stale continuation cursor")
        paths = _default_source_paths(runtime, include, exclude)
        use_rg = include == list(DEFAULT_SOURCE_GLOBS) and not exclude
        candidates = _rg_default_source_candidates(config, query, budget, paths) if use_rg and (state is None or state.get("mode") == "rg") else None

        if candidates is not None:
            candidate_fingerprint = _ordered_paths_fingerprint(candidates)
            if state:
                path_index = int(state.get("path_offset", -1))
                next_line = int(state.get("next_line", 0))
                current_path = state.get("current_path")
                if (
                    state.get("mode") != "rg"
                    or state.get("candidate_fingerprint") != candidate_fingerprint
                    or path_index < 0
                    or path_index >= len(candidates)
                    or current_path != candidates[path_index]
                    or next_line < 1
                ):
                    raise ValueError("Invalid or stale continuation cursor")
            else:
                path_index = 0
                next_line = 1
            while path_index < len(candidates) and not budget.exhausted and len(items) < limit:
                rel = candidates[path_index]
                found, following_line, completed = _search_file(config, rel, query, context, next_line, budget, limit - len(items))
                items.extend(found)
                scanned_files += 1
                if completed:
                    path_index += 1
                    next_line = 1
                else:
                    next_line = following_line
                    break
            partial = path_index < len(candidates)
            next_cursor = (
                runtime.cursors.create(
                    "search_source",
                    fingerprint,
                    {
                        "mode": "rg",
                        "generation": runtime.source_index.generation,
                        "candidate_fingerprint": candidate_fingerprint,
                        "path_offset": path_index,
                        "current_path": candidates[path_index],
                        "next_line": next_line,
                    },
                )
                if partial
                else None
            )
        else:
            # A missing, timed-out, or oversized ripgrep response falls back to
            # the indexed Python scan. A prior rg cursor resumes from its current
            # source path without storing the candidate list in cursor state.
            if state and state.get("mode") == "rg":
                current_path = state.get("current_path")
                next_line = int(state.get("next_line", 0))
                if not isinstance(current_path, str) or current_path not in paths or next_line < 1:
                    raise ValueError("Invalid or stale continuation cursor")
                path_index = paths.index(current_path)
            else:
                path_index = int(state.get("path_index", 0)) if state else 0
                next_line = int(state.get("next_line", 1)) if state else 1
                if path_index < 0 or path_index > len(paths) or next_line < 1:
                    raise ValueError("Invalid or stale continuation cursor")
            while path_index < len(paths) and not budget.exhausted and len(items) < limit:
                rel = paths[path_index]
                found, following_line, completed = _search_file(config, rel, query, context, next_line, budget, limit - len(items))
                items.extend(found)
                scanned_files += 1
                if completed:
                    path_index += 1
                    next_line = 1
                else:
                    next_line = following_line
                    break
            partial = path_index < len(paths)
            next_cursor = runtime.cursors.create("search_source", fingerprint, {"mode": "index", "generation": runtime.source_index.generation, "path_index": path_index, "next_line": next_line}) if partial else None
    else:
        if state:
            if state.get("mode") != "walk":
                raise ValueError("Invalid or stale continuation cursor")
            walk_state = {"stack": list(state["stack"]), "current_path": state.get("current_path"), "next_line": int(state.get("next_line", 1))}
            policy = RepositoryScanPolicy(exclude_globs=tuple(exclude), include_globs=tuple(include), allow_explicit_top_level_root=bool(state.get("allow_top")))
        else:
            walk_state, root_policy = _initial_walk_state(config, normalized_roots)
            policy = RepositoryScanPolicy(exclude_globs=tuple(exclude), include_globs=tuple(include), allow_explicit_top_level_root=root_policy.allow_explicit_top_level_root)
        while not budget.exhausted and len(items) < limit:
            current = walk_state.get("current_path")
            if current is None:
                current = _next_walk_file(config, walk_state, policy, include, budget)
                if current is None:
                    break
                walk_state["current_path"] = current
                walk_state["next_line"] = 1
            found, following_line, completed = _search_file(config, str(current), query, context, int(walk_state["next_line"]), budget, limit - len(items))
            items.extend(found)
            scanned_files += 1
            if completed:
                walk_state["current_path"] = None
                walk_state["next_line"] = 1
            else:
                walk_state["next_line"] = following_line
                break
        partial = bool(walk_state["stack"] or walk_state.get("current_path"))
        next_cursor = runtime.cursors.create("search_source", fingerprint, {"mode": "walk", "stack": walk_state["stack"], "current_path": walk_state.get("current_path"), "next_line": walk_state["next_line"], "allow_top": policy.allow_explicit_top_level_root}) if partial else None

    return {"status": "partial" if partial else "ok", "items": items, "next_cursor": next_cursor, "truncated": partial, "elapsed_ms": budget.elapsed_ms, "scanned_files": scanned_files, "skipped_paths": []}


def search_code(
    config: ServerConfig,
    query: str,
    root: str = ".",
    file_glob: str | None = None,
    max_results: int | None = None,
    context_lines: int = 1,
    time_budget_ms: int = 3_000,
    cursor: str | None = None,
) -> dict[str, Any]:
    use_default_index = root in {"", "."}
    response = search_source(
        config,
        query=query,
        roots=None if use_default_index else [root],
        include_globs=[file_glob] if file_glob else list(DEFAULT_SOURCE_GLOBS),
        max_results=max_results or config.max_search_results,
        context_lines=context_lines,
        time_budget_ms=time_budget_ms,
        cursor=cursor,
    )
    return {"query": query, "results": response["items"], "truncated": response["truncated"], "next_cursor": response["next_cursor"], "elapsed_ms": response["elapsed_ms"]}


def _python_symbols(path: Path, repo_root: Path) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return []
    rel = to_repo_relative(repo_root, path)
    return [{"name": node.name, "kind": "class" if isinstance(node, ast.ClassDef) else "function", "path": rel, "line": node.lineno} for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]


def _text_symbols(path: Path, repo_root: Path) -> list[dict[str, Any]]:
    try:
        text, _ = read_text_limited(path, 256_000)
    except OSError:
        return []
    rel = to_repo_relative(repo_root, path)
    return [{"name": line.lstrip("#").strip(), "kind": "markdown_heading", "path": rel, "line": index} for index, line in enumerate(text.splitlines(), start=1) if line.startswith("#")]


def search_symbols(config: ServerConfig, query: str, root: str = ".", max_results: int | None = None) -> dict[str, Any]:
    search_root, policy, _ = _root_policy(config, root)
    limit = _bounded_limit(max_results, config.max_search_results, config.max_search_results)
    results: list[dict[str, Any]] = []
    for item in _safe_walk(config, search_root, policy):
        if len(results) >= limit:
            break
        symbols = _python_symbols(item, config.repo_root) if item.suffix.lower() == ".py" else _text_symbols(item, config.repo_root) if item.suffix.lower() == ".md" else []
        results.extend(symbol for symbol in symbols if query.casefold() in symbol["name"].casefold())
        results = results[:limit]
    return {"query": query, "results": results, "truncated": len(results) >= limit}


def find_references(config: ServerConfig, symbol: str, root: str = ".", max_results: int | None = None) -> dict[str, Any]:
    pattern = re.compile(rf"\b{re.escape(symbol)}\b")
    search_root, policy, _ = _root_policy(config, root)
    limit = _bounded_limit(max_results, config.max_search_results, config.max_search_results)
    results: list[dict[str, Any]] = []
    for item in _safe_walk(config, search_root, policy):
        if len(results) >= limit or not is_probably_text(item):
            continue
        try:
            text, _ = read_text_limited(item, min(config.max_read_bytes, 1_000_000))
        except OSError:
            continue
        rel = to_repo_relative(config.repo_root, item)
        for index, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                results.append({"path": rel, "line": index, "text": line})
                if len(results) >= limit:
                    break
    return {"symbol": symbol, "results": results, "truncated": len(results) >= limit}


def search_standard(config: ServerConfig, query: str) -> str:
    code_results = search_code(config, query=query, max_results=25)["results"]
    file_results = search_files(config, pattern=f"*{query}*", max_results=25)["results"]
    seen: set[str] = set()
    merged = []
    for result in file_results + code_results:
        if result["path"] not in seen:
            seen.add(result["path"])
            merged.append({"id": result["path"], "title": result["path"], "url": f"repo://{result['path']}"})
    return json.dumps({"results": merged}, ensure_ascii=False)


def fetch_standard(config: ServerConfig, item_id: str) -> str:
    payload = read_file(config, item_id)
    return json.dumps({"id": payload["path"], "title": payload["path"], "text": payload["text"], "url": f"repo://{payload['path']}", "metadata": {"size_bytes": payload["size_bytes"], "truncated": payload["truncated"], "line_count": payload["line_count"]}}, ensure_ascii=False)
