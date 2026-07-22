from __future__ import annotations

import difflib
import hashlib
import os
import re
import shlex
import shutil
import stat
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

from .config import ServerConfig
from .runtime import get_runtime
from .scan_policy import DEFAULT_SOURCE_ROOTS, as_posix_relative
from .security import (
    PathSecurityError,
    reject_protected_write_path,
    resolve_repo_path,
    to_repo_relative,
)


_WRITE_LOCK = threading.RLock()
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class ConcurrentWriteError(RuntimeError):
    def __init__(self, actual_sha256: str | None) -> None:
        super().__init__("Destination changed while the atomic replacement was being prepared")
        self.actual_sha256 = actual_sha256


def _require_capability(config: ServerConfig, capability: str) -> None:
    full = config.full_access
    allowed = {
        "write": full.allow_write,
        "delete": full.allow_delete,
    }.get(capability, False)
    if not full.enabled or not allowed:
        raise PermissionError(f"Full-access {capability} operations are disabled in MCP config")


def _require_confirmation(config: ServerConfig, capability: str, confirmation: str | None) -> None:
    if config.full_access.require_confirmation and not (confirmation or "").strip():
        raise PermissionError(
            f"{capability} requires a non-empty confirmation describing the user's explicit request"
        )


def _reject_git_metadata(repo_relative_path: str) -> None:
    if repo_relative_path == ".git" or repo_relative_path.startswith(".git/"):
        raise PermissionError("Refusing to modify .git through repository file tools")


def _resolve_mutable_path(config: ServerConfig, path: str) -> tuple[Path, str]:
    resolved = resolve_repo_path(config.repo_root, path)
    rel = to_repo_relative(config.repo_root, resolved)
    _reject_git_metadata(rel)
    reject_protected_write_path(rel)
    return resolved, rel


def _file_limit(config: ServerConfig) -> int:
    return max(1, int(config.full_access.max_file_bytes))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validate_expected_sha256(expected_sha256: str | None) -> str | None:
    if expected_sha256 is None:
        return None
    if not _SHA256_RE.fullmatch(expected_sha256):
        raise ValueError("expected_sha256 must be a 64-character hexadecimal SHA-256 digest")
    return expected_sha256.lower()


def _base_response(
    *,
    success: bool,
    changed_files: list[str] | None = None,
    created_files: list[str] | None = None,
    deleted_files: list[str] | None = None,
    warnings: list[str] | None = None,
    diff_stat: str = "",
    error: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "success": success,
        "ok": success,
        "changed_files": changed_files or [],
        "created_files": created_files or [],
        "deleted_files": deleted_files or [],
        "warnings": warnings or [],
        "diff_stat": diff_stat,
        "error": error,
    }


def _error_response(code: str, message: str, **fields: Any) -> dict[str, Any]:
    return {
        **_base_response(success=False, error={"code": code, "message": message}),
        **fields,
    }


def _atomic_write_bytes(
    target: Path,
    payload: bytes,
    mode: int | None = None,
    guard_sha256: str | None = None,
) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temporary, stat.S_IMODE(mode))
        if guard_sha256 is not None:
            actual_sha256 = _sha256_file(target) if target.is_file() else None
            if actual_sha256 != guard_sha256:
                raise ConcurrentWriteError(actual_sha256)
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _text_diff_stat(path: str, previous: bytes, current: bytes) -> str:
    before = previous.decode("utf-8", errors="replace").splitlines()
    after = current.decode("utf-8", errors="replace").splitlines()
    additions = 0
    deletions = 0
    for line in difflib.ndiff(before, after):
        if line.startswith("+ "):
            additions += 1
        elif line.startswith("- "):
            deletions += 1
    return f"{path} | +{additions} -{deletions}"


def _invalidate_source_index(config: ServerConfig, *paths: str) -> None:
    source_roots = set(DEFAULT_SOURCE_ROOTS)
    if any((as_posix_relative(path).split("/", 1)[0] in source_roots) for path in paths):
        get_runtime(config.repo_root).source_index.invalidate()


