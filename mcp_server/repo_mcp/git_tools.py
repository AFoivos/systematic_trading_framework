from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import ServerConfig
from .repository import _read_file_record
from .runtime import OperationBudget, get_runtime
from .scan_policy import RepositoryScanPolicy, TOP_LEVEL_EXCLUDED_ROOTS, classify_source_path
from .security import PathSecurityError, is_probably_text, resolve_repo_path, to_repo_relative


GIT_STATUS_TIMEOUT_SECONDS = 12
GIT_DIFF_TIMEOUT_SECONDS = 20
GIT_OUTPUT_LIMIT_BYTES = 4_000_000
GIT_DIFF_REPLAY_LIMIT_BYTES = 8_000_000


@dataclass
class GitCommandResult:
    stdout: bytes
    stderr: bytes
    returncode: int | None
    timed_out: bool
    stdout_truncated: bool
    stderr_truncated: bool
    elapsed_ms: int
    error: str | None = None


@dataclass
class GitState:
    git_available: bool
    worktree_valid: bool | None
    records: list[dict[str, Any]]
    fingerprint: str | None
    error: str | None
    stderr: str
    elapsed_ms: int

    @property
    def ok(self) -> bool:
        return self.git_available and self.worktree_valid is True and self.error is None


def _drain(stream: Any, limit: int, target: bytearray, truncated: list[bool]) -> None:
    try:
        while chunk := stream.read(64 * 1024):
            available = max(0, limit - len(target))
            if available:
                target.extend(chunk[:available])
            if len(chunk) > available:
                truncated[0] = True
    finally:
        stream.close()


def _run_git(config: ServerConfig, args: list[str], *, timeout_seconds: int, max_output_bytes: int) -> GitCommandResult:
    """Run Git without a shell and safely drain both subprocess pipes."""
    started = time.perf_counter()
    try:
        proc = subprocess.Popen(["git", *args], cwd=config.repo_root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    except OSError as exc:
        return GitCommandResult(b"", b"", None, False, False, False, int((time.perf_counter() - started) * 1000), str(exc))
    stdout, stderr = bytearray(), bytearray()
    stdout_truncated, stderr_truncated = [False], [False]
    out_thread = threading.Thread(target=_drain, args=(proc.stdout, max_output_bytes, stdout, stdout_truncated), daemon=True)
    err_thread = threading.Thread(target=_drain, args=(proc.stderr, 64 * 1024, stderr, stderr_truncated), daemon=True)
    out_thread.start()
    err_thread.start()
    timed_out = False
    try:
        proc.wait(timeout=max(1, timeout_seconds))
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        proc.wait()
    out_thread.join(timeout=1)
    err_thread.join(timeout=1)
    return GitCommandResult(bytes(stdout), bytes(stderr), proc.returncode, timed_out, stdout_truncated[0], stderr_truncated[0], int((time.perf_counter() - started) * 1000))


def _git(config: ServerConfig, args: list[str], timeout_seconds: int = 30, max_output_bytes: int = GIT_OUTPUT_LIMIT_BYTES) -> str:
    result = _run_git(config, args, timeout_seconds=timeout_seconds, max_output_bytes=max_output_bytes)
    if result.error:
        raise RuntimeError(f"Git unavailable: {result.error}")
    if result.timed_out:
        raise TimeoutError(f"git {' '.join(args[:2])} timed out after {timeout_seconds} seconds")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip() or f"git {' '.join(args)} failed")
    return result.stdout.decode("utf-8", errors="replace")


def _bounded_error(result: GitCommandResult, fallback: str) -> str:
    if result.error:
        return result.error[:4096]
    if result.timed_out:
        return f"{fallback} timed out"
    return result.stderr.decode("utf-8", errors="replace").strip()[:4096] or fallback


def _probe_worktree(config: ServerConfig) -> tuple[bool, bool | None, str | None, str, int]:
    result = _run_git(config, ["rev-parse", "--is-inside-work-tree"], timeout_seconds=5, max_output_bytes=1024)
    stderr = result.stderr.decode("utf-8", errors="replace")[:4096]
    if result.error:
        return False, None, _bounded_error(result, "Git executable is unavailable"), stderr, result.elapsed_ms
    if result.timed_out:
        return True, None, _bounded_error(result, "Git worktree probe"), stderr, result.elapsed_ms
    if result.returncode == 0 and result.stdout.decode("utf-8", errors="replace").strip() == "true":
        return True, True, None, stderr, result.elapsed_ms
    return True, False, _bounded_error(result, "Configured repository root is not a Git worktree"), stderr, result.elapsed_ms


