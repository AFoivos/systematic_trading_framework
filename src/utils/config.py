from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.utils.paths import CONFIG_DIR, PROJECT_ROOT, in_project
from src.utils.repro import RuntimeConfigError, validate_runtime_config


class ConfigError(ValueError):
    """Raised for invalid or inconsistent experiment configs."""


def _resolve_config_path(config_path: str | Path) -> Path:
    """Resolve a config path relative to CONFIG_DIR and verify it exists."""
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
        raise ConfigError(f"Config path is not a file: {path}")
    return path


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"Config at {path} must be a mapping at top level.")
    return data


def _deep_update(base: Mapping[str, Any], updates: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge mappings; lists and scalars are overwritten."""
    merged: dict[str, Any] = dict(base)
    for k, v in updates.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k] = _deep_update(merged[k], v)
        else:
            merged[k] = v
    return merged


def _load_with_extends(path: Path, seen: set[Path] | None = None) -> dict[str, Any]:
    seen = seen or set()
    if path in seen:
        raise ConfigError(f"Cyclic config inheritance detected at {path}")
    seen.add(path)

    cfg = _load_yaml(path)
    parent_ref = cfg.pop("extends", None)
    if parent_ref:
        parent_path = _resolve_config_path(parent_ref)
        parent_cfg = _load_with_extends(parent_path, seen)
        cfg = _deep_update(parent_cfg, cfg)

    cfg["config_path"] = str(path)
    return cfg


def _default_risk_block(risk: dict[str, Any]) -> dict[str, Any]:
    risk = dict(risk) if risk else {}
    risk.setdefault("cost_per_turnover", 0.0)
    risk.setdefault("slippage_per_turnover", 0.0)
    risk.setdefault("target_vol", None)
    risk.setdefault("max_leverage", 3.0)
    dd = risk.get("dd_guard") or {}
    if not isinstance(dd, dict):
        raise ConfigError("risk.dd_guard must be a mapping.")
    dd.setdefault("max_drawdown", 0.2)
    dd.setdefault("cooloff_bars", 20)
    risk["dd_guard"] = dd
    return risk


def _default_backtest_block(backtest: dict[str, Any]) -> dict[str, Any]:
    backtest = dict(backtest) if backtest else {}
    backtest.setdefault("periods_per_year", 252)
    backtest.setdefault("returns_type", "simple")
    return backtest


def _resolve_logging_block(logging_cfg: dict[str, Any], config_path: Path) -> dict[str, Any]:
    logging_cfg = dict(logging_cfg) if logging_cfg else {}
    logging_cfg.setdefault("run_name", Path(config_path).stem)
    out_dir = logging_cfg.get("output_dir", "logs/experiments")
    if isinstance(out_dir, str):
        logging_cfg["output_dir"] = str(in_project(out_dir))
    return logging_cfg


def _validate_data_block(data: dict[str, Any]) -> None:
    if "symbol" not in data or not isinstance(data["symbol"], str):
        raise ConfigError("data.symbol (str) is required.")
    source = data.get("source", "yahoo")
    if source not in {"yahoo", "alpha"}:
        raise ConfigError("data.source must be 'yahoo' or 'alpha'.")
    interval = data.get("interval", "1d")
    if not isinstance(interval, str):
        raise ConfigError("data.interval must be a string (e.g. '1d').")


def _inject_api_key_from_env(data: dict[str, Any]) -> None:
    env_name = data.get("api_key_env")
    if env_name and not data.get("api_key"):
        data["api_key"] = os.getenv(env_name)


def _validate_features_block(features: Any) -> None:
    if not isinstance(features, list):
        raise ConfigError("features must be a list of steps.")
    for step in features:
        if not isinstance(step, dict) or "step" not in step:
            raise ConfigError("Each feature entry must be a mapping with a 'step' key.")


def _validate_model_block(model: dict[str, Any]) -> None:
    if "kind" not in model:
        raise ConfigError("model.kind is required.")
    if not isinstance(model["kind"], str):
        raise ConfigError("model.kind must be a string.")

    split = model.get("split")
    if split is None:
        return
    if not isinstance(split, dict):
        raise ConfigError("model.split must be a mapping when provided.")

    method = split.get("method", "time")
    if method not in {"time", "walk_forward", "purged"}:
        raise ConfigError("model.split.method must be one of: time, walk_forward, purged.")

    if method == "time":
        train_frac = float(split.get("train_frac", 0.7))
        if not 0.0 < train_frac < 1.0:
            raise ConfigError("model.split.train_frac must be in (0,1) for method=time.")
        return

    train_size = split.get("train_size")
    train_frac = split.get("train_frac", 0.7 if train_size is None else None)
    if train_size is None and train_frac is None:
        raise ConfigError(
            "model.split for walk_forward/purged requires either train_size or train_frac."
        )
    if train_size is not None and (not isinstance(train_size, int) or train_size <= 0):
        raise ConfigError("model.split.train_size must be a positive integer.")
    if train_size is None:
        train_frac = float(train_frac)
        if not 0.0 < train_frac < 1.0:
            raise ConfigError(
                "model.split.train_frac must be in (0,1) when train_size is not provided."
            )

    test_size = int(split.get("test_size", 63))
    if test_size <= 0:
        raise ConfigError("model.split.test_size must be a positive integer.")

    step_size = split.get("step_size")
    if step_size is not None and (not isinstance(step_size, int) or step_size <= 0):
        raise ConfigError("model.split.step_size must be a positive integer when provided.")

    expanding = split.get("expanding", True)
    if not isinstance(expanding, bool):
        raise ConfigError("model.split.expanding must be boolean.")

    max_folds = split.get("max_folds")
    if max_folds is not None and (not isinstance(max_folds, int) or max_folds <= 0):
        raise ConfigError("model.split.max_folds must be a positive integer when provided.")

    if method == "purged":
        purge_bars = int(split.get("purge_bars", 0))
        embargo_bars = int(split.get("embargo_bars", 0))
        if purge_bars < 0:
            raise ConfigError("model.split.purge_bars must be >= 0 for method=purged.")
        if embargo_bars < 0:
            raise ConfigError("model.split.embargo_bars must be >= 0 for method=purged.")


def _validate_signals_block(signals: dict[str, Any]) -> None:
    if "kind" not in signals:
        raise ConfigError("signals.kind is required.")
    if not isinstance(signals["kind"], str):
        raise ConfigError("signals.kind must be a string.")


def _validate_risk_block(risk: dict[str, Any]) -> None:
    cpt = risk.get("cost_per_turnover", 0.0)
    if cpt < 0:
        raise ConfigError("risk.cost_per_turnover must be >= 0.")
    spt = risk.get("slippage_per_turnover", 0.0)
    if spt < 0:
        raise ConfigError("risk.slippage_per_turnover must be >= 0.")
    tv = risk.get("target_vol")
    if tv is not None and tv <= 0:
        raise ConfigError("risk.target_vol must be > 0 or null.")
    max_lev = risk.get("max_leverage", 3.0)
    if max_lev <= 0:
        raise ConfigError("risk.max_leverage must be > 0.")
    dd = risk.get("dd_guard", {})
    if not isinstance(dd, dict):
        raise ConfigError("risk.dd_guard must be a mapping.")
    if dd.get("max_drawdown", 0.2) <= 0:
        raise ConfigError("risk.dd_guard.max_drawdown must be > 0.")
    if dd.get("cooloff_bars", 0) < 0:
        raise ConfigError("risk.dd_guard.cooloff_bars must be >= 0.")


def _validate_backtest_block(backtest: dict[str, Any]) -> None:
    for key in ("returns_col", "signal_col"):
        if key not in backtest or not isinstance(backtest[key], str):
            raise ConfigError(f"backtest.{key} (str) is required.")
    ppy = backtest.get("periods_per_year", 252)
    if not isinstance(ppy, int) or ppy <= 0:
        raise ConfigError("backtest.periods_per_year must be a positive integer.")
    returns_type = backtest.get("returns_type", "simple")
    if returns_type not in {"simple", "log"}:
        raise ConfigError("backtest.returns_type must be 'simple' or 'log'.")


def load_experiment_config(config_path: str | Path) -> dict[str, Any]:
    """
    Load an experiment YAML, apply inheritance, defaults, validation,
    and resolve logging paths. Returns a plain dict ready for use.
    """
    path = _resolve_config_path(config_path)
    cfg = _load_with_extends(path)

    cfg.setdefault("data", {})
    cfg.setdefault("features", [])
    cfg.setdefault("model", {"kind": "none"})
    cfg.setdefault("signals", {"kind": "none", "params": {}})
    cfg.setdefault("runtime", {})
    cfg["risk"] = _default_risk_block(cfg.get("risk", {}))
    cfg["backtest"] = _default_backtest_block(cfg.get("backtest", {}))
    cfg["logging"] = _resolve_logging_block(cfg.get("logging", {}), path)
    try:
        cfg["runtime"] = validate_runtime_config(cfg.get("runtime", {}))
    except RuntimeConfigError as exc:
        raise ConfigError(str(exc)) from exc

    _inject_api_key_from_env(cfg["data"])

    _validate_data_block(cfg["data"])
    _validate_features_block(cfg["features"])
    _validate_model_block(cfg["model"])
    _validate_signals_block(cfg["signals"])
    _validate_risk_block(cfg["risk"])
    _validate_backtest_block(cfg["backtest"])

    return cfg


__all__ = [
    "ConfigError",
    "_resolve_config_path",
    "load_experiment_config",
]