def write_file(
    config: ServerConfig,
    path: str,
    content: str,
    create_parent_dirs: bool = True,
    expected_sha256: str | None = None,
    *,
    create_dirs: bool | None = None,
    overwrite: bool = True,
    confirmation: str | None = None,
) -> dict[str, Any]:
    """Atomically create or replace one UTF-8 repository text file.

    ``create_dirs`` and ``confirmation`` remain accepted for compatibility with
    older MCP clients. Ordinary source edits do not require a confirmation
    token; deletion and command execution do.
    """
    del confirmation
    _require_capability(config, "write")
    if not isinstance(content, str):
        raise TypeError("content must be a UTF-8 text string")
    if create_dirs is not None:
        create_parent_dirs = create_dirs
    expected = _validate_expected_sha256(expected_sha256)
    payload = content.encode("utf-8")
    if len(payload) > _file_limit(config):
        raise ValueError(
            f"File content exceeds configured max_file_bytes={_file_limit(config)}"
        )

    with _WRITE_LOCK:
        target, rel = _resolve_mutable_path(config, path)
        existed = target.exists()
        if existed and not target.is_file():
            raise IsADirectoryError(path)
        if existed and not overwrite:
            return _error_response(
                "destination_exists",
                f"File already exists: {rel}",
                path=rel,
                action=None,
                previous_sha256=_sha256_file(target),
                new_sha256=None,
                bytes_written=0,
            )
        previous = target.read_bytes() if existed else b""
        previous_sha256 = _sha256_bytes(previous) if existed else None
        if expected is not None and previous_sha256 != expected:
            return _error_response(
                "sha256_mismatch",
                f"Refusing to overwrite {rel}: expected SHA-256 {expected}, found {previous_sha256}",
                path=rel,
                action=None,
                previous_sha256=previous_sha256,
                new_sha256=None,
                bytes_written=0,
            )
        if create_parent_dirs:
            target.parent.mkdir(parents=True, exist_ok=True)
        elif not target.parent.is_dir():
            raise FileNotFoundError(target.parent.as_posix())
        # Re-resolve after creating parents so a symlink introduced during the
        # operation cannot redirect the destination outside the repository.
        target, rel = _resolve_mutable_path(config, path)
        mode = target.stat().st_mode if target.is_file() else None
        try:
            _atomic_write_bytes(target, payload, mode, guard_sha256=expected)
        except ConcurrentWriteError as exc:
            return _error_response(
                "sha256_mismatch",
                f"Refusing to overwrite {rel}: the destination changed during the write",
                path=rel,
                action=None,
                previous_sha256=exc.actual_sha256,
                new_sha256=None,
                bytes_written=0,
            )

    new_sha256 = _sha256_bytes(payload)
    _invalidate_source_index(config, rel)
    created = [] if existed else [rel]
    changed = [rel] if existed else []
    return {
        **_base_response(
            success=True,
            changed_files=changed,
            created_files=created,
            diff_stat=_text_diff_stat(rel, previous, payload),
        ),
        "path": rel,
        "action": "updated" if existed else "created",
        "previous_sha256": previous_sha256,
        "new_sha256": new_sha256,
        "bytes_written": len(payload),
        "existed": existed,
    }


def append_file(
    config: ServerConfig,
    path: str,
    content: str,
    create_dirs: bool = True,
    confirmation: str | None = None,
) -> dict[str, Any]:
    """Backward-compatible atomic append implemented as a guarded rewrite."""
    del confirmation
    _require_capability(config, "write")
    target, _ = _resolve_mutable_path(config, path)
    if target.exists() and not target.is_file():
        raise IsADirectoryError(path)
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    return write_file(
        config,
        path,
        existing + content,
        create_parent_dirs=create_dirs,
    )


def create_directory(config: ServerConfig, path: str) -> dict[str, Any]:
    _require_capability(config, "write")
    with _WRITE_LOCK:
        target, rel = _resolve_mutable_path(config, path)
        existed = target.exists()
        if existed and not target.is_dir():
            raise FileExistsError(f"A non-directory path already exists: {rel}")
        target.mkdir(parents=True, exist_ok=True)
        target, rel = _resolve_mutable_path(config, path)
    return {
        **_base_response(success=True),
        "path": rel,
        "created": not existed,
        "created_directories": [rel] if not existed else [],
    }


def _patch_header_path(value: str, *, strip_git_prefix: bool = True) -> str:
    value = value.strip()
    if value == "/dev/null":
        return value
    if value.startswith(('"', "'")):
        parsed = shlex.split(value)
        if not parsed:
            raise ValueError("Malformed quoted patch path")
        value = parsed[0]
    else:
        value = value.split("\t", 1)[0]
    return re.sub(r"^[ab]/", "", value) if strip_git_prefix else value


