from __future__ import annotations

import ast
import fnmatch
import json
import re
from pathlib import Path
from typing import Any

from .config import ServerConfig
from .security import (
    PathSecurityError,
    is_probably_text,
    read_text_limited,
    resolve_repo_path,
    to_repo_relative,
)


def _iter_paths(root: Path, recursive: bool) -> list[Path]:
    if recursive:
        return sorted(root.rglob("*"), key=lambda item: item.as_posix())
    return sorted(root.iterdir(), key=lambda item: item.as_posix())


def list_directory(config: ServerConfig, path: str = ".", recursive: bool = False, max_entries: int | None = None) -> dict[str, Any]:
    directory = resolve_repo_path(config.repo_root, path)
    if not directory.exists():
        raise FileNotFoundError(path)
    if not directory.is_dir():
        raise NotADirectoryError(path)

    limit = min(max_entries or config.max_tree_entries, config.max_tree_entries)
    entries: list[dict[str, Any]] = []
    truncated = False
    for item in _iter_paths(directory, recursive):
        try:
            resolved = item.resolve()
            if resolved != config.repo_root and config.repo_root not in resolved.parents:
                continue
        except OSError:
            continue
        if len(entries) >= limit:
            truncated = True
            break
        entries.append(
            {
                "path": to_repo_relative(config.repo_root, item),
                "type": "directory" if item.is_dir() else "file",
                "size_bytes": item.stat().st_size if item.is_file() else None,
            }
        )
    return {"root": to_repo_relative(config.repo_root, directory) if directory != config.repo_root else ".", "entries": entries, "truncated": truncated}


def read_file(config: ServerConfig, path: str, start_line: int | None = None, max_lines: int | None = None, max_bytes: int | None = None) -> dict[str, Any]:
    file_path = resolve_repo_path(config.repo_root, path)
    if not file_path.exists():
        raise FileNotFoundError(path)
    if not file_path.is_file():
        raise IsADirectoryError(path)

    byte_limit = min(max_bytes or config.max_read_bytes, config.max_read_bytes)
    text, byte_truncated = read_text_limited(file_path, byte_limit)
    lines = text.splitlines()
    total_lines = len(lines)
    start = max((start_line or 1) - 1, 0)
    selected = lines[start:]
    line_truncated = False
    if max_lines is not None:
        selected = selected[: max(max_lines, 0)]
        line_truncated = start + len(selected) < total_lines
    return {
        "path": to_repo_relative(config.repo_root, file_path),
        "size_bytes": file_path.stat().st_size,
        "start_line": start + 1,
        "line_count": len(selected),
        "total_lines": total_lines,
        "truncated": byte_truncated or line_truncated,
        "text": "\n".join(selected),
    }


def read_project_tree(config: ServerConfig, max_depth: int = 4, include_files: bool = True, max_entries: int | None = None) -> dict[str, Any]:
    limit = min(max_entries or config.max_tree_entries, config.max_tree_entries)
    root = config.repo_root
    entries: list[dict[str, Any]] = []
    truncated = False
    for item in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        try:
            rel = item.relative_to(root)
        except ValueError:
            continue
        depth = len(rel.parts)
        if depth > max_depth:
            continue
        if item.is_file() and not include_files:
            continue
        if len(entries) >= limit:
            truncated = True
            break
        entries.append({"path": rel.as_posix(), "type": "directory" if item.is_dir() else "file", "depth": depth})
    return {"root": ".", "max_depth": max_depth, "entries": entries, "truncated": truncated}


def search_files(config: ServerConfig, pattern: str, root: str = ".", max_results: int | None = None) -> dict[str, Any]:
    search_root = resolve_repo_path(config.repo_root, root)
    if not search_root.is_dir():
        raise NotADirectoryError(root)
    limit = min(max_results or config.max_search_results, config.max_search_results)
    results: list[dict[str, Any]] = []
    for item in sorted(search_root.rglob("*"), key=lambda item: item.as_posix()):
        if len(results) >= limit:
            break
        try:
            rel = to_repo_relative(config.repo_root, item)
        except ValueError:
            continue
        if fnmatch.fnmatch(item.name, pattern) or fnmatch.fnmatch(rel, pattern):
            results.append({"path": rel, "type": "directory" if item.is_dir() else "file"})
    return {"pattern": pattern, "results": results, "truncated": len(results) >= limit}


