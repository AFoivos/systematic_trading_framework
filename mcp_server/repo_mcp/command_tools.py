from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from .config import ServerConfig
from .security import (
    PathSecurityError,
    reject_protected_write_path,
    resolve_repo_path,
    to_repo_relative,
)


_SECRET_KEY_RE = re.compile(
    r"(?:TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE_KEY)",
    flags=re.IGNORECASE,
)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(\b[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE_KEY)[A-Z0-9_]*\b\s*[=:]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;}]*)"
)


def _require_full_access(config: ServerConfig, capability: str, confirmation: str | None) -> None:
    full = config.full_access
    allowed = {
        "shell": full.allow_shell,
        "git_write": full.allow_git_write,
    }.get(capability, False)
    if not full.enabled or not allowed:
        raise PermissionError(f"Full-access {capability} operations are disabled in MCP config")
    if full.require_confirmation and not (confirmation or "").strip():
        raise PermissionError(
            f"Full-access {capability} operations require a non-empty confirmation describing the user's explicit request"
        )


def _timeout(config: ServerConfig, timeout_seconds: int | None) -> int:
    requested = timeout_seconds or config.full_access.default_timeout_seconds
    return max(1, min(int(requested), config.full_access.max_timeout_seconds))


def _max_output(config: ServerConfig, max_output_bytes: int | None = None) -> int:
    return max(
        1,
        min(
            int(max_output_bytes or config.full_access.max_output_bytes),
            config.full_access.max_output_bytes,
        ),
    )


def _resolve_cwd(config: ServerConfig, cwd: str) -> tuple[Path, str]:
    resolved = resolve_repo_path(config.repo_root, cwd)
    if not resolved.exists():
        raise FileNotFoundError(cwd)
    if not resolved.is_dir():
        raise NotADirectoryError(cwd)
    return resolved, "." if resolved == config.repo_root else to_repo_relative(config.repo_root, resolved)


def _validate_arguments(command: list[str]) -> list[str]:
    if not isinstance(command, list) or not command:
        raise ValueError("command must be a non-empty argument array")
    normalized: list[str] = []
    for index, value in enumerate(command):
        if not isinstance(value, str):
            raise TypeError(f"command[{index}] must be a string")
        if "\0" in value:
            raise ValueError(f"command[{index}] contains a NUL byte")
        normalized.append(value)
    if not normalized[0]:
        raise ValueError("command executable must not be empty")
    return normalized


def _subprocess_environment(extra: dict[str, str] | None) -> tuple[dict[str, str], set[str]]:
    redacted_values = {
        value
        for key, value in os.environ.items()
        if _SECRET_KEY_RE.search(key) and value
    }
    environment = {
        key: value
        for key, value in os.environ.items()
        if not _SECRET_KEY_RE.search(key)
    }
    for key, value in (extra or {}).items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise TypeError("env keys and values must be strings")
        if not key or "=" in key or "\0" in key or "\0" in value:
            raise ValueError(f"Invalid environment entry: {key!r}")
        environment[key] = value
        if _SECRET_KEY_RE.search(key) and value:
            redacted_values.add(value)
    return environment, redacted_values


def _redact_text(value: str, redacted_values: set[str]) -> str:
    result = value
    for secret in sorted(redacted_values, key=len, reverse=True):
        if len(secret) >= 4:
            result = result.replace(secret, "<redacted>")
    return _SECRET_ASSIGNMENT_RE.sub(r"\1<redacted>", result)


def _redact_command(command: list[str] | str, redacted_values: set[str]) -> list[str] | str:
    if isinstance(command, str):
        return _redact_text(command, redacted_values)
    return [_redact_text(value, redacted_values) for value in command]