def _patch_changes(patch: str) -> dict[str, list[str]]:
    changed: list[str] = []
    created: list[str] = []
    deleted: list[str] = []
    validation_paths: list[str] = []
    lines = patch.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("--- ") and index + 1 < len(lines) and lines[index + 1].startswith("+++ "):
            old = _patch_header_path(line[4:])
            new = _patch_header_path(lines[index + 1][4:])
            validation_paths.extend(path for path in (old, new) if path != "/dev/null")
            if old == "/dev/null" and new != "/dev/null":
                created.append(new)
            elif new == "/dev/null" and old != "/dev/null":
                deleted.append(old)
            elif old != new:
                deleted.append(old)
                created.append(new)
            elif new != "/dev/null":
                changed.append(new)
            index += 2
            continue
        if line.startswith("diff --git "):
            try:
                fields = shlex.split(line)
            except ValueError as exc:
                raise ValueError(f"Malformed diff --git header: {line}") from exc
            if len(fields) >= 4:
                validation_paths.extend(_patch_header_path(value) for value in fields[2:4])
        if line.startswith("rename from "):
            old = _patch_header_path(line[len("rename from ") :], strip_git_prefix=False)
            deleted.append(old)
            validation_paths.append(old)
        if line.startswith("rename to "):
            new = _patch_header_path(line[len("rename to ") :], strip_git_prefix=False)
            created.append(new)
            validation_paths.append(new)
        if line.startswith("copy from "):
            validation_paths.append(
                _patch_header_path(line[len("copy from ") :], strip_git_prefix=False)
            )
        if line.startswith("copy to "):
            new = _patch_header_path(line[len("copy to ") :], strip_git_prefix=False)
            created.append(new)
            validation_paths.append(new)
        index += 1

    def unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    return {
        "changed": unique(changed),
        "created": unique(created),
        "deleted": unique(deleted),
        "validation": unique(validation_paths),
    }


def _validate_patch_paths(config: ServerConfig, changes: dict[str, list[str]]) -> None:
    paths = changes["validation"]
    if not paths:
        raise ValueError("Patch does not contain any standard unified-diff file headers")
    for path in paths:
        resolved = resolve_repo_path(config.repo_root, path)
        rel = to_repo_relative(config.repo_root, resolved)
        _reject_git_metadata(rel)
        reject_protected_write_path(rel)


def _timeout(config: ServerConfig, timeout_seconds: int | None) -> int:
    requested = timeout_seconds or config.full_access.default_timeout_seconds
    return max(1, min(int(requested), config.full_access.max_timeout_seconds))


def _run_git_apply(
    config: ServerConfig,
    args: list[str],
    patch: str,
    timeout_seconds: int | None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "apply", *args],
        cwd=config.repo_root,
        input=patch,
        check=False,
        capture_output=True,
        text=True,
        timeout=_timeout(config, timeout_seconds),
    )


def _bounded_text(value: str, limit: int) -> tuple[str, bool]:
    encoded = value.encode("utf-8")
    if len(encoded) <= limit:
        return value, False
    return encoded[-limit:].decode("utf-8", errors="replace"), True


def _rejected_hunks(stderr: str) -> list[str]:
    return [
        line
        for line in stderr.splitlines()
        if "patch failed" in line.lower()
        or "does not apply" in line.lower()
        or line.lower().startswith("error:")
    ]


