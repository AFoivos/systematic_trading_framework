from __future__ import annotations

"""Shared, conservative policy for normal source-code inspection."""

import fnmatch
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


DEFAULT_SOURCE_ROOTS = ("src", "tests", "config", "scripts", "docs")
DEFAULT_SOURCE_GLOBS = (
    "*.py",
    "*.yaml",
    "*.yml",
    "*.json",
    "*.toml",
    "*.md",
    "*.txt",
    "*.ini",
    "*.cfg",
)

# These are generated/heavy *repository roots*, not package names.  In
# particular, src/models and tests/models are valid source locations.
TOP_LEVEL_EXCLUDED_ROOTS = frozenset({"data", "logs", "reports", "artifacts", "tmp", "models"})

# These names are unsafe or unhelpful wherever they occur in a source walk.
GLOBAL_EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "htmlcov",
        "dist",
        "build",
        "site-packages",
        ".ipynb_checkpoints",
    }
)
VIRTUALENV_DIRECTORY_PATTERNS = (".venv", ".venv*", "venv", "venv*", "env")
DEFAULT_EXCLUDED_SUFFIXES = frozenset(
    {
        ".csv",
        ".parquet",
        ".feather",
        ".pkl",
        ".pickle",
        ".joblib",
        ".sqlite",
        ".sqlite3",
        ".db",
        ".npy",
        ".npz",
        ".pt",
        ".pth",
        ".onnx",
        ".h5",
        ".hdf5",
        ".zip",
        ".tar",
        ".gz",
        ".7z",
        ".log",
    }
)
SENSITIVE_FILE_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "credentials.json",
    "secrets.json",
    "id_rsa",
    "id_ed25519",
)


def as_posix_relative(value: str | Path) -> str:
    """Normalise a repository-relative path without making it platform-specific."""
    normalized = str(value).replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.rstrip("/")


def _matches(path: str, patterns: Iterable[str]) -> bool:
    pure = PurePosixPath(path)
    return any(pure.match(pattern) or fnmatch.fnmatch(pure.name, pattern) for pattern in patterns)


def _is_global_excluded_name(name: str) -> bool:
    return (
        name in GLOBAL_EXCLUDED_DIRECTORY_NAMES
        or "pycache" in name
        or any(fnmatch.fnmatch(name, pattern) for pattern in VIRTUALENV_DIRECTORY_PATTERNS)
    )


@dataclass(frozen=True)
class RepositoryScanPolicy:
    """Decides what a generic source-inspection operation may traverse.

    Direct artifact/log/database tools deliberately do not use this policy. A
    caller explicitly naming a top-level generated root may opt into that root,
    while global environments/caches remain excluded everywhere.
    """

    exclude_globs: tuple[str, ...] = ()
    include_globs: tuple[str, ...] = ()
    allow_explicit_top_level_root: bool = False

    def is_sensitive(self, relative_path: str | Path) -> bool:
        return _matches(as_posix_relative(relative_path), SENSITIVE_FILE_PATTERNS)

    def should_skip_directory(self, relative_path: str | Path, *, is_root: bool = False) -> bool:
        relative = as_posix_relative(relative_path)
        if not relative or _matches(relative, self.exclude_globs):
            return bool(relative)
        parts = PurePosixPath(relative).parts
        if not parts:
            return False
        if parts[0] in TOP_LEVEL_EXCLUDED_ROOTS and not self.allow_explicit_top_level_root:
            return True
        return any(_is_global_excluded_name(part) for part in parts)

    def should_skip_file(self, relative_path: str | Path, *, allow_included_type: bool = False) -> bool:
        relative = as_posix_relative(relative_path)
        if _matches(relative, self.exclude_globs) or self.is_sensitive(relative):
            return True
        pure = PurePosixPath(relative)
        if pure.name == ".coverage":
            return True
        parts = pure.parts
        if parts and parts[0] in TOP_LEVEL_EXCLUDED_ROOTS and not self.allow_explicit_top_level_root:
            return True
        if any(_is_global_excluded_name(part) for part in parts[:-1]):
            return True
        return pure.suffix.lower() in DEFAULT_EXCLUDED_SUFFIXES and not allow_included_type

    def matches_include(self, relative_path: str | Path, include_globs: Iterable[str] | None = None) -> bool:
        patterns = tuple(include_globs or self.include_globs)
        return not patterns or _matches(as_posix_relative(relative_path), patterns)


def classify_source_path(relative_path: str) -> str:
    path = PurePosixPath(as_posix_relative(relative_path))
    first = path.parts[0].lower() if path.parts else ""
    if first in {"test", "tests"} or path.name.startswith("test_") or path.name.endswith("_test.py"):
        return "test"
    if first in {"config", "configs"} or path.suffix.lower() in {".yaml", ".yml", ".toml", ".ini", ".cfg"}:
        return "config"
    if first in {"script", "scripts", "tools"}:
        return "script"
    if first in {"doc", "docs", "documentation"} or path.suffix.lower() in {".md", ".rst"}:
        return "documentation"
    if first in {"src", "app", "apps", "lib", "package", "packages"} or path.suffix.lower() in {".py", ".pyi"}:
        return "source"
    return "other"
