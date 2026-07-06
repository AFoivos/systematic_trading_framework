from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .config import ServerConfig
from .security import (
    PathSecurityError,
    reject_protected_write_path,
    resolve_repo_path,
    to_repo_relative,
)


def _require_full_access(config: ServerConfig, capability: str, confirmation: str | None) -> None:
    full = config.full_access
    allowed = {
        "write": full.allow_write,
        "delete": full.allow_delete,
    }.get(capability, False)
    if not full.enabled or not allowed:
        raise PermissionError(f"Full-access {capability} operations are disabled in MCP config")
    if full.require_confirmation and confirmation != full.confirmation_token:
        raise PermissionError(f"Full-access {capability} operations require confirmation='{full.confirmation_token}'")


def _resolve_mutable_path(config: ServerConfig, path: str) -> tuple[Path, str]:
    resolved = resolve_repo_path(config.repo_root, path)
    rel = to_repo_relative(config.repo_root, resolved)
    reject_protected_write_path(rel)
    return resolved, rel


def _preview(content: str, limit: int = 500) -> str:
    return content[:limit]


def write_file(
    config: ServerConfig,
    path: str,
    content: str,
    create_dirs: bool = True,
    overwrite: bool = True,
    confirmation: str | None = None,
) -> dict[str, Any]:
    _require_full_access(config, "write", confirmation)
    target, rel = _resolve_mutable_path(config, path)
    existed = target.exists()
    if existed and not target.is_file():
        raise IsADirectoryError(path)
    if existed and not overwrite:
        return {"ok": False, "error": f"File already exists: {rel}", "path": rel, "existed": True}
    if create_dirs:
        target.parent.mkdir(parents=True, exist_ok=True)
    elif not target.parent.is_dir():
        raise FileNotFoundError(target.parent.as_posix())
    target.write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "path": rel,
        "bytes_written": len(content.encode("utf-8")),
        "existed": existed,
        "preview": _preview(content),
    }


def append_file(
    config: ServerConfig,
    path: str,
    content: str,
    create_dirs: bool = True,
    confirmation: str | None = None,
) -> dict[str, Any]:
    _require_full_access(config, "write", confirmation)
    target, rel = _resolve_mutable_path(config, path)
    existed = target.exists()
    if existed and not target.is_file():
        raise IsADirectoryError(path)
    if create_dirs:
        target.parent.mkdir(parents=True, exist_ok=True)
    elif not target.parent.is_dir():
        raise FileNotFoundError(target.parent.as_posix())
    with target.open("a", encoding="utf-8") as fh:
        fh.write(content)
    return {
        "ok": True,
        "path": rel,
        "bytes_written": len(content.encode("utf-8")),
        "existed": existed,
        "preview": _preview(content),
    }


def _patch_paths(patch: str) -> list[str]:
    paths: list[str] = []
    for line in patch.splitlines():
        candidates: list[str] = []
        if line.startswith(("--- ", "+++ ")):
            candidates.append(line[4:].split("\t", 1)[0].strip())
        elif line.startswith("diff --git "):
            candidates.extend(line.split()[2:4])
        elif line.startswith(("rename from ", "rename to ")):
            candidates.append(line.split(" ", 2)[2].strip())
        elif line.startswith(("copy from ", "copy to ")):
            candidates.append(line.split(" ", 2)[2].strip())
        for raw in candidates:
            if raw == "/dev/null":
                continue
            raw = re.sub(r"^[ab]/", "", raw)
            paths.append(raw)
    return paths


def _validate_patch_paths(config: ServerConfig, patch: str) -> None:
    for path in _patch_paths(patch):
        resolved = resolve_repo_path(config.repo_root, path)
        rel = to_repo_relative(config.repo_root, resolved)
        reject_protected_write_path(rel)


def _timeout(config: ServerConfig, timeout_seconds: int | None) -> int:
    requested = timeout_seconds or config.full_access.default_timeout_seconds
    return max(1, min(requested, config.full_access.max_timeout_seconds))


def apply_patch(
    config: ServerConfig,
    patch: str,
    confirmation: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    _require_full_access(config, "write", confirmation)
    _validate_patch_paths(config, patch)
    proc = subprocess.run(
        ["git", "apply"],
        cwd=config.repo_root,
        input=patch,
        check=False,
        capture_output=True,
        text=True,
        timeout=_timeout(config, timeout_seconds),
    )
    return {
        "command": "git apply",
        "return_code": proc.returncode,
        "stdout": proc.stdout[-config.full_access.max_output_bytes :],
        "stderr": proc.stderr[-config.full_access.max_output_bytes :],
    }


def delete_path(
    config: ServerConfig,
    path: str,
    recursive: bool = False,
    confirmation: str | None = None,
) -> dict[str, Any]:
    _require_full_access(config, "delete", confirmation)
    target = resolve_repo_path(config.repo_root, path)
    if target == config.repo_root:
        raise PermissionError("Refusing to delete repository root")
    rel = to_repo_relative(config.repo_root, target)
    if rel == ".git" or rel.startswith(".git/"):
        raise PermissionError("Refusing to delete .git")
    reject_protected_write_path(rel)
    if not target.exists():
        return {"ok": False, "path": rel, "deleted": False, "error": "Path does not exist"}
    if target.is_dir():
        if not recursive:
            raise IsADirectoryError("Directory deletion requires recursive=True")
        shutil.rmtree(target)
    else:
        target.unlink()
    return {"ok": True, "path": rel, "deleted": True, "recursive": recursive}


def move_path(
    config: ServerConfig,
    src: str,
    dst: str,
    overwrite: bool = False,
    confirmation: str | None = None,
) -> dict[str, Any]:
    _require_full_access(config, "write", confirmation)
    source = resolve_repo_path(config.repo_root, src)
    if not source.exists():
        raise FileNotFoundError(src)
    src_rel = to_repo_relative(config.repo_root, source)
    if src_rel == ".git" or src_rel.startswith(".git/"):
        raise PermissionError("Refusing to move .git")
    reject_protected_write_path(src_rel)
    destination, dst_rel = _resolve_mutable_path(config, dst)
    if destination.exists() and not overwrite:
        return {"ok": False, "error": f"Destination already exists: {dst_rel}", "src": src_rel, "dst": dst_rel}
    if destination.exists():
        if destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return {"ok": True, "src": src_rel, "dst": dst_rel, "overwrote": overwrite}
