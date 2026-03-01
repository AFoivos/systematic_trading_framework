from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.utils.paths import CONFIG_DIR, PROJECT_ROOT, in_project
from src.utils.repro import RuntimeConfigError, validate_runtime_config


class ConfigError(ValueError):
    """Raised for invalid or inconsistent experiment configs."""


def _default_normalize_daily_for_interval(interval: str) -> bool:
    """Infer a safe timestamp-normalization default from the configured data interval."""
    value = str(interval).strip().lower()
    if value.endswith(("d", "wk", "mo")):
        return True
    return False


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
    """
    Handle YAML inside the infrastructure layer. The helper isolates one focused responsibility
    so the surrounding code remains modular, readable, and easier to test.
    """
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
    """
    Handle with extends inside the infrastructure layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
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
    """
    Handle default risk block inside the infrastructure layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
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


def _default_data_block(data: dict[str, Any]) -> dict[str, Any]:
    """
    Handle default data block inside the infrastructure layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    data = dict(data) if data else {}
    data.setdefault("source", "yahoo")
    data.setdefault("interval", "1d")
    data.setdefault("start", None)
    data.setdefault("end", None)
    data.setdefault("alignment", "inner")

    pit = dict(data.get("pit", {}) or {})
    ts = dict(pit.get("timestamp_alignment", {}) or {})
    ts.setdefault("source_timezone", "UTC")
    ts.setdefault("output_timezone", "UTC")
    ts.setdefault(
        "normalize_daily",
        _default_normalize_daily_for_interval(str(data.get("interval", "1d"))),
    )
    ts.setdefault("duplicate_policy", "last")
    pit["timestamp_alignment"] = ts

    corp = dict(pit.get("corporate_actions", {}) or {})
    corp.setdefault("policy", "none")
    corp.setdefault("adj_close_col", "adj_close")
    pit["corporate_actions"] = corp

    snapshot = dict(pit.get("universe_snapshot", {}) or {})
    snapshot.setdefault("inactive_policy", "raise")
    pit["universe_snapshot"] = snapshot
    data["pit"] = pit

    storage = dict(data.get("storage", {}) or {})
    storage.setdefault("mode", "live")
    storage.setdefault("dataset_id", None)
    storage.setdefault("load_path", None)
    storage.setdefault("save_raw", False)
    storage.setdefault("save_processed", False)
    raw_dir = storage.get("raw_dir", "data/raw")
    processed_dir = storage.get("processed_dir", "data/processed")
    storage["raw_dir"] = str(in_project(raw_dir)) if isinstance(raw_dir, str) else str(raw_dir)
    storage["processed_dir"] = (
        str(in_project(processed_dir)) if isinstance(processed_dir, str) else str(processed_dir)
    )
    load_path = storage.get("load_path")
    if isinstance(load_path, str):
        storage["load_path"] = str(in_project(load_path))
    data["storage"] = storage
    return data


def _default_backtest_block(backtest: dict[str, Any]) -> dict[str, Any]:
    """
    Handle default backtest block inside the infrastructure layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    backtest = dict(backtest) if backtest else {}
    backtest.setdefault("periods_per_year", 252)
    backtest.setdefault("returns_type", "simple")
    backtest.setdefault("missing_return_policy", "raise_if_exposed")
    return backtest


def _default_portfolio_block(portfolio: dict[str, Any]) -> dict[str, Any]:
    """
    Handle default portfolio block inside the infrastructure layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    portfolio = dict(portfolio) if portfolio else {}
    portfolio.setdefault("enabled", False)
    portfolio.setdefault("construction", "signal_weights")
    portfolio.setdefault("gross_target", 1.0)
    portfolio.setdefault("long_short", True)
    portfolio.setdefault("expected_return_col", None)
    portfolio.setdefault("covariance_window", 60)
    portfolio.setdefault("risk_aversion", 5.0)
    portfolio.setdefault("trade_aversion", 0.0)
    portfolio["constraints"] = dict(portfolio.get("constraints", {}) or {})
    portfolio["asset_groups"] = dict(portfolio.get("asset_groups", {}) or {})
    return portfolio


def _default_monitoring_block(monitoring: dict[str, Any]) -> dict[str, Any]:
    """
    Handle default monitoring block inside the infrastructure layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    monitoring = dict(monitoring) if monitoring else {}
    monitoring.setdefault("enabled", True)
    monitoring.setdefault("psi_threshold", 0.2)
    monitoring.setdefault("n_bins", 10)
    return monitoring


