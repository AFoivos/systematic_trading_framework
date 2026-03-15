from __future__ import annotations

from typing import Any

from src.experiments.registry import FEATURE_REGISTRY, MODEL_REGISTRY, SIGNAL_REGISTRY
from src.intraday import validate_intraday_normalization_policy
from src.utils.repro import RuntimeConfigError, validate_runtime_config


class ConfigValidationError(ValueError):
    """Raised for invalid or inconsistent experiment configs."""


def validate_runtime_block(runtime_cfg: dict[str, Any]) -> dict[str, Any]:
    try:
        return validate_runtime_config(runtime_cfg)
    except RuntimeConfigError as exc:
        raise ConfigValidationError(str(exc)) from exc


def validate_data_block(data: dict[str, Any]) -> None:
    has_symbol = "symbol" in data and data["symbol"] is not None
    has_symbols = "symbols" in data and data["symbols"] is not None
    if has_symbol and has_symbols:
        raise ConfigValidationError("Specify either data.symbol or data.symbols, not both.")
    if not has_symbol and not has_symbols:
        raise ConfigValidationError("Either data.symbol (str) or data.symbols (list[str]) is required.")
    if has_symbol and not isinstance(data["symbol"], str):
        raise ConfigValidationError("data.symbol must be a string.")
    if has_symbols:
        symbols = data["symbols"]
        if not isinstance(symbols, list) or not symbols or any(not isinstance(s, str) for s in symbols):
            raise ConfigValidationError("data.symbols must be a non-empty list[str].")
        if len(set(symbols)) != len(symbols):
            raise ConfigValidationError("data.symbols must not contain duplicates.")

    source = data.get("source", "yahoo")
    if source not in {"yahoo", "alpha", "twelve_data", "twelve"}:
        raise ConfigValidationError(
            "data.source must be 'yahoo', 'alpha', 'twelve_data', or 'twelve'."
        )
    interval = data.get("interval", "1d")
    if not isinstance(interval, str):
        raise ConfigValidationError("data.interval must be a string (e.g. '1d').")
    requested_symbols = (
        [data["symbol"]] if has_symbol else list(data.get("symbols", []) or [])
    )
    if source == "alpha":
        if interval != "1d":
            raise ConfigValidationError("data.interval must be '1d' when data.source='alpha'.")
        for symbol in requested_symbols:
            normalized = str(symbol).replace("=X", "")
            if len(normalized) != 6 or not normalized.isalpha():
                raise ConfigValidationError(
                    "Alpha Vantage FX symbols must look like 'EURUSD' or 'EURUSD=X'."
                )
    alignment = data.get("alignment", "inner")
    if alignment not in {"inner", "outer"}:
        raise ConfigValidationError("data.alignment must be 'inner' or 'outer'.")
    for key in ("start", "end"):
        if key in data and data[key] is not None and not isinstance(data[key], str):
            raise ConfigValidationError(f"data.{key} must be a string date or null.")

    pit = data.get("pit", {})
    if pit is None:
        return
    if not isinstance(pit, dict):
        raise ConfigValidationError("data.pit must be a mapping.")

    ts = pit.get("timestamp_alignment", {})
    if ts is not None:
        if not isinstance(ts, dict):
            raise ConfigValidationError("data.pit.timestamp_alignment must be a mapping.")
        duplicate_policy = ts.get("duplicate_policy", "last")
        if duplicate_policy not in {"first", "last", "raise"}:
            raise ConfigValidationError(
                "data.pit.timestamp_alignment.duplicate_policy must be one of: first, last, raise."
            )
        for key in ("source_timezone", "output_timezone"):
            if key in ts and not isinstance(ts[key], str):
                raise ConfigValidationError(f"data.pit.timestamp_alignment.{key} must be a string.")
        if "normalize_daily" in ts and not isinstance(ts["normalize_daily"], bool):
            raise ConfigValidationError("data.pit.timestamp_alignment.normalize_daily must be boolean.")
        validate_intraday_normalization_policy(
            str(interval),
            normalize_daily=bool(ts.get("normalize_daily", False)),
        )

    corp = pit.get("corporate_actions", {})
    if corp is not None:
        if not isinstance(corp, dict):
            raise ConfigValidationError("data.pit.corporate_actions must be a mapping.")
        policy = corp.get("policy", "none")
        if policy not in {"none", "adj_close_ratio", "adj_close_replace_close"}:
            raise ConfigValidationError(
                "data.pit.corporate_actions.policy must be one of: "
                "none, adj_close_ratio, adj_close_replace_close."
            )
        if "adj_close_col" in corp and not isinstance(corp["adj_close_col"], str):
            raise ConfigValidationError("data.pit.corporate_actions.adj_close_col must be a string.")

    snapshot = pit.get("universe_snapshot", {})
    if snapshot is not None:
        if not isinstance(snapshot, dict):
            raise ConfigValidationError("data.pit.universe_snapshot must be a mapping.")
        if "path" in snapshot and snapshot["path"] is not None and not isinstance(snapshot["path"], str):
            raise ConfigValidationError("data.pit.universe_snapshot.path must be a string or null.")
        if "as_of" in snapshot and snapshot["as_of"] is not None and not isinstance(snapshot["as_of"], str):
            raise ConfigValidationError("data.pit.universe_snapshot.as_of must be a string date or null.")
        inactive_policy = snapshot.get("inactive_policy", "raise")
        if inactive_policy not in {"raise", "drop_inactive_rows"}:
            raise ConfigValidationError(
                "data.pit.universe_snapshot.inactive_policy must be 'raise' or 'drop_inactive_rows'."
            )

    storage = data.get("storage", {})
    if storage is not None:
        if not isinstance(storage, dict):
            raise ConfigValidationError("data.storage must be a mapping.")
        mode = storage.get("mode", "live")
        if mode not in {"live", "live_or_cached", "cached_only"}:
            raise ConfigValidationError(
                "data.storage.mode must be one of: live, live_or_cached, cached_only."
            )
        dataset_id = storage.get("dataset_id")
        if dataset_id is not None and not isinstance(dataset_id, str):
            raise ConfigValidationError("data.storage.dataset_id must be a string or null.")
        load_path = storage.get("load_path")
        if load_path is not None and not isinstance(load_path, str):
            raise ConfigValidationError("data.storage.load_path must be a string or null.")
        for key in ("raw_dir", "processed_dir"):
            if key in storage and not isinstance(storage[key], str):
                raise ConfigValidationError(f"data.storage.{key} must be a string.")
        for key in ("save_raw", "save_processed"):
            if key in storage and not isinstance(storage[key], bool):
                raise ConfigValidationError(f"data.storage.{key} must be boolean.")