def _parse_status(stdout: bytes, include_ignored: bool) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    chunks = stdout.split(b"\0")
    index = 0
    while index < len(chunks):
        entry = chunks[index]
        index += 1
        if not entry or len(entry) < 3:
            continue
        prefix = entry[:3].decode("ascii", errors="replace")
        code = prefix[:2]
        path = entry[3:].decode("utf-8", errors="replace").replace("\\", "/")
        if code == "!!":
            if include_ignored:
                records.append({"path": path, "code": code, "kind": "ignored", "from_path": None})
            continue
        old_path = None
        if "R" in code or "C" in code:
            if index < len(chunks):
                old_path = chunks[index].decode("utf-8", errors="replace").replace("\\", "/")
                index += 1
        if code == "??":
            kind = "untracked"
        elif "U" in code:
            kind = "conflicted"
        elif "D" in code:
            kind = "deleted"
        elif "R" in code:
            kind = "renamed"
        elif "C" in code:
            kind = "copied"
        elif "A" in code:
            kind = "added"
        else:
            kind = "modified"
        records.append({"path": path, "code": code, "kind": kind, "from_path": old_path})
    return records


def _review_pathspecs() -> list[str]:
    top = [f":(exclude){name}/**" for name in TOP_LEVEL_EXCLUDED_ROOTS]
    global_excludes = [
        ":(exclude)**/.git/**",
        ":(exclude)**/node_modules/**",
        ":(exclude)**/__pycache__/**",
        ":(exclude)**/*pycache*/**",
        ":(exclude)**/.pytest_cache/**",
        ":(exclude)**/.mypy_cache/**",
        ":(exclude)**/.ruff_cache/**",
        ":(exclude)**/.venv*/**",
        ":(exclude)**/venv*/**",
        ":(exclude)**/env/**",
    ]
    return [".", *top, *global_excludes]