def apply_patch(
    config: ServerConfig,
    patch: str,
    check_only: bool = False,
    *,
    confirmation: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    """Validate and atomically apply a standard unified diff with ``git apply``."""
    _require_capability(config, "write")
    if not isinstance(patch, str) or not patch.strip():
        raise ValueError("patch must be non-empty unified diff text")
    if len(patch.encode("utf-8")) > _file_limit(config):
        raise ValueError(f"Patch exceeds configured max_file_bytes={_file_limit(config)}")
    changes = _patch_changes(patch)
    _validate_patch_paths(config, changes)
    if changes["deleted"]:
        _require_confirmation(config, "Patch deletion", confirmation)

    limit = max(1, config.full_access.max_output_bytes)
    with _WRITE_LOCK:
        stat_result = _run_git_apply(config, ["--stat"], patch, timeout_seconds)
        diff_stat, stat_truncated = _bounded_text(stat_result.stdout, limit)
        check = _run_git_apply(config, ["--check"], patch, timeout_seconds)
        check_stdout, stdout_truncated = _bounded_text(check.stdout, limit)
        check_stderr, stderr_truncated = _bounded_text(check.stderr, limit)
        if check.returncode != 0:
            return {
                **_base_response(
                    success=False,
                    warnings=["git apply --stat output was truncated"] if stat_truncated else [],
                    diff_stat=diff_stat,
                    error={"code": "patch_check_failed", "message": check_stderr.strip() or "Patch check failed"},
                ),
                "check_only": check_only,
                "return_code": check.returncode,
                "stdout": check_stdout,
                "stderr": check_stderr,
                "truncated": stdout_truncated or stderr_truncated or stat_truncated,
                "rejected_hunks": _rejected_hunks(check_stderr),
                "planned_changed_files": changes["changed"],
                "planned_created_files": changes["created"],
                "planned_deleted_files": changes["deleted"],
            }
        if check_only:
            return {
                **_base_response(
                    success=True,
                    changed_files=changes["changed"],
                    created_files=changes["created"],
                    deleted_files=changes["deleted"],
                    warnings=["git apply --stat output was truncated"] if stat_truncated else [],
                    diff_stat=diff_stat,
                ),
                "check_only": True,
                "return_code": 0,
                "stdout": check_stdout,
                "stderr": check_stderr,
                "truncated": stdout_truncated or stderr_truncated or stat_truncated,
                "rejected_hunks": [],
            }
        applied = _run_git_apply(config, [], patch, timeout_seconds)
        stdout, stdout_truncated = _bounded_text(applied.stdout, limit)
        stderr, stderr_truncated = _bounded_text(applied.stderr, limit)

    success = applied.returncode == 0
    if success:
        _invalidate_source_index(
            config,
            *(changes["changed"] + changes["created"] + changes["deleted"]),
        )
    return {
        **_base_response(
            success=success,
            changed_files=changes["changed"] if success else [],
            created_files=changes["created"] if success else [],
            deleted_files=changes["deleted"] if success else [],
            warnings=["git apply --stat output was truncated"] if stat_truncated else [],
            diff_stat=diff_stat,
            error=None
            if success
            else {"code": "patch_apply_failed", "message": stderr.strip() or "Patch application failed"},
        ),
        "check_only": False,
        "return_code": applied.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "truncated": stdout_truncated or stderr_truncated or stat_truncated,
        "rejected_hunks": _rejected_hunks(stderr),
    }


def delete_path(
    config: ServerConfig,
    path: str,
    recursive: bool = False,
    confirmation: str | None = None,
) -> dict[str, Any]:
    _require_capability(config, "delete")
    _require_confirmation(config, "Deletion", confirmation)
    with _WRITE_LOCK:
        target = resolve_repo_path(config.repo_root, path)
        if target == config.repo_root:
            raise PermissionError("Refusing to delete repository root")
        rel = to_repo_relative(config.repo_root, target)
        _reject_git_metadata(rel)
        reject_protected_write_path(rel)
        if not target.exists():
            return _error_response(
                "path_not_found",
                f"Path does not exist: {rel}",
                path=rel,
                deleted=False,
            )
        if target.is_dir():
            if not recursive:
                raise IsADirectoryError("Directory deletion requires recursive=True")
            deleted_paths = [rel]
            shutil.rmtree(target)
        else:
            deleted_paths = [rel]
            target.unlink()
    _invalidate_source_index(config, rel)
    return {
        **_base_response(success=True, deleted_files=deleted_paths, diff_stat=f"deleted {rel}"),
        "path": rel,
        "deleted": True,
        "recursive": recursive,
        "deleted_paths": deleted_paths,
    }


def move_path(
    config: ServerConfig,
    source: str | None = None,
    destination: str | None = None,
    overwrite: bool = False,
    *,
    confirmation: str | None = None,
    src: str | None = None,
    dst: str | None = None,
) -> dict[str, Any]:
    _require_capability(config, "write")
    # ``src``/``dst`` remain accepted for older generated MCP clients.
    source = src if src is not None else source
    destination = dst if dst is not None else destination
    if source is None or destination is None:
        raise ValueError("Both source and destination are required")
    with _WRITE_LOCK:
        source_path = resolve_repo_path(config.repo_root, source)
        if not source_path.exists():
            raise FileNotFoundError(source)
        source_rel = to_repo_relative(config.repo_root, source_path)
        _reject_git_metadata(source_rel)
        reject_protected_write_path(source_rel)
        destination_path, destination_rel = _resolve_mutable_path(config, destination)
        destination_existed = destination_path.exists()
        if destination_existed and not overwrite:
            return _error_response(
                "destination_exists",
                f"Destination already exists: {destination_rel}",
                source=source_rel,
                destination=destination_rel,
            )
        if destination_existed:
            _require_confirmation(config, "Move with overwrite", confirmation)
            if destination_path.is_dir():
                shutil.rmtree(destination_path)
            else:
                destination_path.unlink()
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(destination_path))
    _invalidate_source_index(config, source_rel, destination_rel)
    return {
        **_base_response(
            success=True,
            changed_files=[destination_rel],
            deleted_files=[source_rel],
            diff_stat=f"{source_rel} -> {destination_rel}",
        ),
        "source": source_rel,
        "destination": destination_rel,
        "src": source_rel,
        "dst": destination_rel,
        "overwrote": destination_existed,
    }


