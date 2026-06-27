from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


DEFAULT_MAX_READ_BYTES = 1_000_000
DEFAULT_MAX_SEARCH_RESULTS = 200
DEFAULT_MAX_TREE_ENTRIES = 5_000
DEFAULT_SCRIPT_TIMEOUT_SECONDS = 120


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
    )