def validate_features_block(features: Any) -> None:
    if not isinstance(features, list):
        raise ConfigValidationError("features must be a list of steps.")
    for step in features:
        if not isinstance(step, dict) or "step" not in step:
            raise ConfigValidationError("Each feature entry must be a mapping with a 'step' key.")
        if not isinstance(step["step"], str):
            raise ConfigValidationError("features[].step must be a string.")
        if step["step"] not in FEATURE_REGISTRY:
            raise ConfigValidationError(f"Unknown feature step: {step['step']}")
        if "params" in step and step["params"] is not None and not isinstance(step["params"], dict):
            raise ConfigValidationError("features[].params must be a mapping when provided.")


def validate_model_block(model: dict[str, Any]) -> None:
    if "kind" not in model:
        raise ConfigValidationError("model.kind is required.")
    if not isinstance(model["kind"], str):
        raise ConfigValidationError("model.kind must be a string.")
    if model["kind"] != "none" and model["kind"] not in MODEL_REGISTRY:
        raise ConfigValidationError(f"Unknown model kind: {model['kind']}")

    if model["kind"] != "none":
        feature_cols = model.get("feature_cols")
        if feature_cols is not None:
            if (
                not isinstance(feature_cols, list)
                or not feature_cols
                or any(not isinstance(col, str) or not col.strip() for col in feature_cols)
            ):
                raise ConfigValidationError(
                    "model.feature_cols must be a non-empty list[str] when provided."
                )

        target = model.get("target", {}) or {}
        if not isinstance(target, dict):
            raise ConfigValidationError("model.target must be a mapping when provided.")
        target_kind = target.get("kind", "forward_return")
        if target_kind != "forward_return":
            raise ConfigValidationError("model.target.kind must be 'forward_return'.")
        if "price_col" in target and not isinstance(target["price_col"], str):
            raise ConfigValidationError("model.target.price_col must be a string.")
        horizon = int(target.get("horizon", 1))
        if horizon <= 0:
            raise ConfigValidationError("model.target.horizon must be a positive integer.")
        quantiles = target.get("quantiles")
        if quantiles is not None:
            if not isinstance(quantiles, (list, tuple)) or len(quantiles) != 2:
                raise ConfigValidationError("model.target.quantiles must be a [low, high] pair.")
            q_low, q_high = float(quantiles[0]), float(quantiles[1])
            if not (0.0 <= q_low < q_high <= 1.0):
                raise ConfigValidationError("model.target.quantiles must satisfy 0 <= low < high <= 1.")

    split = model.get("split")
    if split is None:
        return
    if not isinstance(split, dict):
        raise ConfigValidationError("model.split must be a mapping when provided.")

    method = split.get("method", "time")
    if method not in {"time", "walk_forward", "purged"}:
        raise ConfigValidationError("model.split.method must be one of: time, walk_forward, purged.")

    if method == "time":
        train_frac = float(split.get("train_frac", 0.7))
        if not 0.0 < train_frac < 1.0:
            raise ConfigValidationError("model.split.train_frac must be in (0,1) for method=time.")
        return

    train_size = split.get("train_size")
    train_frac = split.get("train_frac", 0.7 if train_size is None else None)
    if train_size is None and train_frac is None:
        raise ConfigValidationError(
            "model.split for walk_forward/purged requires either train_size or train_frac."
        )
    if train_size is not None and (not isinstance(train_size, int) or train_size <= 0):
        raise ConfigValidationError("model.split.train_size must be a positive integer.")
    if train_size is None:
        train_frac = float(train_frac)
        if not 0.0 < train_frac < 1.0:
            raise ConfigValidationError(
                "model.split.train_frac must be in (0,1) when train_size is not provided."
            )

    test_size = int(split.get("test_size", 63))
    if test_size <= 0:
        raise ConfigValidationError("model.split.test_size must be a positive integer.")

    step_size = split.get("step_size")
    if step_size is not None and (not isinstance(step_size, int) or step_size <= 0):
        raise ConfigValidationError("model.split.step_size must be a positive integer when provided.")

    expanding = split.get("expanding", True)
    if not isinstance(expanding, bool):
        raise ConfigValidationError("model.split.expanding must be boolean.")

    max_folds = split.get("max_folds")
    if max_folds is not None and (not isinstance(max_folds, int) or max_folds <= 0):
        raise ConfigValidationError("model.split.max_folds must be a positive integer when provided.")

    if method == "purged":
        purge_bars = int(split.get("purge_bars", 0))
        embargo_bars = int(split.get("embargo_bars", 0))
        if purge_bars < 0:
            raise ConfigValidationError("model.split.purge_bars must be >= 0 for method=purged.")
        if embargo_bars < 0:
            raise ConfigValidationError("model.split.embargo_bars must be >= 0 for method=purged.")