def _default_execution_block(execution: dict[str, Any]) -> dict[str, Any]:
    """
    Handle default execution block inside the infrastructure layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    execution = dict(execution) if execution else {}
    execution.setdefault("enabled", False)
    execution.setdefault("mode", "paper")
    execution.setdefault("capital", 1_000_000.0)
    execution.setdefault("price_col", "close")
    execution.setdefault("min_trade_notional", 0.0)
    execution["current_weights"] = dict(execution.get("current_weights", {}) or {})
    return execution


def _resolve_logging_block(logging_cfg: dict[str, Any], config_path: Path) -> dict[str, Any]:
    """
    Handle logging block inside the infrastructure layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    logging_cfg = dict(logging_cfg) if logging_cfg else {}
    logging_cfg.setdefault("run_name", Path(config_path).stem)
    out_dir = logging_cfg.get("output_dir", "logs/experiments")
    if isinstance(out_dir, str):
        logging_cfg["output_dir"] = str(in_project(out_dir))
    return logging_cfg


def _validate_data_block(data: dict[str, Any]) -> None:
    """
    Handle data block inside the infrastructure layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    has_symbol = "symbol" in data and data["symbol"] is not None
    has_symbols = "symbols" in data and data["symbols"] is not None
    if has_symbol and has_symbols:
        raise ConfigError("Specify either data.symbol or data.symbols, not both.")
    if not has_symbol and not has_symbols:
        raise ConfigError("Either data.symbol (str) or data.symbols (list[str]) is required.")
    if has_symbol and not isinstance(data["symbol"], str):
        raise ConfigError("data.symbol must be a string.")
    if has_symbols:
        symbols = data["symbols"]
        if not isinstance(symbols, list) or not symbols or any(not isinstance(s, str) for s in symbols):
            raise ConfigError("data.symbols must be a non-empty list[str].")

    source = data.get("source", "yahoo")
    if source not in {"yahoo", "alpha"}:
        raise ConfigError("data.source must be 'yahoo' or 'alpha'.")
    interval = data.get("interval", "1d")
    if not isinstance(interval, str):
        raise ConfigError("data.interval must be a string (e.g. '1d').")
    alignment = data.get("alignment", "inner")
    if alignment not in {"inner", "outer"}:
        raise ConfigError("data.alignment must be 'inner' or 'outer'.")
    for key in ("start", "end"):
        if key in data and data[key] is not None and not isinstance(data[key], str):
            raise ConfigError(f"data.{key} must be a string date or null.")

    pit = data.get("pit", {})
    if pit is None:
        return
    if not isinstance(pit, dict):
        raise ConfigError("data.pit must be a mapping.")

    ts = pit.get("timestamp_alignment", {})
    if ts is not None:
        if not isinstance(ts, dict):
            raise ConfigError("data.pit.timestamp_alignment must be a mapping.")
        duplicate_policy = ts.get("duplicate_policy", "last")
        if duplicate_policy not in {"first", "last", "raise"}:
            raise ConfigError(
                "data.pit.timestamp_alignment.duplicate_policy must be one of: first, last, raise."
            )
        for k in ("source_timezone", "output_timezone"):
            if k in ts and not isinstance(ts[k], str):
                raise ConfigError(f"data.pit.timestamp_alignment.{k} must be a string.")
        if "normalize_daily" in ts and not isinstance(ts["normalize_daily"], bool):
            raise ConfigError("data.pit.timestamp_alignment.normalize_daily must be boolean.")

    corp = pit.get("corporate_actions", {})
    if corp is not None:
        if not isinstance(corp, dict):
            raise ConfigError("data.pit.corporate_actions must be a mapping.")
        policy = corp.get("policy", "none")
        if policy not in {"none", "adj_close_ratio", "adj_close_replace_close"}:
            raise ConfigError(
                "data.pit.corporate_actions.policy must be one of: "
                "none, adj_close_ratio, adj_close_replace_close."
            )
        if "adj_close_col" in corp and not isinstance(corp["adj_close_col"], str):
            raise ConfigError("data.pit.corporate_actions.adj_close_col must be a string.")

    snapshot = pit.get("universe_snapshot", {})
    if snapshot is not None:
        if not isinstance(snapshot, dict):
            raise ConfigError("data.pit.universe_snapshot must be a mapping.")
        if "path" in snapshot and snapshot["path"] is not None and not isinstance(snapshot["path"], str):
            raise ConfigError("data.pit.universe_snapshot.path must be a string or null.")
        if "as_of" in snapshot and snapshot["as_of"] is not None and not isinstance(snapshot["as_of"], str):
            raise ConfigError("data.pit.universe_snapshot.as_of must be a string date or null.")
        inactive_policy = snapshot.get("inactive_policy", "raise")
        if inactive_policy not in {"raise", "drop_inactive_rows"}:
            raise ConfigError(
                "data.pit.universe_snapshot.inactive_policy must be 'raise' or 'drop_inactive_rows'."
            )

    storage = data.get("storage", {})
    if storage is not None:
        if not isinstance(storage, dict):
            raise ConfigError("data.storage must be a mapping.")
        mode = storage.get("mode", "live")
        if mode not in {"live", "live_or_cached", "cached_only"}:
            raise ConfigError(
                "data.storage.mode must be one of: live, live_or_cached, cached_only."
            )
        dataset_id = storage.get("dataset_id")
        if dataset_id is not None and not isinstance(dataset_id, str):
            raise ConfigError("data.storage.dataset_id must be a string or null.")
        load_path = storage.get("load_path")
        if load_path is not None and not isinstance(load_path, str):
            raise ConfigError("data.storage.load_path must be a string or null.")
        for key in ("raw_dir", "processed_dir"):
            if key in storage and not isinstance(storage[key], str):
                raise ConfigError(f"data.storage.{key} must be a string.")
        for key in ("save_raw", "save_processed"):
            if key in storage and not isinstance(storage[key], bool):
                raise ConfigError(f"data.storage.{key} must be boolean.")


def _inject_api_key_from_env(data: dict[str, Any]) -> None:
    """
    Handle inject API key from env inside the infrastructure layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    env_name = data.get("api_key_env")
    if env_name and not data.get("api_key"):
        data["api_key"] = os.getenv(env_name)