def _allowed_import_source(config: ServerConfig, source_path: str) -> tuple[Path, Path]:
    requested = Path(source_path)
    if not requested.is_absolute():
        raise PathSecurityError("Import source_path must be an absolute path in an allowed upload root")
    try:
        resolved = requested.resolve(strict=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Import source does not exist: {source_path}") from exc
    allowed_root = next(
        (
            root.resolve()
            for root in config.full_access.allowed_import_roots
            if resolved == root.resolve() or root.resolve() in resolved.parents
        ),
        None,
    )
    if allowed_root is None:
        roots = ", ".join(path.as_posix() for path in config.full_access.allowed_import_roots)
        raise PathSecurityError(
            f"Import source escapes configured upload roots ({roots}): {source_path}"
        )
    mode = resolved.stat().st_mode
    if not stat.S_ISREG(mode):
        raise PathSecurityError("Import source must resolve to a regular file; directories and device files are rejected")
    return resolved, allowed_root


def import_local_file(
    config: ServerConfig,
    source_path: str,
    destination_path: str,
    overwrite: bool = False,
    *,
    create_parent_dirs: bool = True,
    confirmation: str | None = None,
) -> dict[str, Any]:
    _require_capability(config, "write")
    source, allowed_root = _allowed_import_source(config, source_path)
    source_stat = source.stat()
    if source_stat.st_size > _file_limit(config):
        raise ValueError(
            f"Import source exceeds configured max_file_bytes={_file_limit(config)}"
        )

    with _WRITE_LOCK:
        destination, rel = _resolve_mutable_path(config, destination_path)
        existed = destination.exists()
        if existed and not destination.is_file():
            raise IsADirectoryError(destination_path)
        if existed and not overwrite:
            return _error_response(
                "destination_exists",
                f"Destination already exists: {rel}",
                source_path=source_path,
                destination_path=rel,
            )
        if existed:
            _require_confirmation(config, "Import with overwrite", confirmation)
        if create_parent_dirs:
            destination.parent.mkdir(parents=True, exist_ok=True)
        elif not destination.parent.is_dir():
            raise FileNotFoundError(destination.parent.as_posix())
        destination, rel = _resolve_mutable_path(config, destination_path)
        previous_sha256 = _sha256_file(destination) if existed else None
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        temporary = Path(temporary_name)
        digest = hashlib.sha256()
        bytes_written = 0
        try:
            with source.open("rb") as source_handle, os.fdopen(descriptor, "wb") as target_handle:
                while chunk := source_handle.read(1024 * 1024):
                    target_handle.write(chunk)
                    digest.update(chunk)
                    bytes_written += len(chunk)
                target_handle.flush()
                os.fsync(target_handle.fileno())
            final_source_stat = source.stat()
            if (
                final_source_stat.st_size != source_stat.st_size
                or final_source_stat.st_mtime_ns != source_stat.st_mtime_ns
            ):
                raise RuntimeError("Import source changed while it was being copied")
            os.replace(temporary, destination)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    new_sha256 = digest.hexdigest()
    _invalidate_source_index(config, rel)
    return {
        **_base_response(
            success=True,
            changed_files=[rel] if existed else [],
            created_files=[] if existed else [rel],
            diff_stat=f"{rel} | {bytes_written} bytes imported",
        ),
        "source_path": source_path,
        "resolved_source_path": source.as_posix(),
        "allowed_source_root": allowed_root.as_posix(),
        "destination_path": rel,
        "action": "updated" if existed else "created",
        "previous_sha256": previous_sha256,
        "source_sha256": new_sha256,
        "destination_sha256": _sha256_file(destination),
        "bytes_written": bytes_written,
    }