def validate_signals_block(signals: dict[str, Any]) -> None:
    if "kind" not in signals:
        raise ConfigValidationError("signals.kind is required.")
    if not isinstance(signals["kind"], str):
        raise ConfigValidationError("signals.kind must be a string.")
    if signals["kind"] != "none" and signals["kind"] not in SIGNAL_REGISTRY:
        raise ConfigValidationError(f"Unknown signals kind: {signals['kind']}")


def validate_risk_block(risk: dict[str, Any]) -> None:
    cpt = risk.get("cost_per_turnover", 0.0)
    if cpt < 0:
        raise ConfigValidationError("risk.cost_per_turnover must be >= 0.")
    spt = risk.get("slippage_per_turnover", 0.0)
    if spt < 0:
        raise ConfigValidationError("risk.slippage_per_turnover must be >= 0.")
    tv = risk.get("target_vol")
    if tv is not None and tv <= 0:
        raise ConfigValidationError("risk.target_vol must be > 0 or null.")
    max_lev = risk.get("max_leverage", 3.0)
    if max_lev <= 0:
        raise ConfigValidationError("risk.max_leverage must be > 0.")
    dd = risk.get("dd_guard", {})
    if not isinstance(dd, dict):
        raise ConfigValidationError("risk.dd_guard must be a mapping.")
    if dd.get("max_drawdown", 0.2) <= 0:
        raise ConfigValidationError("risk.dd_guard.max_drawdown must be > 0.")
    if dd.get("cooloff_bars", 0) < 0:
        raise ConfigValidationError("risk.dd_guard.cooloff_bars must be >= 0.")