def _state_fingerprint(config: ServerConfig, status_payload: bytes, records: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256(status_payload)
    for record in sorted(records, key=lambda item: (item["path"], item["code"], item.get("from_path") or "")):
        digest.update(f"{record['code']}\0{record['path']}\0{record.get('from_path') or ''}\0".encode("utf-8"))
        try:
            path = resolve_repo_path(config.repo_root, record["path"])
            if path.exists():
                stat = path.stat()
                digest.update(f"{stat.st_size}:{stat.st_mtime_ns}".encode("ascii"))
        except (OSError, PathSecurityError):
            pass
    return digest.hexdigest()


def _collect_git_state(
    config: ServerConfig,
    *,
    untracked_mode: str = "normal",
    include_ignored: bool = False,
    reviewable_only: bool = False,
    pathspecs: list[str] | None = None,
) -> GitState:
    available, valid, probe_error, probe_stderr, probe_elapsed = _probe_worktree(config)
    if not available or valid is not True:
        return GitState(available, valid, [], None, probe_error, probe_stderr, probe_elapsed)
    if untracked_mode not in {"no", "normal", "all"}:
        raise ValueError("untracked_mode must be no, normal, or all")
    effective_untracked_mode = "all" if include_ignored and untracked_mode != "no" else untracked_mode
    args = ["status", "--porcelain=v1", "-z", f"--untracked-files={effective_untracked_mode}"]
    if include_ignored:
        args.append("--ignored=traditional")
    specs = pathspecs or (_review_pathspecs() if reviewable_only and untracked_mode == "all" else [])
    if specs:
        args.extend(["--", *specs])
    result = _run_git(config, args, timeout_seconds=GIT_STATUS_TIMEOUT_SECONDS, max_output_bytes=GIT_OUTPUT_LIMIT_BYTES)
    stderr = result.stderr.decode("utf-8", errors="replace")[:4096]
    if result.error or result.timed_out or result.returncode != 0:
        return GitState(True, True, _parse_status(result.stdout, include_ignored), None, _bounded_error(result, "git status failed"), stderr, probe_elapsed + result.elapsed_ms)
    records = _parse_status(result.stdout, include_ignored)
    return GitState(True, True, records, _state_fingerprint(config, result.stdout, records), None, stderr, probe_elapsed + result.elapsed_ms)


def _state_fields(state: GitState) -> dict[str, Any]:
    return {"git_available": state.git_available, "git_worktree_valid": state.worktree_valid, "error": state.error, "stderr": state.stderr}


def _fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _grouped(records: list[dict[str, Any]]) -> dict[str, list[Any]]:
    groups: dict[str, list[Any]] = {name: [] for name in ("modified", "added", "untracked", "deleted", "renamed", "copied", "conflicted", "ignored")}
    for record in records:
        value: Any = record["path"]
        if record["kind"] in {"renamed", "copied"}:
            value = {"path": record["path"], "from_path": record["from_path"], "code": record["code"]}
        groups[record["kind"]].append(value)
    return groups


def list_changed_paths(
    config: ServerConfig,
    include_untracked: bool = True,
    include_ignored: bool = False,
    pathspecs: list[str] | None = None,
    max_paths: int = 1000,
    cursor: str | None = None,
) -> dict[str, Any]:
    budget = OperationBudget(2_000)
    safe_specs = [to_repo_relative(config.repo_root, resolve_repo_path(config.repo_root, value)) for value in pathspecs or []]
    request_fingerprint = _fingerprint({"untracked": include_untracked, "ignored": include_ignored, "pathspecs": safe_specs})
    runtime = get_runtime(config.repo_root)
    state = _collect_git_state(config, untracked_mode="normal" if include_untracked else "no", include_ignored=include_ignored, pathspecs=safe_specs or None)
    if not state.ok:
        return {**_grouped([]), "status": "error", "total_paths": None, "truncated": False, "next_cursor": None, "elapsed_ms": budget.elapsed_ms, **_state_fields(state)}
    records = sorted(state.records, key=lambda record: (record["path"], record["kind"], record.get("from_path") or ""))
    position = 0
    if cursor:
        cursor_state = runtime.cursors.read(cursor, "list_changed_paths", request_fingerprint)
        if cursor_state.get("git_fingerprint") != state.fingerprint:
            raise ValueError("Continuation cursor is stale because Git state changed")
        position = int(cursor_state["position"])
    limit = max(1, min(int(max_paths), 10_000))
    page = records[position : position + limit]
    position += len(page)
    partial = position < len(records)
    next_cursor = runtime.cursors.create("list_changed_paths", request_fingerprint, {"position": position, "git_fingerprint": state.fingerprint}) if partial else None
    return {**_grouped(page), "status": "partial" if partial else "ok", "total_paths": len(records), "truncated": partial, "next_cursor": next_cursor, "elapsed_ms": budget.elapsed_ms, **_state_fields(state)}


def _branch_info(config: ServerConfig) -> tuple[str | None, bool | None, str | None, str]:
    result = _run_git(config, ["symbolic-ref", "--quiet", "--short", "HEAD"], timeout_seconds=GIT_STATUS_TIMEOUT_SECONDS, max_output_bytes=4096)
    if result.error or result.timed_out:
        return None, None, _bounded_error(result, "Unable to determine Git branch"), result.stderr.decode("utf-8", errors="replace")[:4096]
    if result.returncode == 0:
        return result.stdout.decode("utf-8", errors="replace").strip() or None, False, None, ""
    if result.returncode == 1:
        return None, True, None, ""
    return None, None, _bounded_error(result, "Unable to determine Git branch"), result.stderr.decode("utf-8", errors="replace")[:4096]


def _legacy_status(records: list[dict[str, Any]], branch: str | None, detached: bool | None) -> str:
    header = f"## {branch}" if branch else "## HEAD (detached)" if detached else "## Git state unavailable"
    lines = [header]
    for record in records:
        if record.get("from_path"):
            lines.append(f"{record['code']} {record['from_path']} -> {record['path']}")
        else:
            lines.append(f"{record['code']} {record['path']}")
    return "\n".join(lines)


def git_status(config: ServerConfig) -> dict[str, Any]:
    state = _collect_git_state(config, untracked_mode="normal")
    if not state.ok:
        return {"status": "", "porcelain": "", "records": [], "branch": None, "detached_head": None, "clean": None, "truncated": False, "elapsed_ms": state.elapsed_ms, **_state_fields(state)}
    branch, detached, branch_error, branch_stderr = _branch_info(config)
    error = branch_error
    porcelain_lines = []
    for record in state.records:
        if record.get("from_path"):
            porcelain_lines.append(f"{record['code']} {record['from_path']} -> {record['path']}")
        else:
            porcelain_lines.append(f"{record['code']} {record['path']}")
    return {"status": _legacy_status(state.records, branch, detached), "porcelain": "\n".join(porcelain_lines), "records": state.records, "branch": branch, "detached_head": detached, "clean": not state.records, "truncated": False, "elapsed_ms": state.elapsed_ms, "git_available": True, "git_worktree_valid": True, "error": error, "stderr": branch_stderr}


def git_status_map(config: ServerConfig, paths: list[str]) -> tuple[dict[str, str], str | None]:
    result = _run_git(config, ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *paths], timeout_seconds=GIT_STATUS_TIMEOUT_SECONDS, max_output_bytes=GIT_OUTPUT_LIMIT_BYTES)
    if result.error or result.timed_out or result.returncode != 0:
        return {}, _bounded_error(result, "git status failed")
    mapping: dict[str, str] = {}
    for record in _parse_status(result.stdout, include_ignored=False):
        mapping[record["path"]] = record["code"]
        if record.get("from_path"):
            mapping[record["from_path"]] = record["code"]
    return mapping, None


def git_path_status(config: ServerConfig, path: str) -> str | None:
    mapping, _ = git_status_map(config, [path])
    return mapping.get(path)