def _validate_features_block(features: Any) -> None:
    """
    Handle features block inside the infrastructure layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    if not isinstance(features, list):
        raise ConfigError("features must be a list of steps.")
    for step in features:
        if not isinstance(step, dict) or "step" not in step:
            raise ConfigError("Each feature entry must be a mapping with a 'step' key.")
        if not isinstance(step["step"], str):
            raise ConfigError("features[].step must be a string.")
        if "params" in step and step["params"] is not None and not isinstance(step["params"], dict):
            raise ConfigError("features[].params must be a mapping when provided.")


def _validate_model_block(model: dict[str, Any]) -> None:
    """
    Handle model block inside the infrastructure layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    if "kind" not in model:
        raise ConfigError("model.kind is required.")
    if not isinstance(model["kind"], str):
        raise ConfigError("model.kind must be a string.")

    if model["kind"] != "none":
        target = model.get("target", {}) or {}
        if not isinstance(target, dict):
            raise ConfigError("model.target must be a mapping when provided.")
        target_kind = target.get("kind", "forward_return")
        if target_kind != "forward_return":
            raise ConfigError("model.target.kind must be 'forward_return'.")
        if "price_col" in target and not isinstance(target["price_col"], str):
            raise ConfigError("model.target.price_col must be a string.")
        horizon = int(target.get("horizon", 1))
        if horizon <= 0:
            raise ConfigError("model.target.horizon must be a positive integer.")
        quantiles = target.get("quantiles")
        if quantiles is not None:
            if not isinstance(quantiles, (list, tuple)) or len(quantiles) != 2:
                raise ConfigError("model.target.quantiles must be a [low, high] pair.")
            q_low, q_high = float(quantiles[0]), float(quantiles[1])
            if not (0.0 <= q_low < q_high <= 1.0):
                raise ConfigError("model.target.quantiles must satisfy 0 <= low < high <= 1.")

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
    """
    Handle signals block inside the infrastructure layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    if "kind" not in signals:
        raise ConfigError("signals.kind is required.")
    if not isinstance(signals["kind"], str):
        raise ConfigError("signals.kind must be a string.")


def _validate_risk_block(risk: dict[str, Any]) -> None:
    """
    Handle risk block inside the infrastructure layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
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
    """
    Handle backtest block inside the infrastructure layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    for key in ("returns_col", "signal_col"):
        if key not in backtest or not isinstance(backtest[key], str):
            raise ConfigError(f"backtest.{key} (str) is required.")
    ppy = backtest.get("periods_per_year", 252)
    if not isinstance(ppy, int) or ppy <= 0:
        raise ConfigError("backtest.periods_per_year must be a positive integer.")
    returns_type = backtest.get("returns_type", "simple")
    if returns_type not in {"simple", "log"}:
        raise ConfigError("backtest.returns_type must be 'simple' or 'log'.")
    missing_return_policy = backtest.get("missing_return_policy", "raise_if_exposed")
    if missing_return_policy not in {"raise", "raise_if_exposed", "fill_zero"}:
        raise ConfigError(
            "backtest.missing_return_policy must be 'raise', 'raise_if_exposed', or 'fill_zero'."
        )


def _validate_portfolio_block(portfolio: dict[str, Any]) -> None:
    """
    Handle portfolio block inside the infrastructure layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    if not isinstance(portfolio.get("enabled", False), bool):
        raise ConfigError("portfolio.enabled must be boolean.")
    construction = portfolio.get("construction", "signal_weights")
    if construction not in {"signal_weights", "mean_variance"}:
        raise ConfigError("portfolio.construction must be 'signal_weights' or 'mean_variance'.")
    if float(portfolio.get("gross_target", 1.0)) <= 0:
        raise ConfigError("portfolio.gross_target must be > 0.")
    if not isinstance(portfolio.get("long_short", True), bool):
        raise ConfigError("portfolio.long_short must be boolean.")
    expected_return_col = portfolio.get("expected_return_col")
    if expected_return_col is not None and not isinstance(expected_return_col, str):
        raise ConfigError("portfolio.expected_return_col must be a string or null.")
    covariance_window = portfolio.get("covariance_window")
    if covariance_window is not None and (not isinstance(covariance_window, int) or covariance_window <= 1):
        raise ConfigError("portfolio.covariance_window must be null or an integer > 1.")
    if float(portfolio.get("risk_aversion", 0.0)) < 0:
        raise ConfigError("portfolio.risk_aversion must be >= 0.")
    if float(portfolio.get("trade_aversion", 0.0)) < 0:
        raise ConfigError("portfolio.trade_aversion must be >= 0.")
    if not isinstance(portfolio.get("constraints", {}), dict):
        raise ConfigError("portfolio.constraints must be a mapping.")
    if not isinstance(portfolio.get("asset_groups", {}), dict):
        raise ConfigError("portfolio.asset_groups must be a mapping.")
    for asset, group in portfolio.get("asset_groups", {}).items():
        if not isinstance(asset, str) or not isinstance(group, str):
            raise ConfigError("portfolio.asset_groups must map str -> str.")