def search_code(config: ServerConfig, query: str, root: str = ".", file_glob: str | None = None, max_results: int | None = None, context_lines: int = 1) -> dict[str, Any]:
    search_root = resolve_repo_path(config.repo_root, root)
    if not search_root.is_dir():
        raise NotADirectoryError(root)
    limit = min(max_results or config.max_search_results, config.max_search_results)
    results: list[dict[str, Any]] = []
    needle = query.lower()
    for item in sorted(search_root.rglob("*"), key=lambda item: item.as_posix()):
        if len(results) >= limit:
            break
        if not item.is_file() or not is_probably_text(item):
            continue
        rel = to_repo_relative(config.repo_root, item)
        if file_glob and not fnmatch.fnmatch(rel, file_glob):
            continue
        text, _ = read_text_limited(item, config.max_read_bytes)
        lines = text.splitlines()
        for index, line in enumerate(lines, start=1):
            if needle not in line.lower():
                continue
            before = max(index - context_lines - 1, 0)
            after = min(index + context_lines, len(lines))
            results.append(
                {
                    "path": rel,
                    "line": index,
                    "match": line,
                    "context": "\n".join(lines[before:after]),
                }
            )
            if len(results) >= limit:
                break
    return {"query": query, "results": results, "truncated": len(results) >= limit}


def _python_symbols(path: Path, repo_root: Path) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    rel = to_repo_relative(repo_root, path)
    symbols: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            symbols.append({"name": node.name, "kind": kind, "path": rel, "line": node.lineno})
    return symbols


def _text_symbols(path: Path, repo_root: Path) -> list[dict[str, Any]]:
    rel = to_repo_relative(repo_root, path)
    symbols: list[dict[str, Any]] = []
    if path.suffix.lower() == ".md":
        for index, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if line.startswith("#"):
                symbols.append({"name": line.lstrip("#").strip(), "kind": "markdown_heading", "path": rel, "line": index})
    return symbols


def search_symbols(config: ServerConfig, query: str, root: str = ".", max_results: int | None = None) -> dict[str, Any]:
    search_root = resolve_repo_path(config.repo_root, root)
    if not search_root.is_dir():
        raise NotADirectoryError(root)
    limit = min(max_results or config.max_search_results, config.max_search_results)
    results: list[dict[str, Any]] = []
    needle = query.lower()
    for item in sorted(search_root.rglob("*"), key=lambda item: item.as_posix()):
        if len(results) >= limit:
            break
        if not item.is_file():
            continue
        symbols = _python_symbols(item, config.repo_root) if item.suffix == ".py" else _text_symbols(item, config.repo_root)
        for symbol in symbols:
            if needle in symbol["name"].lower():
                results.append(symbol)
                if len(results) >= limit:
                    break
    return {"query": query, "results": results, "truncated": len(results) >= limit}


def find_references(config: ServerConfig, symbol: str, root: str = ".", max_results: int | None = None) -> dict[str, Any]:
    pattern = re.compile(rf"\b{re.escape(symbol)}\b")
    search_root = resolve_repo_path(config.repo_root, root)
    if not search_root.is_dir():
        raise NotADirectoryError(root)
    limit = min(max_results or config.max_search_results, config.max_search_results)
    results: list[dict[str, Any]] = []
    for item in sorted(search_root.rglob("*"), key=lambda item: item.as_posix()):
        if len(results) >= limit:
            break
        if not item.is_file() or not is_probably_text(item):
            continue
        rel = to_repo_relative(config.repo_root, item)
        text, _ = read_text_limited(item, config.max_read_bytes)
        for index, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                results.append({"path": rel, "line": index, "text": line})
                if len(results) >= limit:
                    break
    return {"symbol": symbol, "results": results, "truncated": len(results) >= limit}


def search_standard(config: ServerConfig, query: str) -> str:
    code_results = search_code(config, query=query, max_results=25)["results"]
    file_results = search_files(config, pattern=f"*{query}*", max_results=25)["results"]
    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    for result in file_results + code_results:
        path = result["path"]
        if path in seen:
            continue
        seen.add(path)
        merged.append({"id": path, "title": path, "url": f"repo://{path}"})
    return json.dumps({"results": merged}, ensure_ascii=False)


def fetch_standard(config: ServerConfig, item_id: str) -> str:
    payload = read_file(config, item_id)
    return json.dumps(
        {
            "id": payload["path"],
            "title": payload["path"],
            "text": payload["text"],
            "url": f"repo://{payload['path']}",
            "metadata": {
                "size_bytes": payload["size_bytes"],
                "truncated": payload["truncated"],
                "line_count": payload["line_count"],
            },
        },
        ensure_ascii=False,
    )