def _diff_paths(config: ServerConfig, safe_paths: list[str], staged: bool) -> tuple[list[str], GitCommandResult]:
    args = ["diff", "--no-ext-diff"]
    if staged:
        args.append("--cached")
    args.extend(["--name-only", "-z", "--", *safe_paths])
    result = _run_git(config, args, timeout_seconds=GIT_DIFF_TIMEOUT_SECONDS, max_output_bytes=1_000_000)
    paths = [part.decode("utf-8", errors="replace").replace("\\", "/") for part in result.stdout.split(b"\0") if part]
    return paths, result


def _complete_diff_lines(result: GitCommandResult) -> tuple[list[str], bool]:
    payload = result.stdout
    complete = not result.stdout_truncated and not result.timed_out
    if not complete:
        last_newline = payload.rfind(b"\n")
        payload = payload[: last_newline + 1] if last_newline >= 0 else b""
    return payload.decode("utf-8", errors="strict").splitlines(keepends=True), complete


def _tracked_diff_lines(config: ServerConfig, path: str, context: int, staged: bool) -> tuple[list[str], bool, GitCommandResult]:
    args = ["diff", "--no-ext-diff"]
    if staged:
        args.append("--cached")
    args.extend([f"--unified={context}", "--", path])
    result = _run_git(config, args, timeout_seconds=GIT_DIFF_TIMEOUT_SECONDS, max_output_bytes=GIT_DIFF_REPLAY_LIMIT_BYTES)
    if result.error or (not result.timed_out and result.returncode not in {0, None}):
        return [], True, result
    try:
        lines, complete = _complete_diff_lines(result)
    except UnicodeDecodeError:
        return [], True, result
    return lines, complete, result