def _validate_monitoring_block(monitoring: dict[str, Any]) -> None:
    """
    Handle monitoring block inside the infrastructure layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    if not isinstance(monitoring.get("enabled", False), bool):
        raise ConfigError("monitoring.enabled must be boolean.")
    if float(monitoring.get("psi_threshold", 0.2)) < 0:
        raise ConfigError("monitoring.psi_threshold must be >= 0.")
    n_bins = monitoring.get("n_bins", 10)
    if not isinstance(n_bins, int) or n_bins <= 1:
        raise ConfigError("monitoring.n_bins must be an integer > 1.")


def _validate_execution_block(execution: dict[str, Any]) -> None:
    """
    Handle execution block inside the infrastructure layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    if not isinstance(execution.get("enabled", False), bool):
        raise ConfigError("execution.enabled must be boolean.")
    if execution.get("mode", "paper") != "paper":
        raise ConfigError("execution.mode currently supports only 'paper'.")
    if float(execution.get("capital", 0.0)) <= 0:
        raise ConfigError("execution.capital must be > 0.")
    if not isinstance(execution.get("price_col", "close"), str):
        raise ConfigError("execution.price_col must be a string.")
    if float(execution.get("min_trade_notional", 0.0)) < 0:
        raise ConfigError("execution.min_trade_notional must be >= 0.")
    if not isinstance(execution.get("current_weights", {}), dict):
        raise ConfigError("execution.current_weights must be a mapping.")


def load_experiment_config(config_path: str | Path) -> dict[str, Any]:
    """
    Load an experiment YAML, apply inheritance, defaults, validation,
    and resolve logging paths. Returns a plain dict ready for use.
    """
    path = _resolve_config_path(config_path)
    cfg = _load_with_extends(path)

    cfg["data"] = _default_data_block(cfg.get("data", {}))
    cfg.setdefault("features", [])
    cfg.setdefault("model", {"kind": "none"})
    cfg.setdefault("signals", {"kind": "none", "params": {}})
    cfg.setdefault("runtime", {})
    cfg["risk"] = _default_risk_block(cfg.get("risk", {}))
    cfg["backtest"] = _default_backtest_block(cfg.get("backtest", {}))
    cfg["portfolio"] = _default_portfolio_block(cfg.get("portfolio", {}))
    cfg["monitoring"] = _default_monitoring_block(cfg.get("monitoring", {}))
    cfg["execution"] = _default_execution_block(cfg.get("execution", {}))
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
    _validate_portfolio_block(cfg["portfolio"])
    _validate_monitoring_block(cfg["monitoring"])
    _validate_execution_block(cfg["execution"])

    return cfg


__all__ = [
    "ConfigError",
    "_resolve_config_path",
    "load_experiment_config",
]
