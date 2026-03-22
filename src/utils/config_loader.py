from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from src.utils.paths import CONFIG_DIR, PROJECT_ROOT


class ConfigPathError(ValueError):
    """Raised when a config path cannot be resolved safely."""


def resolve_config_path(config_path: str | Path) -> Path:
    """
    Resolve a config path relative to the project config directory and enforce safe access.
    """
    path = Path(config_path)
    if not path.is_absolute():
        candidate = (PROJECT_ROOT / path).resolve()
        if candidate.exists():
            path = candidate
        else:
            path = (CONFIG_DIR / path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    if not path.is_file():
        raise ConfigPathError(f"Config path is not a file: {path}")
    from src.utils.paths import enforce_safe_absolute_path

    return enforce_safe_absolute_path(path)


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    """
    Load a YAML file and require a top-level mapping.
    """
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ConfigPathError(f"Config at {path} must be a mapping at top level.")
    return data


def load_resolved_config(path: Path) -> dict[str, Any]:
    """
    Load a self-contained experiment config and reject legacy inheritance.
    """
    cfg = load_yaml_mapping(path)
    if "extends" in cfg:
        raise ConfigPathError(
            "Config inheritance via 'extends' is no longer supported. "
            "Each experiment YAML must be fully self-contained."
        )
    cfg["config_path"] = str(path)
    return cfg


def inject_api_key_from_env(data: dict[str, Any]) -> None:
    """
    Hydrate provider credentials from environment variables when the config references them.
    """
    env_name = data.get("api_key_env")
    if env_name and not data.get("api_key"):
        data["api_key"] = os.getenv(env_name)


__all__ = [
    "ConfigPathError",
    "inject_api_key_from_env",
    "load_resolved_config",
    "load_yaml_mapping",
    "resolve_config_path",
]