def git_diff(
    config: ServerConfig,
    path: str | None = None,
    max_bytes: int | None = None,
    *,
    paths: list[str] | None = None,
    mode: str = "unified",
    include_untracked: bool = False,
    context_lines: int = 3,
    cursor: str | None = None,
    staged: bool = False,
) -> dict[str, Any]:
    if mode not in {"unified", "stat", "name_only"}:
        raise ValueError("mode must be unified, stat, or name_only")
    if staged and include_untracked:
        raise ValueError("include_untracked cannot be combined with staged=True")
    requested = list(paths or []) + ([path] if path is not None else [])
    safe_paths = [to_repo_relative(config.repo_root, resolve_repo_path(config.repo_root, value)) for value in requested]
    limit = max(1, min(int(max_bytes or config.max_read_bytes), config.max_read_bytes))
    context = max(0, min(int(context_lines), 100))
    request_fingerprint = _fingerprint({"paths": safe_paths, "mode": mode, "include_untracked": include_untracked, "context": context, "staged": staged})
    runtime = get_runtime(config.repo_root)
    git_state = _collect_git_state(config, untracked_mode="all" if include_untracked else "no", reviewable_only=include_untracked)
    if not git_state.ok:
        return {"path": safe_paths[0] if len(safe_paths) == 1 else None, "diff": "", "mode": mode, "staged": staged, "items": [], "status": "error", "truncated": False, "next_cursor": None, "omitted_paths": [], "elapsed_ms": git_state.elapsed_ms, **_state_fields(git_state)}
    tracked, names_result = _diff_paths(config, safe_paths, staged)
    if names_result.error or names_result.timed_out or names_result.returncode not in {0, None}:
        return {"path": None, "diff": "", "mode": mode, "staged": staged, "items": [], "status": "error", "truncated": False, "next_cursor": None, "omitted_paths": [], "elapsed_ms": names_result.elapsed_ms, "git_available": True, "git_worktree_valid": True, "error": _bounded_error(names_result, "git diff failed"), "stderr": names_result.stderr.decode("utf-8", errors="replace")[:4096]}
    entries = [{"kind": "tracked", "path": item} for item in tracked]
    if include_untracked:
        policy = RepositoryScanPolicy()
        entries.extend({"kind": "untracked", "path": record["path"]} for record in git_state.records if record["kind"] == "untracked" and not policy.should_skip_file(record["path"]) and not policy.is_sensitive(record["path"]))
    cursor_state = runtime.cursors.read(cursor, "git_diff", request_fingerprint) if cursor else None
    if cursor_state and cursor_state.get("git_fingerprint") != git_state.fingerprint:
        raise ValueError("Continuation cursor is stale because Git state changed")
    entry_index = int(cursor_state.get("entry_index", 0)) if cursor_state else 0
    line_index = int(cursor_state.get("line_index", 0)) if cursor_state else 0
    pieces: list[str] = []
    items: list[dict[str, Any]] = []
    used = 0
    partial = False
    while entry_index < len(entries) and used < limit:
        entry = entries[entry_index]
        item_path = entry["path"]
        if mode == "name_only":
            piece = f"{item_path}\n"
            if used and used + len(piece.encode("utf-8")) > limit:
                break
            pieces.append(piece)
            items.append({"path": item_path, "content": piece})
            used += len(piece.encode("utf-8"))
            entry_index += 1
            continue
        if mode == "stat":
            if entry["kind"] == "untracked":
                piece = f" untracked: {item_path}\n"
            else:
                stat_args = ["diff", "--no-ext-diff"]
                if staged:
                    stat_args.append("--cached")
                stat_args.extend(["--stat", "--", item_path])
                stat_result = _run_git(config, stat_args, timeout_seconds=GIT_DIFF_TIMEOUT_SECONDS, max_output_bytes=64_000)
                piece = stat_result.stdout.decode("utf-8", errors="replace")
            if used and used + len(piece.encode("utf-8")) > limit:
                break
            pieces.append(piece)
            items.append({"path": item_path, "content": piece})
            used += len(piece.encode("utf-8"))
            entry_index += 1
            continue
        if entry["kind"] == "untracked":
            read = _read_file_record(config, item_path, 1, 10_000, max(1, limit - used))
            if read["error"]:
                entry_index += 1
                continue
            piece = f"# Untracked file: {item_path}\n{read['content']}"
            if used and len(piece.encode("utf-8")) + used > limit:
                break
            pieces.append(piece)
            items.append({"path": item_path, "content": read["content"], "untracked": True, "truncated": read["truncated"]})
            used += len(piece.encode("utf-8"))
            entry_index += 1
            continue
        lines, complete, diff_result = _tracked_diff_lines(config, item_path, context, staged)
        if diff_result.error or (not diff_result.timed_out and diff_result.returncode not in {0, None}):
            return {"path": item_path, "diff": "".join(pieces), "mode": mode, "staged": staged, "items": items, "status": "error", "truncated": bool(items), "next_cursor": None, "omitted_paths": [entry["path"] for entry in entries[entry_index:]], "elapsed_ms": diff_result.elapsed_ms, "git_available": True, "git_worktree_valid": True, "error": _bounded_error(diff_result, "git diff failed"), "stderr": diff_result.stderr.decode("utf-8", errors="replace")[:4096]}
        selected: list[str] = []
        next_line = line_index
        while next_line < len(lines):
            line = lines[next_line]
            size = len(line.encode("utf-8"))
            if selected and used + sum(len(part.encode("utf-8")) for part in selected) + size > limit:
                break
            # Prefer a complete line over an invalid byte-slice, even for a very small caller limit.
            if not selected and used == 0 and size > limit:
                selected.append(line)
                next_line += 1
                break
            if used + sum(len(part.encode("utf-8")) for part in selected) + size > limit:
                break
            selected.append(line)
            next_line += 1
        piece = "".join(selected)
        if piece:
            pieces.append(piece)
            items.append({"path": item_path, "content": piece})
            used += len(piece.encode("utf-8"))
        if next_line < len(lines):
            line_index = next_line
            partial = True
            break
        if not complete:
            partial = True
            break
        entry_index += 1
        line_index = 0
    partial = partial or entry_index < len(entries)
    next_cursor = runtime.cursors.create("git_diff", request_fingerprint, {"entry_index": entry_index, "line_index": line_index, "git_fingerprint": git_state.fingerprint}) if partial else None
    omitted_start = entry_index if line_index == 0 else max(0, entry_index)
    omitted_paths = [entry["path"] for entry in entries[omitted_start:]] if partial else []
    text = "".join(pieces)
    return {"path": safe_paths[0] if len(safe_paths) == 1 else None, "diff": text if mode == "unified" else "", "mode": mode, "staged": staged, "items": items, "output": text if mode != "unified" else None, "status": "partial" if partial else "ok", "truncated": partial, "next_cursor": next_cursor, "omitted_paths": omitted_paths, "elapsed_ms": git_state.elapsed_ms, "git_available": True, "git_worktree_valid": True, "error": None, "stderr": ""}


def _review_candidates(records: list[dict[str, Any]], *, include_modified: bool, include_untracked: bool, include_deleted: bool, include_docs: bool, include_tests: bool, include_configs: bool, extensions: list[str] | None) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, int]]:
    policy = RepositoryScanPolicy()
    normalized_extensions = {value.lower() if value.startswith(".") else f".{value.lower()}" for value in extensions or []}
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    counts = {"source": 0, "test": 0, "config": 0, "script": 0, "documentation": 0, "other": 0}
    for record in sorted(records, key=lambda entry: (entry["path"], entry["kind"], entry.get("from_path") or "")):
        path = record["path"]
        category = classify_source_path(path)
        counts[category] += 1
        if policy.is_sensitive(path):
            skipped.append({"path": path, "reason": "sensitive"})
            continue
        if policy.should_skip_file(path):
            skipped.append({"path": path, "reason": "default_excluded"})
            continue
        if normalized_extensions and Path(path).suffix.lower() not in normalized_extensions:
            continue
        if category == "documentation" and not include_docs:
            continue
        if category == "test" and not include_tests:
            continue
        if category == "config" and not include_configs:
            continue
        if record["kind"] == "untracked" and not include_untracked:
            continue
        if record["kind"] == "deleted" and not include_deleted:
            continue
        if record["kind"] not in {"untracked", "deleted"} and not include_modified:
            continue
        candidates.append({**record, "category": category})
    return candidates, skipped[:100], counts