class _BoundedCapture:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.head_limit = max(1, limit // 2)
        self.tail_limit = max(0, limit - self.head_limit)
        self.head = bytearray()
        self.tail = bytearray()
        self.total_bytes = 0

    def add(self, chunk: bytes) -> None:
        self.total_bytes += len(chunk)
        available = max(0, self.head_limit - len(self.head))
        if available:
            self.head.extend(chunk[:available])
            chunk = chunk[available:]
        if chunk and self.tail_limit:
            self.tail.extend(chunk)
            if len(self.tail) > self.tail_limit:
                del self.tail[: len(self.tail) - self.tail_limit]

    @property
    def truncated(self) -> bool:
        return self.total_bytes > self.limit

    def text(self) -> str:
        if not self.truncated:
            return bytes(self.head + self.tail).decode("utf-8", errors="replace")
        omitted = self.total_bytes - len(self.head) - len(self.tail)
        marker = f"\n... <{omitted} bytes omitted> ...\n".encode("utf-8")
        return bytes(self.head + marker + self.tail).decode("utf-8", errors="replace")


def _drain(stream: Any, capture: _BoundedCapture) -> None:
    try:
        while chunk := stream.read(64 * 1024):
            capture.add(chunk)
    finally:
        stream.close()


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (AttributeError, ProcessLookupError, PermissionError):
        process.kill()


def _run_process(
    config: ServerConfig,
    command: list[str] | str,
    *,
    cwd: Path,
    relative_cwd: str,
    env: dict[str, str] | None = None,
    timeout_seconds: int | None = None,
    max_output_bytes: int | None = None,
    shell: bool = False,
) -> dict[str, Any]:
    limit = _max_output(config, max_output_bytes)
    effective_timeout = _timeout(config, timeout_seconds)
    environment, redacted_values = _subprocess_environment(env)
    started = time.perf_counter()
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=shell,
            start_new_session=True,
        )
    except OSError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "success": False,
            "command": _redact_command(command, redacted_values),
            "cwd": relative_cwd,
            "exit_code": None,
            "return_code": None,
            "stdout": "",
            "stderr": "",
            "elapsed_ms": elapsed_ms,
            "timed_out": False,
            "truncated": False,
            "stdout_truncated": False,
            "stderr_truncated": False,
            "stdout_total_bytes": 0,
            "stderr_total_bytes": 0,
            "timeout_seconds": effective_timeout,
            "error": {"code": "process_start_failed", "message": str(exc)},
        }

    assert process.stdout is not None
    assert process.stderr is not None
    stdout_capture = _BoundedCapture(limit)
    stderr_capture = _BoundedCapture(limit)
    stdout_thread = threading.Thread(target=_drain, args=(process.stdout, stdout_capture), daemon=True)
    stderr_thread = threading.Thread(target=_drain, args=(process.stderr, stderr_capture), daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    timed_out = False
    try:
        process.wait(timeout=effective_timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_process_group(process)
        process.wait()
    stdout_thread.join(timeout=2)
    stderr_thread.join(timeout=2)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    exit_code = None if timed_out else process.returncode
    success = exit_code == 0 and not timed_out
    stdout = _redact_text(stdout_capture.text(), redacted_values)
    stderr = _redact_text(stderr_capture.text(), redacted_values)
    if timed_out:
        error = {
            "code": "command_timed_out",
            "message": f"Command exceeded timeout_seconds={effective_timeout}",
        }
    elif exit_code != 0:
        error = {
            "code": "nonzero_exit",
            "message": f"Command exited with code {exit_code}",
        }
    else:
        error = None
    return {
        "success": success,
        "command": _redact_command(command, redacted_values),
        "cwd": relative_cwd,
        "exit_code": exit_code,
        "return_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "elapsed_ms": elapsed_ms,
        "timed_out": timed_out,
        "truncated": stdout_capture.truncated or stderr_capture.truncated,
        "stdout_truncated": stdout_capture.truncated,
        "stderr_truncated": stderr_capture.truncated,
        "stdout_total_bytes": stdout_capture.total_bytes,
        "stderr_total_bytes": stderr_capture.total_bytes,
        "timeout_seconds": effective_timeout,
        "error": error,
    }


def run_command(
    config: ServerConfig,
    command: list[str],
    cwd: str = ".",
    env: dict[str, str] | None = None,
    timeout_seconds: int | None = None,
    confirmation: str | None = None,
    max_output_bytes: int | None = None,
) -> dict[str, Any]:
    """Run an arbitrary argument-array command inside the repository boundary."""
    _require_full_access(config, "shell", confirmation)
    arguments = _validate_arguments(command)
    cwd_path, relative_cwd = _resolve_cwd(config, cwd)
    return _run_process(
        config,
        arguments,
        cwd=cwd_path,
        relative_cwd=relative_cwd,
        env=env,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        shell=False,
    )


def run_python(
    config: ServerConfig,
    code: str | None = None,
    script_path: str | None = None,
    args: list[str] | None = None,
    cwd: str = ".",
    env: dict[str, str] | None = None,
    timeout_seconds: int | None = None,
    confirmation: str | None = None,
    max_output_bytes: int | None = None,
) -> dict[str, Any]:
    if (code is None) == (script_path is None):
        raise ValueError("Exactly one of code or script_path must be supplied")
    safe_args = [str(value) for value in (args or [])]
    if code is not None:
        if len(code.encode("utf-8")) > config.full_access.max_file_bytes:
            raise ValueError("Python code exceeds configured max_file_bytes")
        command = [sys.executable, "-c", code, *safe_args]
    else:
        assert script_path is not None
        resolved = resolve_repo_path(config.repo_root, script_path)
        if not resolved.is_file() or resolved.suffix.lower() != ".py":
            raise FileNotFoundError(f"Repository Python script not found: {script_path}")
        command = [sys.executable, resolved.as_posix(), *safe_args]
    result = run_command(
        config,
        command,
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds,
        confirmation=confirmation,
        max_output_bytes=max_output_bytes,
    )
    result["script_path"] = script_path
    result["execution_mode"] = "code" if code is not None else "script"
    return result


def run_shell_command(
    config: ServerConfig,
    command: str,
    cwd: str = ".",
    timeout_seconds: int | None = None,
    confirmation: str | None = None,
    max_output_bytes: int | None = None,
) -> dict[str, Any]:
    """Backward-compatible shell-string execution with the same confirmation gate."""
    _require_full_access(config, "shell", confirmation)
    if not isinstance(command, str) or not command.strip():
        raise ValueError("command must be a non-empty shell string")
    cwd_path, relative_cwd = _resolve_cwd(config, cwd)
    return _run_process(
        config,
        command,
        cwd=cwd_path,
        relative_cwd=relative_cwd,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        shell=True,
    )


def _run(
    config: ServerConfig,
    args: list[str],
    timeout_seconds: int | None = None,
    max_output_bytes: int | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    effective_cwd = cwd or config.repo_root
    relative_cwd = "." if effective_cwd == config.repo_root else to_repo_relative(config.repo_root, effective_cwd)
    return _run_process(
        config,
        _validate_arguments(args),
        cwd=effective_cwd,
        relative_cwd=relative_cwd,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )


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
        [sys.executable, "-m", "src.experiments.runner", rel],
        timeout_seconds=timeout_seconds,
    )
    after = _recent_run_dirs(config)
    return {
        **result,
        "config_path": rel,
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