def validate_backtest_block(backtest: dict[str, Any]) -> None:
    for key in ("returns_col", "signal_col"):
        if key not in backtest or not isinstance(backtest[key], str):
            raise ConfigValidationError(f"backtest.{key} (str) is required.")
    ppy = backtest.get("periods_per_year", 252)
    if not isinstance(ppy, int) or ppy <= 0:
        raise ConfigValidationError("backtest.periods_per_year must be a positive integer.")
    returns_type = backtest.get("returns_type", "simple")
    if returns_type not in {"simple", "log"}:
        raise ConfigValidationError("backtest.returns_type must be 'simple' or 'log'.")
    missing_return_policy = backtest.get("missing_return_policy", "raise_if_exposed")
    if missing_return_policy not in {"raise", "raise_if_exposed", "fill_zero"}:
        raise ConfigValidationError(
            "backtest.missing_return_policy must be 'raise', 'raise_if_exposed', or 'fill_zero'."
        )


def validate_portfolio_block(portfolio: dict[str, Any]) -> None:
    if not isinstance(portfolio.get("enabled", False), bool):
        raise ConfigValidationError("portfolio.enabled must be boolean.")
    construction = portfolio.get("construction", "signal_weights")
    if construction not in {"signal_weights", "mean_variance"}:
        raise ConfigValidationError("portfolio.construction must be 'signal_weights' or 'mean_variance'.")
    if float(portfolio.get("gross_target", 1.0)) <= 0:
        raise ConfigValidationError("portfolio.gross_target must be > 0.")
    if not isinstance(portfolio.get("long_short", True), bool):
        raise ConfigValidationError("portfolio.long_short must be boolean.")
    expected_return_col = portfolio.get("expected_return_col")
    if expected_return_col is not None and not isinstance(expected_return_col, str):
        raise ConfigValidationError("portfolio.expected_return_col must be a string or null.")
    covariance_window = portfolio.get("covariance_window")
    if covariance_window is not None and (not isinstance(covariance_window, int) or covariance_window <= 1):
        raise ConfigValidationError("portfolio.covariance_window must be null or an integer > 1.")
    covariance_rebalance_step = portfolio.get("covariance_rebalance_step")
    if covariance_rebalance_step is not None and (
        not isinstance(covariance_rebalance_step, int) or covariance_rebalance_step <= 0
    ):
        raise ConfigValidationError("portfolio.covariance_rebalance_step must be a positive integer.")
    if float(portfolio.get("risk_aversion", 0.0)) < 0:
        raise ConfigValidationError("portfolio.risk_aversion must be >= 0.")
    if float(portfolio.get("trade_aversion", 0.0)) < 0:
        raise ConfigValidationError("portfolio.trade_aversion must be >= 0.")
    if not isinstance(portfolio.get("constraints", {}), dict):
        raise ConfigValidationError("portfolio.constraints must be a mapping.")
    if not isinstance(portfolio.get("asset_groups", {}), dict):
        raise ConfigValidationError("portfolio.asset_groups must be a mapping.")
    for asset, group in portfolio.get("asset_groups", {}).items():
        if not isinstance(asset, str) or not isinstance(group, str):
            raise ConfigValidationError("portfolio.asset_groups must map str -> str.")