def read_changed_files(
    config: ServerConfig,
    include_modified: bool = True,
    include_untracked: bool = True,
    include_deleted: bool = False,
    include_docs: bool = False,
    include_tests: bool = True,
    include_configs: bool = True,
    extensions: list[str] | None = None,
    max_files: int = 200,
    max_bytes_per_file: int = 150_000,
    total_max_bytes: int = 3_000_000,
    cursor: str | None = None,
    *,
    _git_state: GitState | None = None,
) -> dict[str, Any]:
    budget = OperationBudget(5_000)
    request_fingerprint = _fingerprint({"modified": include_modified, "untracked": include_untracked, "deleted": include_deleted, "docs": include_docs, "tests": include_tests, "configs": include_configs, "extensions": extensions or []})
    runtime = get_runtime(config.repo_root)
    git_state = _git_state or _collect_git_state(config, untracked_mode="all" if include_untracked else "no", reviewable_only=include_untracked)
    if not git_state.ok:
        return {"status": "error", "items": [], "total_counts": {}, "total_candidate_files": None, "total_returned_bytes": 0, "truncated": False, "next_cursor": None, "skipped_paths": [], "elapsed_ms": budget.elapsed_ms, **_state_fields(git_state)}
    candidates, skipped, totals = _review_candidates(git_state.records, include_modified=include_modified, include_untracked=include_untracked, include_deleted=include_deleted, include_docs=include_docs, include_tests=include_tests, include_configs=include_configs, extensions=extensions)
    position = 0
    if cursor:
        cursor_state = runtime.cursors.read(cursor, "read_changed_files", request_fingerprint)
        if cursor_state.get("git_fingerprint") != git_state.fingerprint:
            raise ValueError("Continuation cursor is stale because Git state changed")
        position = int(cursor_state["position"])
    file_limit = max(1, min(int(max_files), 1_000))
    per_file_limit = max(1, min(int(max_bytes_per_file), config.max_read_bytes))
    total_limit = max(1, min(int(total_max_bytes), max(config.max_read_bytes * 10, 3_000_000)))
    items: list[dict[str, Any]] = []
    returned = 0
    while position < len(candidates) and len(items) < file_limit and returned < total_limit and not budget.exhausted:
        candidate = candidates[position]
        position += 1
        item_path = candidate["path"]
        remaining = min(per_file_limit, total_limit - returned)
        item: dict[str, Any] = {"path": item_path, "change_type": candidate["kind"], "category": candidate["category"], "truncated": False, "error": None}
        if candidate["kind"] == "untracked":
            read = _read_file_record(config, item_path, 1, 10_000, remaining)
            if read["error"]:
                skipped.append({"path": item_path, "reason": read["error"]})
                continue
            item.update({"content": read["content"], "returned_bytes": read["returned_bytes"], "truncated": read["truncated"]})
        elif candidate["kind"] == "deleted":
            result = _run_git(config, ["show", f"HEAD:{item_path}"], timeout_seconds=GIT_DIFF_TIMEOUT_SECONDS, max_output_bytes=remaining)
            if result.returncode not in {0, None} or result.error:
                item["error"] = _bounded_error(result, "git show failed")
            elif b"\0" in result.stdout:
                skipped.append({"path": item_path, "reason": "binary"})
                continue
            else:
                item.update({"previous_content": result.stdout.decode("utf-8", errors="replace"), "returned_bytes": len(result.stdout), "truncated": result.stdout_truncated or result.timed_out})
        else:
            try:
                current = resolve_repo_path(config.repo_root, item_path)
                if current.exists() and not is_probably_text(current):
                    skipped.append({"path": item_path, "reason": "binary"})
                    continue
            except (OSError, PathSecurityError):
                skipped.append({"path": item_path, "reason": "unreadable"})
                continue
            result = _run_git(config, ["diff", "--no-ext-diff", "--unified=3", "HEAD", "--", item_path], timeout_seconds=GIT_DIFF_TIMEOUT_SECONDS, max_output_bytes=remaining)
            if result.returncode not in {0, None} or result.error:
                item["error"] = _bounded_error(result, "git diff failed")
            else:
                item.update({"diff": result.stdout.decode("utf-8", errors="replace"), "returned_bytes": len(result.stdout), "truncated": result.stdout_truncated or result.timed_out})
        returned += int(item.get("returned_bytes", 0))
        items.append(item)
    partial = position < len(candidates)
    next_cursor = runtime.cursors.create("read_changed_files", request_fingerprint, {"position": position, "git_fingerprint": git_state.fingerprint}) if partial else None
    return {"status": "partial" if partial else "ok", "items": items, "total_counts": totals, "total_candidate_files": len(candidates), "total_returned_bytes": returned, "truncated": partial or any(item.get("truncated") for item in items), "next_cursor": next_cursor, "skipped_paths": skipped[:100], "elapsed_ms": budget.elapsed_ms, "git_available": True, "git_worktree_valid": True, "error": None, "stderr": ""}


