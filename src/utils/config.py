from __future__ import annotations

from pathlib import Path
from typing import Any

from src.intraday import default_normalize_daily
from src.utils.config_defaults import apply_top_level_defaults
from src.utils.config_loader import (
    ConfigPathError,
    inject_api_key_from_env,
    load_resolved_config,
    resolve_config_path,
)
from src.utils.config_schemas import ResolvedExperimentConfig
from src.utils.config_validation import ConfigValidationError, validate_resolved_config


class ConfigError(ValueError):
    """Raised for invalid or inconsistent experiment configs."""


def _default_normalize_daily_for_interval(interval: str) -> bool:
    """
    Backward-compatible façade for the intraday-aware normalization default.
    """
    return default_normalize_daily(interval)


def _resolve_config_path(config_path: str | Path) -> Path:
    """
    Backward-compatible façade for config path resolution.
    """
    try:
        return resolve_config_path(config_path)
    except (FileNotFoundError, ConfigPathError, ValueError) as exc:
        raise ConfigError(str(exc)) from exc


def load_experiment_config_typed(config_path: str | Path) -> ResolvedExperimentConfig:
    """
    Load an experiment YAML into a typed resolved config object.
    """
    path = _resolve_config_path(config_path)
    try:
        cfg = load_resolved_config(path)
        cfg = apply_top_level_defaults(cfg, config_path=path)
        inject_api_key_from_env(cfg["data"])
        cfg = validate_resolved_config(cfg)
        return ResolvedExperimentConfig.from_dict(cfg)
    except (ConfigValidationError, TypeError, ValueError) as exc:
        raise ConfigError(str(exc)) from exc


def load_experiment_config(config_path: str | Path) -> dict[str, Any]:
    """
    Load a self-contained experiment YAML, apply defaults and validation,
    and resolve logging paths. Returns a plain dict ready for use.
    """
    return load_experiment_config_typed(config_path).to_dict()


__all__ = [
    "ConfigError",
    "ResolvedExperimentConfig",
    "_default_normalize_daily_for_interval",
    "_resolve_config_path",
    "load_experiment_config",
    "load_experiment_config_typed",
]