def validate_monitoring_block(monitoring: dict[str, Any]) -> None:
    if not isinstance(monitoring.get("enabled", False), bool):
        raise ConfigValidationError("monitoring.enabled must be boolean.")
    if float(monitoring.get("psi_threshold", 0.2)) < 0:
        raise ConfigValidationError("monitoring.psi_threshold must be >= 0.")
    n_bins = monitoring.get("n_bins", 10)
    if not isinstance(n_bins, int) or n_bins <= 1:
        raise ConfigValidationError("monitoring.n_bins must be an integer > 1.")


def validate_execution_block(execution: dict[str, Any]) -> None:
    if not isinstance(execution.get("enabled", False), bool):
        raise ConfigValidationError("execution.enabled must be boolean.")
    if execution.get("mode", "paper") != "paper":
        raise ConfigValidationError("execution.mode currently supports only 'paper'.")
    if float(execution.get("capital", 0.0)) <= 0:
        raise ConfigValidationError("execution.capital must be > 0.")
    if not isinstance(execution.get("price_col", "close"), str):
        raise ConfigValidationError("execution.price_col must be a string.")
    if float(execution.get("min_trade_notional", 0.0)) < 0:
        raise ConfigValidationError("execution.min_trade_notional must be >= 0.")
    if not isinstance(execution.get("current_weights", {}), dict):
        raise ConfigValidationError("execution.current_weights must be a mapping.")


def validate_logging_block(logging_cfg: dict[str, Any]) -> None:
    if not isinstance(logging_cfg.get("enabled", False), bool):
        raise ConfigValidationError("logging.enabled must be boolean.")
    if not isinstance(logging_cfg.get("run_name", ""), str) or not logging_cfg.get("run_name", "").strip():
        raise ConfigValidationError("logging.run_name must be a non-empty string.")
    if not isinstance(logging_cfg.get("output_dir", ""), str) or not logging_cfg.get("output_dir", "").strip():
        raise ConfigValidationError("logging.output_dir must be a non-empty string.")


def validate_resolved_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """
    Validate all top-level blocks and normalize the runtime sub-config.
    """
    validate_data_block(cfg["data"])
    validate_features_block(cfg["features"])
    validate_model_block(cfg["model"])
    validate_signals_block(cfg["signals"])
    validate_risk_block(cfg["risk"])
    validate_backtest_block(cfg["backtest"])
    validate_portfolio_block(cfg["portfolio"])
    validate_monitoring_block(cfg["monitoring"])
    validate_execution_block(cfg["execution"])
    validate_logging_block(cfg["logging"])
    cfg["runtime"] = validate_runtime_block(dict(cfg.get("runtime", {}) or {}))
    return cfg


__all__ = [
    "ConfigValidationError",
    "validate_backtest_block",
    "validate_data_block",
    "validate_execution_block",
    "validate_logging_block",
    "validate_features_block",
    "validate_model_block",
    "validate_monitoring_block",
    "validate_portfolio_block",
    "validate_resolved_config",
    "validate_risk_block",
    "validate_runtime_block",
    "validate_signals_block",
]