def _snapshot_from_state(config: ServerConfig, state: GitState, include_changed_paths: bool, include_diff_stat: bool, include_recent_commits: bool, recent_commit_count: int) -> dict[str, Any]:
    if not state.ok:
        return {"repository_root": str(config.repo_root), "branch": None, "detached_head": None, "clean": None, "status": "error", "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "elapsed_ms": state.elapsed_ms, **_state_fields(state)}
    branch, detached, branch_error, branch_stderr = _branch_info(config)
    response: dict[str, Any] = {"repository_root": str(config.repo_root), "branch": branch, "detached_head": detached, "clean": not state.records, "status": "ok" if branch_error is None else "partial", "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git_available": True, "git_worktree_valid": True, "error": branch_error, "stderr": branch_stderr}
    if include_changed_paths:
        groups = _grouped(state.records)
        response["changed_paths"] = groups
        response["changed_path_count"] = len(state.records)
        response["changed_paths_truncated"] = False
    if include_diff_stat:
        diff = _run_git(config, ["diff", "--no-ext-diff", "--stat", "HEAD"], timeout_seconds=GIT_DIFF_TIMEOUT_SECONDS, max_output_bytes=128_000)
        response["diff_stat"] = diff.stdout.decode("utf-8", errors="replace")
        response["diff_stat_truncated"] = diff.stdout_truncated or diff.timed_out
        if diff.error or (not diff.timed_out and diff.returncode not in {0, None}):
            response["diff_stat_error"] = _bounded_error(diff, "git diff --stat failed")
    if include_recent_commits:
        count = max(1, min(int(recent_commit_count), 20))
        commits = _run_git(config, ["log", f"--max-count={count}", "--date=iso-strict", "--pretty=format:%h%x09%ad%x09%s"], timeout_seconds=GIT_STATUS_TIMEOUT_SECONDS, max_output_bytes=32_000)
        response["recent_commits"] = [{"sha": fields[0], "date": fields[1] if len(fields) > 1 else "", "subject": fields[2] if len(fields) > 2 else ""} for line in commits.stdout.decode("utf-8", errors="replace").splitlines() if (fields := line.split("\t", 2))]
    return response


def get_repo_snapshot(config: ServerConfig, include_changed_paths: bool = True, include_diff_stat: bool = True, include_untracked: bool = False, include_recent_commits: bool = False, recent_commit_count: int = 5, *, _git_state: GitState | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    state = _git_state or _collect_git_state(config, untracked_mode="normal" if include_untracked else "no")
    response = _snapshot_from_state(config, state, include_changed_paths, include_diff_stat, include_recent_commits, recent_commit_count)
    response["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    return response


def _related_paths(config: ServerConfig, changed_paths: list[str], want_category: str) -> list[str]:
    runtime = get_runtime(config.repo_root)
    build_budget = OperationBudget(1_000)
    if not runtime.source_index.ensure_ready(build_budget):
        return []
    needles = {Path(path).stem.replace("test_", "") for path in changed_paths if Path(path).stem}
    related: list[str] = []
    for item_path, metadata in sorted(runtime.source_index.entries.items()):
        if metadata["category"] != want_category or item_path in changed_paths:
            continue
        stem = Path(item_path).stem.replace("test_", "")
        if any(needle and (needle == stem or needle in stem or stem in needle) for needle in needles):
            related.append(item_path)
        if len(related) >= 50:
            break
    return related


def get_code_review_bundle(config: ServerConfig, scope: str = "uncommitted", include_new_files: bool = True, include_modified_diffs: bool = True, include_related_tests: bool = True, include_related_configs: bool = True, include_docs: bool = False, max_total_bytes: int = 3_000_000, cursor: str | None = None) -> dict[str, Any]:
    if scope != "uncommitted":
        raise ValueError("Only scope='uncommitted' is currently supported")
    started = time.perf_counter()
    summary_state = _collect_git_state(config, untracked_mode="normal" if include_new_files else "no")
    snapshot = get_repo_snapshot(config, include_changed_paths=True, include_diff_stat=True, include_untracked=include_new_files, _git_state=summary_state)
    if not summary_state.ok:
        return {"scope": scope, "status": "error", "repository_snapshot": snapshot, "changed_paths": {}, "diff_stat": "", "changes": [], "related_test_paths": [], "related_config_paths": [], "omitted_paths": [], "truncated": False, "next_cursor": None, "elapsed_ms": int((time.perf_counter() - started) * 1000), **_state_fields(summary_state)}
    review_state = _collect_git_state(config, untracked_mode="all" if include_new_files else "no", reviewable_only=include_new_files)
    if not review_state.ok:
        return {"scope": scope, "status": "error", "repository_snapshot": snapshot, "changed_paths": snapshot.get("changed_paths", {}), "diff_stat": snapshot.get("diff_stat", ""), "changes": [], "related_test_paths": [], "related_config_paths": [], "omitted_paths": [], "truncated": False, "next_cursor": None, "elapsed_ms": int((time.perf_counter() - started) * 1000), **_state_fields(review_state)}
    changed = read_changed_files(config, include_modified=include_modified_diffs, include_untracked=include_new_files, include_docs=include_docs, max_bytes_per_file=min(150_000, max(1, int(max_total_bytes))), total_max_bytes=max_total_bytes, cursor=cursor, _git_state=review_state)
    changed_paths = [record["path"] for record in summary_state.records]
    review_paths = {record["path"] for record in review_state.records}
    omitted = list(changed["skipped_paths"])
    for record in summary_state.records:
        if record["path"] not in review_paths and len(omitted) < 100:
            omitted.append({"path": record["path"], "reason": "default_excluded"})
    final_summary = _collect_git_state(config, untracked_mode="normal" if include_new_files else "no")
    final_review = _collect_git_state(config, untracked_mode="all" if include_new_files else "no", reviewable_only=include_new_files)
    stale = not final_summary.ok or not final_review.ok or final_summary.fingerprint != summary_state.fingerprint or final_review.fingerprint != review_state.fingerprint
    return {"scope": scope, "status": "stale" if stale else changed["status"], "repository_snapshot": snapshot, "changed_paths": snapshot.get("changed_paths", {}), "diff_stat": snapshot.get("diff_stat", ""), "changes": changed["items"], "related_test_paths": _related_paths(config, changed_paths, "test") if include_related_tests and not stale else [], "related_config_paths": _related_paths(config, changed_paths, "config") if include_related_configs and not stale else [], "omitted_paths": omitted, "truncated": changed["truncated"] or stale, "next_cursor": None if stale else changed["next_cursor"], "elapsed_ms": int((time.perf_counter() - started) * 1000), "git_available": final_summary.git_available, "git_worktree_valid": final_summary.worktree_valid, "error": "Git state changed while collecting the review bundle" if stale else None, "stderr": final_summary.stderr if stale else ""}


def mcp_health(config: ServerConfig) -> dict[str, Any]:
    health = get_runtime(config.repo_root).health()
    started = time.perf_counter()
    # Health is intentionally a metadata-only probe.  Git-backed tools perform
    # the authoritative `rev-parse` check before reporting repository state.
    # Avoiding a subprocess here keeps frequent MCP health checks cheap.
    available = shutil.which("git") is not None
    git_marker = config.repo_root / ".git"
    valid = git_marker.is_dir() or git_marker.is_file()
    error = None
    if not available:
        error = "Git executable is unavailable"
    elif not valid:
        error = "Configured repository root is not a Git worktree"
    elapsed = int((time.perf_counter() - started) * 1000)
    health.update({"git_available": available, "git_worktree_valid": valid if available else None, "git_error": error, "git_stderr": "", "git_probe_elapsed_ms": elapsed, "git_probe_kind": "structural", "status": "ok" if available and valid else "degraded"})
    return health


def mcp_diagnostics(config: ServerConfig) -> dict[str, Any]:
    return get_runtime(config.repo_root).diagnostics()


def git_log(config: ServerConfig, max_count: int = 20) -> dict[str, Any]:
    count = max(1, min(max_count, 100))
    text = _git(config, ["log", f"--max-count={count}", "--date=iso-strict", "--pretty=format:%H%x09%ad%x09%an%x09%s"])
    commits = []
    for line in text.splitlines():
        sha, date, author, subject = (line.split("\t", 3) + ["", "", "", ""])[:4]
        commits.append({"sha": sha, "date": date, "author": author, "subject": subject})
    return {"commits": commits}


def git_current_branch(config: ServerConfig) -> dict[str, str | None]:
    state = _collect_git_state(config, untracked_mode="no")
    if not state.ok:
        return {"branch": None, **_state_fields(state)}
    branch, detached, error, stderr = _branch_info(config)
    return {"branch": branch, "detached_head": detached, "error": error, "stderr": stderr, "git_available": True, "git_worktree_valid": True}
