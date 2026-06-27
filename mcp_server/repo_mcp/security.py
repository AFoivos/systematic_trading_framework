from __future__ import annotations

import mimetypes
from pathlib import Path


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


def normalize_repo_path(path: str | None) -> str:
    raw = "." if path in (None, "") else str(path)
    normalized = raw.replace("\\", "/")
    if normalized.startswith("/"):
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


def is_probably_text(path: Path, sample_size: int = 4096) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    mime, _ = mimetypes.guess_type(path.name)
    if mime and mime.startswith("text/"):
        return True
    try:
        sample = path.read_bytes()[:sample_size]
    except OSError:
        return False
    return b"\x00" not in sample


def read_text_limited(path: Path, max_bytes: int) -> tuple[str, bool]:
    payload = path.read_bytes()
    truncated = len(payload) > max_bytes
    payload = payload[:max_bytes]
    return payload.decode("utf-8", errors="replace"), truncated
