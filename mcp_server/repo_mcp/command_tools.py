from __future__ import annotations

import re
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
        "shell": full.allow_shell,
        "git_write": full.allow_git_write,
    }.get(capability, False)
    if not full.enabled or not allowed:
        raise PermissionError(f"Full-access {capability} operations are disabled in MCP config")
    if full.require_confirmation and confirmation != full.confirmation_token:
        raise PermissionError(f"Full-access {capability} operations require confirmation='{full.confirmation_token}'")


def _timeout(config: ServerConfig, timeout_seconds: int | None) -> int:
    requested = timeout_seconds or config.full_access.default_timeout_seconds
    return max(1, min(requested, config.full_access.max_timeout_seconds))


def _max_output(config: ServerConfig, max_output_bytes: int | None = None) -> int:
    return max(1, min(max_output_bytes or config.full_access.max_output_bytes, config.full_access.max_output_bytes))


def _truncate_text(text: str, max_bytes: int) -> tuple[str, bool]:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text, False
    truncated = encoded[-max_bytes:].decode("utf-8", errors="replace")
    return truncated, True


def _resolve_cwd(config: ServerConfig, cwd: str) -> tuple[Path, str]:
    resolved = resolve_repo_path(config.repo_root, cwd)
    if not resolved.exists():
        raise FileNotFoundError(cwd)
    if not resolved.is_dir():
        raise NotADirectoryError(cwd)
    return resolved, "." if resolved == config.repo_root else to_repo_relative(config.repo_root, resolved)


def _run(
    config: ServerConfig,
    args: list[str],
    timeout_seconds: int | None = None,
    max_output_bytes: int | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    limit = _max_output(config, max_output_bytes)
    try:
        proc = subprocess.run(
            args,
            cwd=cwd or config.repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=_timeout(config, timeout_seconds),
        )
        stdout, stdout_truncated = _truncate_text(proc.stdout, limit)
        stderr, stderr_truncated = _truncate_text(proc.stderr, limit)
        return {
            "command": args,
            "return_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": False,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }
    except subprocess.TimeoutExpired as exc:
        stdout_text = exc.stdout or ""
        stderr_text = exc.stderr or ""
        if isinstance(stdout_text, bytes):
            stdout_text = stdout_text.decode("utf-8", errors="replace")
        if isinstance(stderr_text, bytes):
            stderr_text = stderr_text.decode("utf-8", errors="replace")
        stdout, stdout_truncated = _truncate_text(stdout_text, limit)
        stderr, stderr_truncated = _truncate_text(stderr_text, limit)
        return {
            "command": args,
            "return_code": None,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": True,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }


def run_shell_command(
    config: ServerConfig,
    command: str,
    cwd: str = ".",
    timeout_seconds: int | None = None,
    confirmation: str | None = None,
    max_output_bytes: int | None = None,
) -> dict[str, Any]:
    _require_full_access(config, "shell", confirmation)
    cwd_path, rel_cwd = _resolve_cwd(config, cwd)
    limit = _max_output(config, max_output_bytes)
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd_path,
            check=False,
            capture_output=True,
            text=True,
            timeout=_timeout(config, timeout_seconds),
        )
        stdout, stdout_truncated = _truncate_text(proc.stdout, limit)
        stderr, stderr_truncated = _truncate_text(proc.stderr, limit)
        return {
            "command": command,
            "cwd": rel_cwd,
            "return_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": False,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }
    except subprocess.TimeoutExpired as exc:
        stdout_text = exc.stdout or ""
        stderr_text = exc.stderr or ""
        if isinstance(stdout_text, bytes):
            stdout_text = stdout_text.decode("utf-8", errors="replace")
        if isinstance(stderr_text, bytes):
            stderr_text = stderr_text.decode("utf-8", errors="replace")
        stdout, stdout_truncated = _truncate_text(stdout_text, limit)
        stderr, stderr_truncated = _truncate_text(stderr_text, limit)
        return {
            "command": command,
            "cwd": rel_cwd,
            "return_code": None,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": True,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }


def _recent_run_dirs(config: ServerConfig) -> set[str]:
    logs = config.repo_root / "logs"
    if not logs.is_dir():
        return set()
    return {
        to_repo_relative(config.repo_root, item.parent)
        for item in logs.rglob("artifact_manifest.json")
        if item.is_file()
    }


def _newest_created_run(before: set[str], after: set[str], config: ServerConfig) -> str | None:
    created = sorted(after - before)
    if not created:
        return None
    return max(created, key=lambda rel: (config.repo_root / rel).stat().st_mtime)


def run_experiment(
    config: ServerConfig,
    config_path: str,
    timeout_seconds: int | None = None,
    confirmation: str | None = None,
) -> dict[str, Any]:
    _require_full_access(config, "shell", confirmation)
    resolved = resolve_repo_path(config.repo_root, config_path)
    rel = to_repo_relative(config.repo_root, resolved)
    if not (rel == "config/experiments" or rel.startswith("config/experiments/")):
        raise PathSecurityError("Experiment configs must be under config/experiments/")
    if not resolved.is_file():
        raise FileNotFoundError(config_path)
    before = _recent_run_dirs(config)
    result = _run(
        config,
        ["python", "-m", "src.experiments.runner", rel],
        timeout_seconds=timeout_seconds,
    )
    after = _recent_run_dirs(config)
    return {
        "config_path": rel,
        "return_code": result["return_code"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "timed_out": result["timed_out"],
        "created_run_dir": _newest_created_run(before, after, config),
    }


def _validate_git_paths(config: ServerConfig, paths: list[str]) -> list[str]:
    if not paths:
        raise ValueError("At least one path is required")
    resolved: list[str] = []
    for path in paths:
        target = resolve_repo_path(config.repo_root, path)
        rel = to_repo_relative(config.repo_root, target)
        if rel == ".git" or rel.startswith(".git/"):
            raise PermissionError("Refusing git write operations on .git")
        reject_protected_write_path(rel)
        resolved.append(rel)
    return resolved


def git_add(config: ServerConfig, paths: list[str], confirmation: str | None = None) -> dict[str, Any]:
    _require_full_access(config, "git_write", confirmation)
    rel_paths = _validate_git_paths(config, paths)
    result = _run(config, ["git", "add", "--", *rel_paths])
    return {**result, "paths": rel_paths}


def git_commit(config: ServerConfig, message: str, confirmation: str | None = None) -> dict[str, Any]:
    _require_full_access(config, "git_write", confirmation)
    if not message.strip():
        raise ValueError("Commit message must not be empty")
    return _run(config, ["git", "commit", "-m", message])


def git_checkout_new_branch(
    config: ServerConfig,
    branch_name: str,
    confirmation: str | None = None,
) -> dict[str, Any]:
    _require_full_access(config, "git_write", confirmation)
    if not re.fullmatch(r"[A-Za-z0-9._/\-]+", branch_name) or branch_name.startswith(("-", "/", ".")):
        raise ValueError("Branch name contains unsupported characters")
    return _run(config, ["git", "checkout", "-b", branch_name])


def git_restore(config: ServerConfig, paths: list[str], confirmation: str | None = None) -> dict[str, Any]:
    _require_full_access(config, "git_write", confirmation)
    rel_paths = _validate_git_paths(config, paths)
    result = _run(config, ["git", "restore", "--", *rel_paths])
    return {**result, "paths": rel_paths}
