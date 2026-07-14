from __future__ import annotations

import mimetypes
import fnmatch
from pathlib import Path, PureWindowsPath


TEXT_EXTENSIONS = {
    ".cfg",
    ".conf",
    ".csv",
    ".dockerfile",
    ".env",
    ".gitignore",
    ".ini",
    ".ipynb",
    ".json",
    ".jsonl",
    ".log",
    ".md",
    ".py",
    ".sql",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


class PathSecurityError(ValueError):
    """Raised when a requested repository path escapes the configured root."""


PROTECTED_WRITE_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_ed25519",
)


def normalize_repo_path(path: str | None) -> str:
    raw = "." if path in (None, "") else str(path)
    normalized = raw.replace("\\", "/")
    windows_path = PureWindowsPath(raw)
    if normalized.startswith("/") or windows_path.is_absolute() or windows_path.drive:
        raise PathSecurityError("Absolute paths are not allowed; use repository-relative paths")
    return normalized


def resolve_repo_path(repo_root: Path, path: str | None) -> Path:
    relative = normalize_repo_path(path)
    candidate = (repo_root / relative).resolve()
    if candidate != repo_root and repo_root not in candidate.parents:
        raise PathSecurityError(f"Path escapes repository root: {path}")
    return candidate


def to_repo_relative(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root).as_posix()


def is_protected_secret_path(repo_relative_path: str) -> bool:
    name = Path(repo_relative_path).name
    return any(fnmatch.fnmatch(name, pattern) for pattern in PROTECTED_WRITE_PATTERNS)


def reject_protected_write_path(repo_relative_path: str) -> None:
    if is_protected_secret_path(repo_relative_path):
        raise PermissionError(f"Refusing to write or delete protected secret-like path: {repo_relative_path}")


def is_probably_text(path: Path, sample_size: int = 4096) -> bool:
    try:
        with path.open("rb") as fh:
            sample = fh.read(sample_size)
    except OSError:
        return False
    if b"\x00" in sample:
        return False
    if sample:
        controls = sum(byte < 9 or 13 < byte < 32 for byte in sample)
        if controls / len(sample) > 0.20:
            return False
        try:
            sample.decode("utf-8")
            return True
        except UnicodeDecodeError:
            pass
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    mime, _ = mimetypes.guess_type(path.name)
    return bool(mime and mime.startswith("text/"))


def read_text_limited(path: Path, max_bytes: int) -> tuple[str, bool]:
    if max_bytes < 0:
        raise ValueError("max_bytes must be non-negative")
    try:
        with path.open("rb") as fh:
            payload = fh.read(max_bytes)
            truncated = bool(fh.read(1))
    except OSError:
        raise
    return payload.decode("utf-8", errors="replace"), truncated
