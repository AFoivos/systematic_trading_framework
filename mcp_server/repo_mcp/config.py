from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


DEFAULT_MAX_READ_BYTES = 1_000_000
DEFAULT_MAX_SEARCH_RESULTS = 200
DEFAULT_MAX_TREE_ENTRIES = 5_000
DEFAULT_SCRIPT_TIMEOUT_SECONDS = 120
DEFAULT_FULL_ACCESS_CONFIRMATION = "RUN_FULL_ACCESS_REPOSITORY_ACTION"
DEFAULT_FULL_ACCESS_MAX_OUTPUT_BYTES = 200_000
DEFAULT_FULL_ACCESS_MAX_FILE_BYTES = 10_000_000
DEFAULT_FULL_ACCESS_TIMEOUT_SECONDS = 300
DEFAULT_FULL_ACCESS_MAX_TIMEOUT_SECONDS = 3_600
DEFAULT_IMPORT_ROOTS = (Path("/mnt/data"),)


@dataclass(frozen=True)
class FullAccessConfig:
    enabled: bool = False
    require_confirmation: bool = True
    confirmation_token: str = DEFAULT_FULL_ACCESS_CONFIRMATION
    max_output_bytes: int = DEFAULT_FULL_ACCESS_MAX_OUTPUT_BYTES
    max_file_bytes: int = DEFAULT_FULL_ACCESS_MAX_FILE_BYTES
    default_timeout_seconds: int = DEFAULT_FULL_ACCESS_TIMEOUT_SECONDS
    max_timeout_seconds: int = DEFAULT_FULL_ACCESS_MAX_TIMEOUT_SECONDS
    allowed_import_roots: tuple[Path, ...] = DEFAULT_IMPORT_ROOTS
    allow_shell: bool = False
    allow_write: bool = False
    allow_delete: bool = False
    allow_git_write: bool = False


@dataclass(frozen=True)
class ServerConfig:
    repo_root: Path
    host: str
    port: int
    max_read_bytes: int
    max_search_results: int
    max_tree_entries: int
    script_timeout_seconds: int
    approved_python_scripts: tuple[str, ...]
    full_access: FullAccessConfig = field(default_factory=FullAccessConfig)


def _read_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        payload = yaml.safe_load(fh) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"MCP config must be a mapping: {path}")
    return payload


def load_config() -> ServerConfig:
    config_path = Path(os.environ.get("MCP_CONFIG_PATH", "/app/mcp-config.yaml"))
    payload = _read_yaml_config(config_path)

    limits = payload.get("limits", {}) if isinstance(payload.get("limits", {}), dict) else {}
    scripts = payload.get("approved_python_scripts", [])
    if not isinstance(scripts, list) or not all(isinstance(item, str) for item in scripts):
        raise ValueError("approved_python_scripts must be a list of repository-relative paths")

    full_access_payload = payload.get("full_access", {})
    if not isinstance(full_access_payload, dict):
        full_access_payload = {}
    import_roots = full_access_payload.get(
        "allowed_import_roots",
        [path.as_posix() for path in DEFAULT_IMPORT_ROOTS],
    )
    if not isinstance(import_roots, list) or not all(isinstance(item, str) for item in import_roots):
        raise ValueError("full_access.allowed_import_roots must be a list of absolute paths")
    canonical_import_roots: list[Path] = []
    for item in import_roots:
        candidate = Path(item)
        if not candidate.is_absolute():
            raise ValueError("full_access.allowed_import_roots entries must be absolute paths")
        canonical_import_roots.append(candidate.resolve())

    return ServerConfig(
        repo_root=Path(os.environ.get("MCP_REPO_ROOT", "/workspace")).resolve(),
        host=os.environ.get("MCP_HOST", str(payload.get("host", "0.0.0.0"))),
        port=int(os.environ.get("MCP_PORT", str(payload.get("port", 8765)))),
        max_read_bytes=int(limits.get("max_read_bytes", DEFAULT_MAX_READ_BYTES)),
        max_search_results=int(limits.get("max_search_results", DEFAULT_MAX_SEARCH_RESULTS)),
        max_tree_entries=int(limits.get("max_tree_entries", DEFAULT_MAX_TREE_ENTRIES)),
        script_timeout_seconds=int(
            limits.get("script_timeout_seconds", DEFAULT_SCRIPT_TIMEOUT_SECONDS)
        ),
        approved_python_scripts=tuple(scripts),
        full_access=FullAccessConfig(
            enabled=bool(full_access_payload.get("enabled", False)),
            require_confirmation=bool(full_access_payload.get("require_confirmation", True)),
            confirmation_token=str(
                full_access_payload.get(
                    "confirmation_token",
                    DEFAULT_FULL_ACCESS_CONFIRMATION,
                )
            ),
            max_output_bytes=int(
                full_access_payload.get(
                    "max_output_bytes",
                    DEFAULT_FULL_ACCESS_MAX_OUTPUT_BYTES,
                )
            ),
            max_file_bytes=int(
                full_access_payload.get(
                    "max_file_bytes",
                    DEFAULT_FULL_ACCESS_MAX_FILE_BYTES,
                )
            ),
            default_timeout_seconds=int(
                full_access_payload.get(
                    "default_timeout_seconds",
                    DEFAULT_FULL_ACCESS_TIMEOUT_SECONDS,
                )
            ),
            max_timeout_seconds=int(
                full_access_payload.get(
                    "max_timeout_seconds",
                    DEFAULT_FULL_ACCESS_MAX_TIMEOUT_SECONDS,
                )
            ),
            allowed_import_roots=tuple(canonical_import_roots),
            allow_shell=bool(full_access_payload.get("allow_shell", False)),
            allow_write=bool(full_access_payload.get("allow_write", False)),
            allow_delete=bool(full_access_payload.get("allow_delete", False)),
            allow_git_write=bool(full_access_payload.get("allow_git_write", False)),
        ),
    )
