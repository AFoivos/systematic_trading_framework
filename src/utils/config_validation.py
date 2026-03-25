from __future__ import annotations

import math
from typing import Any

from src.experiments.registry import (
    FEATURE_REGISTRY,
    MODEL_REGISTRY,
    PORTFOLIO_MODEL_KINDS,
    RL_MODEL_KINDS,
    SIGNAL_REGISTRY,
)
from src.intraday import validate_intraday_normalization_policy
from src.utils.repro import RuntimeConfigError, validate_runtime_config

_RL_SINGLE_ASSET_DQN_KINDS = {"dqn_agent"}
_RL_PORTFOLIO_DQN_KINDS = {"dqn_portfolio_agent"}
_RL_EXTRACTOR_KINDS = {"flatten", "cnn1d", "lstm", "transformer"}
_CLASSIFIER_MODEL_KINDS = {"lightgbm_clf", "logistic_regression_clf", "xgboost_clf"}
_DEEP_FORECASTER_MODEL_KINDS = {"lstm_forecaster", "patchtst_forecaster", "tft_forecaster"}
_FORECASTER_MODEL_KINDS = {"sarimax_forecaster", "garch_forecaster", *_DEEP_FORECASTER_MODEL_KINDS}
_GARCH_OVERLAY_COMPATIBLE_MODEL_KINDS = {
    "lightgbm_clf",
    "logistic_regression_clf",
    "xgboost_clf",
    "sarimax_forecaster",
    "lstm_forecaster",
    "patchtst_forecaster",
    "tft_forecaster",
}
_XGBOOST_UNSUPPORTED_PARAM_KEYS = {"num_leaves", "min_child_samples"}
_PPO_ONLY_RL_PARAM_KEYS = {"n_steps", "gae_lambda", "clip_range", "ent_coef", "vf_coef", "max_grad_norm"}
_DQN_ONLY_RL_PARAM_KEYS = {
    "buffer_size",
    "learning_starts",
    "tau",
    "train_freq",
    "gradient_steps",
    "target_update_interval",
    "exploration_fraction",
    "exploration_initial_eps",
    "exploration_final_eps",
}


class ConfigValidationError(ValueError):
    """Raised for invalid or inconsistent experiment configs."""


def _canonical_symbol_for_source(symbol: str, source: str) -> str:
    raw = str(symbol).strip().upper()
    if source in {"twelve_data", "twelve"}:
        if raw.endswith("=X"):
            raw = raw[:-2]
        if "/" in raw:
            parts = raw.split("/")
            if len(parts) == 2 and all(len(part) == 3 and part.isalpha() for part in parts):
                return f"{parts[0]}/{parts[1]}"
            return raw
        if len(raw) == 6 and raw.isalpha():
            return f"{raw[:3]}/{raw[3:]}"
        return raw
    if source == "alpha":
        return raw.replace("=X", "")
    return raw


def _finite_number(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigValidationError(f"{field} must be a finite number.")
    out = float(value)
    if not math.isfinite(out):
        raise ConfigValidationError(f"{field} must be a finite number.")
    return out


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigValidationError(f"{field} must be a positive integer.")
    return value


def _non_negative_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ConfigValidationError(f"{field} must be an integer >= 0.")
    return value


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
    if source not in {"yahoo", "alpha", "twelve_data", "twelve", "dukascopy_csv"}:
        raise ConfigValidationError(
            "data.source must be 'yahoo', 'alpha', 'twelve_data', 'twelve', or 'dukascopy_csv'."
        )
    interval = data.get("interval", "1d")
    if not isinstance(interval, str):
        raise ConfigValidationError("data.interval must be a string (e.g. '1d').")
    requested_symbols = (
        [data["symbol"]] if has_symbol else list(data.get("symbols", []) or [])
    )
    canonical_symbols = [_canonical_symbol_for_source(symbol, source) for symbol in requested_symbols]
    if len(set(canonical_symbols)) != len(canonical_symbols):
        raise ConfigValidationError(
            "data.symbols must not contain provider-equivalent duplicates after normalization."
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
    if source == "dukascopy_csv":
        storage_for_external_csv = data.get("storage", {}) or {}
        if not isinstance(storage_for_external_csv, dict):
            raise ConfigValidationError("data.storage must be a mapping when data.source='dukascopy_csv'.")
        load_path = storage_for_external_csv.get("load_path")
        if not isinstance(load_path, str) or not load_path.strip():
            raise ConfigValidationError(
                "data.storage.load_path is required when data.source='dukascopy_csv'."
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
        if "enabled" in step and not isinstance(step["enabled"], bool):
            raise ConfigValidationError("features[].enabled must be boolean when provided.")
        if step["step"] not in FEATURE_REGISTRY:
            raise ConfigValidationError(f"Unknown feature step: {step['step']}")
        if "params" in step and step["params"] is not None and not isinstance(step["params"], dict):
            raise ConfigValidationError("features[].params must be a mapping when provided.")
        if step["step"] == "feature_transforms":
            params = step.get("params") or {}
            transforms = params.get("transforms")
            if not isinstance(transforms, list) or not transforms:
                raise ConfigValidationError(
                    "features[].params.transforms must be a non-empty list for step='feature_transforms'."
                )
            for idx, transform in enumerate(transforms):
                field_prefix = f"features[].params.transforms[{idx}]"
                if not isinstance(transform, dict):
                    raise ConfigValidationError(f"{field_prefix} must be a mapping.")
                source_col = transform.get("source_col")
                if not isinstance(source_col, str) or not source_col.strip():
                    raise ConfigValidationError(f"{field_prefix}.source_col must be a non-empty string.")
                kind = transform.get("kind")
                if kind != "rolling_clip":
                    raise ConfigValidationError(
                        f"{field_prefix}.kind must be 'rolling_clip'."
                    )
                output_col = transform.get("output_col")
                if not isinstance(output_col, str) or not output_col.strip():
                    raise ConfigValidationError(f"{field_prefix}.output_col must be a non-empty string.")
                _positive_int(transform.get("window", 2520), field=f"{field_prefix}.window")
                lower_q = _finite_number(transform.get("lower_q", 0.01), field=f"{field_prefix}.lower_q")
                upper_q = _finite_number(transform.get("upper_q", 0.99), field=f"{field_prefix}.upper_q")
                if not 0.0 <= lower_q <= 1.0:
                    raise ConfigValidationError(f"{field_prefix}.lower_q must be in [0, 1].")
                if not 0.0 <= upper_q <= 1.0:
                    raise ConfigValidationError(f"{field_prefix}.upper_q must be in [0, 1].")
                if not lower_q < upper_q:
                    raise ConfigValidationError(
                        f"{field_prefix}.lower_q must be strictly less than {field_prefix}.upper_q."
                    )
                _non_negative_int(transform.get("shift", 1), field=f"{field_prefix}.shift")
        if step["step"] == "shock_context":
            params = step.get("params") or {}
            for key in ("price_col", "high_col", "low_col", "returns_col", "ema_col", "atr_col"):
                if key in params and params[key] is not None and not isinstance(params[key], str):
                    raise ConfigValidationError(f"features[].params.{key} must be a string when provided.")
            for key in (
                "short_horizon",
                "medium_horizon",
                "vol_window",
                "ema_window",
                "atr_window",
                "post_shock_active_bars",
            ):
                if key in params and params[key] is not None:
                    _positive_int(params[key], field=f"features[].params.{key}")
            short_horizon = int(params.get("short_horizon", 1))
            medium_horizon = int(params.get("medium_horizon", 4))
            if medium_horizon < short_horizon:
                raise ConfigValidationError(
                    "features[].params.medium_horizon must be >= features[].params.short_horizon."
                )
            for key in ("ret_z_threshold", "atr_mult_threshold", "distance_from_mean_threshold"):
                if key in params and params[key] is not None:
                    value = _finite_number(params[key], field=f"features[].params.{key}")
                    if value <= 0.0:
                        raise ConfigValidationError(f"features[].params.{key} must be > 0.")
            if "use_log_returns" in params and not isinstance(params["use_log_returns"], bool):
                raise ConfigValidationError("features[].params.use_log_returns must be boolean.")


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
        if target_kind not in {"forward_return", "triple_barrier"}:
            raise ConfigValidationError("model.target.kind must be 'forward_return' or 'triple_barrier'.")
        if target_kind == "triple_barrier" and model["kind"] not in _CLASSIFIER_MODEL_KINDS:
            raise ConfigValidationError("model.target.kind='triple_barrier' is currently supported only for classifiers.")
        if target_kind == "forward_return" and model["kind"] in _CLASSIFIER_MODEL_KINDS:
            pass
        if "price_col" in target and not isinstance(target["price_col"], str):
            raise ConfigValidationError("model.target.price_col must be a string.")
        if target_kind == "forward_return":
            _positive_int(target.get("horizon", 1), field="model.target.horizon")
            if "returns_col" in target and target["returns_col"] is not None and not isinstance(target["returns_col"], str):
                raise ConfigValidationError("model.target.returns_col must be a string or null.")
            returns_type = str(target.get("returns_type", "simple"))
            if returns_type not in {"simple", "log"}:
                raise ConfigValidationError("model.target.returns_type must be 'simple' or 'log'.")
            if target.get("returns_col") is None and returns_type != "simple":
                raise ConfigValidationError("model.target.returns_type='log' requires model.target.returns_col.")
        quantiles = target.get("quantiles")
        if quantiles is not None:
            if not isinstance(quantiles, (list, tuple)) or len(quantiles) != 2:
                raise ConfigValidationError("model.target.quantiles must be a [low, high] pair.")
            q_low, q_high = float(quantiles[0]), float(quantiles[1])
            if not (0.0 <= q_low < q_high <= 1.0):
                raise ConfigValidationError("model.target.quantiles must satisfy 0 <= low < high <= 1.")
            if target_kind != "forward_return":
                raise ConfigValidationError("model.target.quantiles are only supported for target.kind='forward_return'.")
        if target_kind == "triple_barrier":
            for key in ("open_col", "high_col", "low_col", "returns_col", "volatility_col", "label_col"):
                if key in target and target[key] is not None and not isinstance(target[key], str):
                    raise ConfigValidationError(f"model.target.{key} must be a string or null.")
            for key in ("side_col", "candidate_col", "candidate_out_col"):
                if key in target and target[key] is not None and not isinstance(target[key], str):
                    raise ConfigValidationError(f"model.target.{key} must be a string or null.")
            _positive_int(target.get("max_holding", target.get("horizon", 24)), field="model.target.max_holding")
            for key in ("upper_mult", "lower_mult", "min_vol"):
                value = _finite_number(target.get(key, 2.0 if key != "min_vol" else 1e-4), field=f"model.target.{key}")
                if value <= 0:
                    raise ConfigValidationError(f"model.target.{key} must be > 0.")
            if "vol_window" in target:
                _positive_int(target["vol_window"], field="model.target.vol_window")
            neutral_label = target.get("neutral_label", "drop")
            if neutral_label not in {"drop", "lower", "upper"}:
                raise ConfigValidationError("model.target.neutral_label must be one of: drop, lower, upper.")
            tie_break = target.get("tie_break", "closest_to_open")
            if tie_break not in {"closest_to_open", "upper", "lower"}:
                raise ConfigValidationError("model.target.tie_break must be one of: closest_to_open, upper, lower.")
            candidate_mode = str(target.get("candidate_mode", "all_nonzero"))
            if candidate_mode not in {"all_nonzero", "side_change"}:
                raise ConfigValidationError("model.target.candidate_mode must be one of: all_nonzero, side_change.")

        preprocessing = model.get("preprocessing", {}) or {}
        if preprocessing:
            if not isinstance(preprocessing, dict):
                raise ConfigValidationError("model.preprocessing must be a mapping when provided.")
            scaler = str(preprocessing.get("scaler", "none"))
            if scaler not in {"none", "standard"}:
                raise ConfigValidationError("model.preprocessing.scaler must be 'none' or 'standard'.")

        overlay = model.get("overlay", {}) or {}
        if overlay:
            if not isinstance(overlay, dict):
                raise ConfigValidationError("model.overlay must be a mapping when provided.")
            if model["kind"] not in _GARCH_OVERLAY_COMPATIBLE_MODEL_KINDS:
                raise ConfigValidationError(
                    "model.overlay is currently supported only for lightgbm_clf, logistic_regression_clf, "
                    "xgboost_clf, sarimax_forecaster, lstm_forecaster, patchtst_forecaster, and "
                    "tft_forecaster."
                )
            overlay_kind = overlay.get("kind")
            if overlay_kind != "garch":
                raise ConfigValidationError("model.overlay.kind must currently be 'garch'.")
            overlay_params = overlay.get("params", {}) or {}
            if not isinstance(overlay_params, dict):
                raise ConfigValidationError("model.overlay.params must be a mapping when provided.")
            if "returns_input_col" in overlay_params and not isinstance(overlay_params["returns_input_col"], str):
                raise ConfigValidationError("model.overlay.params.returns_input_col must be a string.")
            if "mean_model" in overlay_params and overlay_params["mean_model"] not in {"zero", "constant", "ar1"}:
                raise ConfigValidationError(
                    "model.overlay.params.mean_model must be one of: zero, constant, ar1."
                )

        if model["kind"] in _DEEP_FORECASTER_MODEL_KINDS:
            params = model.get("params", {}) or {}
            if not isinstance(params, dict):
                raise ConfigValidationError("model.params must be a mapping.")
            _positive_int(params.get("lookback", 32), field="model.params.lookback")
            if "epochs" in params:
                _positive_int(params["epochs"], field="model.params.epochs")
            if "batch_size" in params:
                _positive_int(params["batch_size"], field="model.params.batch_size")
            if "hidden_dim" in params:
                _positive_int(params["hidden_dim"], field="model.params.hidden_dim")
            if "num_layers" in params:
                _positive_int(params["num_layers"], field="model.params.num_layers")
            if "num_heads" in params:
                _positive_int(params["num_heads"], field="model.params.num_heads")
            if "patch_len" in params:
                _positive_int(params["patch_len"], field="model.params.patch_len")
            if "patch_stride" in params:
                _positive_int(params["patch_stride"], field="model.params.patch_stride")
            if "learning_rate" in params:
                lr = _finite_number(params["learning_rate"], field="model.params.learning_rate")
                if lr <= 0:
                    raise ConfigValidationError("model.params.learning_rate must be > 0.")
            if "weight_decay" in params:
                wd = _finite_number(params["weight_decay"], field="model.params.weight_decay")
                if wd < 0:
                    raise ConfigValidationError("model.params.weight_decay must be >= 0.")
            if "dropout" in params:
                dropout = _finite_number(params["dropout"], field="model.params.dropout")
                if not 0.0 <= dropout < 1.0:
                    raise ConfigValidationError("model.params.dropout must be in [0,1).")
            if "scale_target" in params and not isinstance(params["scale_target"], bool):
                raise ConfigValidationError("model.params.scale_target must be boolean.")
            quantiles = params.get("quantiles")
            if quantiles is not None:
                if not isinstance(quantiles, (list, tuple)) or len(quantiles) < 2:
                    raise ConfigValidationError("model.params.quantiles must be a list with at least two values.")
                q_values = [float(q) for q in quantiles]
                if any(not 0.0 < q < 1.0 for q in q_values):
                    raise ConfigValidationError("model.params.quantiles values must be in (0,1).")

        params = model.get("params", {}) or {}
        if not isinstance(params, dict):
            raise ConfigValidationError("model.params must be a mapping.")
        if model["kind"] == "xgboost_clf":
            invalid_keys = [
                key
                for key in _XGBOOST_UNSUPPORTED_PARAM_KEYS
                if key in params and params[key] is not None
            ]
            if invalid_keys:
                joined = ", ".join(sorted(invalid_keys))
                raise ConfigValidationError(
                    "xgboost_clf does not support LightGBM-only params: "
                    f"{joined}. Remove them or set them to null in the child config."
                )

        if model["kind"] in RL_MODEL_KINDS:
            if int(target.get("horizon", 1)) != 1:
                raise ConfigValidationError("RL model.target.horizon currently supports only 1.")
            env_cfg = model.get("env", {})
            if env_cfg is not None and not isinstance(env_cfg, dict):
                raise ConfigValidationError("model.env must be a mapping when provided.")
            env_cfg = dict(env_cfg or {})

            action_space = env_cfg.get("action_space")
            if action_space is not None and action_space not in {"continuous", "discrete"}:
                raise ConfigValidationError("model.env.action_space must be 'continuous' or 'discrete'.")

            execution_lag_bars = _positive_int(
                env_cfg.get("execution_lag_bars", 1),
                field="model.env.execution_lag_bars",
            )
            if execution_lag_bars != 1:
                raise ConfigValidationError("RL currently supports only model.env.execution_lag_bars=1.")

            _positive_int(env_cfg.get("window_size", 32), field="model.env.window_size")

            if "max_signal_abs" in env_cfg and "max_position" in env_cfg:
                left = _finite_number(env_cfg["max_signal_abs"], field="model.env.max_signal_abs")
                right = _finite_number(env_cfg["max_position"], field="model.env.max_position")
                if not math.isclose(left, right):
                    raise ConfigValidationError(
                        "model.env.max_signal_abs and model.env.max_position must match when both are set."
                    )
            max_signal_abs = _finite_number(
                env_cfg.get("max_signal_abs", env_cfg.get("max_position", 1.0)),
                field="model.env.max_signal_abs",
            )
            if max_signal_abs <= 0:
                raise ConfigValidationError("model.env.max_signal_abs must be > 0.")
            _non_negative_int(
                env_cfg.get("min_holding_bars", 0),
                field="model.env.min_holding_bars",
            )
            action_hysteresis = _finite_number(
                env_cfg.get("action_hysteresis", 0.0),
                field="model.env.action_hysteresis",
            )
            if action_hysteresis < 0:
                raise ConfigValidationError("model.env.action_hysteresis must be >= 0.")

            reward_cfg = env_cfg.get("reward", {})
            if reward_cfg is not None and not isinstance(reward_cfg, dict):
                raise ConfigValidationError("model.env.reward must be a mapping when provided.")
            for key in (
                "cost_per_turnover",
                "slippage_per_turnover",
                "inventory_penalty",
                "drawdown_penalty",
                "switching_penalty",
            ):
                value = _finite_number(
                    dict(reward_cfg or {}).get(key, 0.0),
                    field=f"model.env.reward.{key}",
                )
                if value < 0:
                    raise ConfigValidationError(f"model.env.reward.{key} must be >= 0.")

            if model["kind"] in (_RL_SINGLE_ASSET_DQN_KINDS | _RL_PORTFOLIO_DQN_KINDS):
                resolved_action_space = action_space or "discrete"
                if resolved_action_space != "discrete":
                    raise ConfigValidationError("DQN agents require model.env.action_space='discrete'.")

            if model["kind"] in _RL_SINGLE_ASSET_DQN_KINDS or (
                model["kind"] == "ppo_agent" and action_space == "discrete"
            ):
                position_grid = env_cfg.get("position_grid")
                if position_grid is not None:
                    if not isinstance(position_grid, (list, tuple)) or len(position_grid) == 0:
                        raise ConfigValidationError(
                            "model.env.position_grid must be a non-empty list when provided."
                        )
                    for idx, value in enumerate(position_grid):
                        _finite_number(value, field=f"model.env.position_grid[{idx}]")

            if model["kind"] in _RL_PORTFOLIO_DQN_KINDS or (
                model["kind"] == "ppo_portfolio_agent" and action_space == "discrete"
            ):
                action_templates = env_cfg.get("action_templates")
                if action_templates is not None:
                    if not isinstance(action_templates, (list, tuple)) or len(action_templates) == 0:
                        raise ConfigValidationError(
                            "model.env.action_templates must be a non-empty 2D list when provided."
                        )
                    row_lengths: set[int] = set()
                    for row_idx, row in enumerate(action_templates):
                        if not isinstance(row, (list, tuple)) or len(row) == 0:
                            raise ConfigValidationError(
                                "Each model.env.action_templates row must be a non-empty list."
                            )
                        row_lengths.add(len(row))
                        for col_idx, value in enumerate(row):
                            _finite_number(
                                value,
                                field=f"model.env.action_templates[{row_idx}][{col_idx}]",
                            )
                    if len(row_lengths) != 1:
                        raise ConfigValidationError(
                            "model.env.action_templates rows must all have the same length."
                        )

            if "signal_col" in model and model["signal_col"] is not None and not isinstance(model["signal_col"], str):
                raise ConfigValidationError("model.signal_col must be a string when provided.")
            if "action_col" in model and model["action_col"] is not None and not isinstance(model["action_col"], str):
                raise ConfigValidationError("model.action_col must be a string when provided.")

            params = model.get("params", {}) or {}
            if not isinstance(params, dict):
                raise ConfigValidationError("model.params must be a mapping.")
            if model["kind"] in (_RL_SINGLE_ASSET_DQN_KINDS | _RL_PORTFOLIO_DQN_KINDS):
                bad_keys = sorted(set(params) & _PPO_ONLY_RL_PARAM_KEYS)
                if bad_keys:
                    raise ConfigValidationError(
                        "DQN agents do not accept PPO-only model.params keys: "
                        + ", ".join(bad_keys)
                    )
            if model["kind"] in {"ppo_agent", "ppo_portfolio_agent"}:
                bad_keys = sorted(set(params) & _DQN_ONLY_RL_PARAM_KEYS)
                if bad_keys:
                    raise ConfigValidationError(
                        "PPO agents do not accept DQN-only model.params keys: "
                        + ", ".join(bad_keys)
                    )
            if "total_timesteps" in params:
                _positive_int(params["total_timesteps"], field="model.params.total_timesteps")
            if "policy" in params and not isinstance(params["policy"], str):
                raise ConfigValidationError("model.params.policy must be a string.")
            if "device" in params and not isinstance(params["device"], str):
                raise ConfigValidationError("model.params.device must be a string.")
            extractor_cfg = params.get("extractor")
            if extractor_cfg is not None:
                if not isinstance(extractor_cfg, dict):
                    raise ConfigValidationError("model.params.extractor must be a mapping when provided.")
                kind = extractor_cfg.get("kind", "flatten")
                if kind not in _RL_EXTRACTOR_KINDS:
                    raise ConfigValidationError(
                        "model.params.extractor.kind must be one of: flatten, cnn1d, lstm, transformer."
                    )
                for key in ("features_dim", "hidden_dim", "num_layers", "num_heads"):
                    if key in extractor_cfg:
                        _positive_int(extractor_cfg[key], field=f"model.params.extractor.{key}")
                if "dropout" in extractor_cfg:
                    dropout = _finite_number(
                        extractor_cfg["dropout"],
                        field="model.params.extractor.dropout",
                    )
                    if not 0.0 <= dropout < 1.0:
                        raise ConfigValidationError("model.params.extractor.dropout must be in [0,1).")

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
    if train_size is not None:
        _positive_int(train_size, field="model.split.train_size")
    if train_size is None:
        train_frac = float(train_frac)
        if not 0.0 < train_frac < 1.0:
            raise ConfigValidationError(
                "model.split.train_frac must be in (0,1) when train_size is not provided."
            )

    _positive_int(split.get("test_size", 63), field="model.split.test_size")

    step_size = split.get("step_size")
    if step_size is not None:
        _positive_int(step_size, field="model.split.step_size")

    expanding = split.get("expanding", True)
    if not isinstance(expanding, bool):
        raise ConfigValidationError("model.split.expanding must be boolean.")

    max_folds = split.get("max_folds")
    if max_folds is not None:
        _positive_int(max_folds, field="model.split.max_folds")

    if method == "purged":
        _non_negative_int(split.get("purge_bars", 0), field="model.split.purge_bars")
        _non_negative_int(split.get("embargo_bars", 0), field="model.split.embargo_bars")


def _model_emitted_columns(model: dict[str, Any]) -> dict[str, str]:
    kind = str(model.get("kind", "none"))
    if kind in _CLASSIFIER_MODEL_KINDS:
        return {"pred_prob_col": str(model.get("pred_prob_col") or "pred_prob")}
    if kind in _FORECASTER_MODEL_KINDS:
        return {
            "pred_ret_col": str(model.get("pred_ret_col") or "pred_ret"),
            "pred_prob_col": str(model.get("pred_prob_col") or "pred_prob"),
        }
    if kind in RL_MODEL_KINDS:
        return {
            "signal_col": str(model.get("signal_col") or "signal_rl"),
            "action_col": str(model.get("action_col") or "action_rl"),
        }
    return {}


def validate_model_stages_block(model_stages: Any) -> None:
    if model_stages in (None, []):
        return
    if not isinstance(model_stages, list) or not model_stages:
        raise ConfigValidationError("model_stages must be a non-empty list of model stage mappings.")

    seen_names: set[str] = set()
    seen_stage_numbers: set[int] = set()
    seen_output_columns: dict[str, str] = {}
    enabled_stage_count = 0
    for idx, raw_stage in enumerate(model_stages):
        field_prefix = f"model_stages[{idx}]"
        if not isinstance(raw_stage, dict):
            raise ConfigValidationError(f"{field_prefix} must be a mapping.")
        stage = dict(raw_stage)
        name = stage.get("name", f"stage_{idx + 1}")
        if not isinstance(name, str) or not name.strip():
            raise ConfigValidationError(f"{field_prefix}.name must be a non-empty string.")
        if name in seen_names:
            raise ConfigValidationError(f"model_stages names must be unique; duplicate name '{name}'.")
        seen_names.add(name)

        enabled = stage.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ConfigValidationError(f"{field_prefix}.enabled must be boolean.")
        stage_number = stage.get("stage", idx + 1)
        _positive_int(stage_number, field=f"{field_prefix}.stage")
        if int(stage_number) in seen_stage_numbers:
            raise ConfigValidationError(
                f"model_stages stage order must be unique; duplicate stage={stage_number}."
            )
        seen_stage_numbers.add(int(stage_number))
        if not enabled:
            continue
        enabled_stage_count += 1

        kind = str(stage.get("kind", "none"))
        if kind == "none":
            raise ConfigValidationError(f"{field_prefix}.kind must not be 'none'.")
        if kind in RL_MODEL_KINDS or kind in PORTFOLIO_MODEL_KINDS:
            raise ConfigValidationError(
                "model_stages currently supports only forecasting/classification stages, "
                f"not '{kind}'."
            )

        validate_model_block(stage)

        for output_field, column in _model_emitted_columns(stage).items():
            previous_stage = seen_output_columns.get(column)
            if previous_stage is not None:
                raise ConfigValidationError(
                    f"{field_prefix}.{output_field} resolves to duplicate emitted column '{column}' "
                    f"already used by stage '{previous_stage}'. Set explicit stage-specific output columns."
                )
            seen_output_columns[column] = name
    if enabled_stage_count == 0:
        raise ConfigValidationError("model_stages must contain at least one entry with enabled=true.")


def validate_signals_block(signals: dict[str, Any]) -> None:
    if "kind" not in signals:
        raise ConfigValidationError("signals.kind is required.")
    if not isinstance(signals["kind"], str):
        raise ConfigValidationError("signals.kind must be a string.")
    if signals["kind"] != "none" and signals["kind"] not in SIGNAL_REGISTRY:
        raise ConfigValidationError(f"Unknown signals kind: {signals['kind']}")
    params = signals.get("params", {}) or {}
    if not isinstance(params, dict):
        raise ConfigValidationError("signals.params must be a mapping when provided.")
    if "signal_name" in params:
        raise ConfigValidationError("signals.params.signal_name is no longer supported; use signals.params.signal_col.")
    if "signal_col" in params and params["signal_col"] is not None and not isinstance(params["signal_col"], str):
        raise ConfigValidationError("signals.params.signal_col must be a string.")
    if signals["kind"] == "probability_threshold":
        for key in ("prob_col", "base_signal_col"):
            if key in params and params[key] is not None and not isinstance(params[key], str):
                raise ConfigValidationError(f"signals.params.{key} must be a string.")
        bounds: dict[str, float] = {}
        for key in ("upper", "lower", "upper_exit", "lower_exit"):
            if key in params and params[key] is not None:
                value = _finite_number(params[key], field=f"signals.params.{key}")
                if not 0.0 < value < 1.0:
                    raise ConfigValidationError(f"signals.params.{key} must be in (0,1).")
                bounds[key] = value
        upper = bounds.get("upper", 0.55)
        lower = bounds.get("lower", 0.45)
        upper_exit = bounds.get("upper_exit", upper)
        lower_exit = bounds.get("lower_exit", lower)
        if not lower <= lower_exit <= upper_exit <= upper:
            raise ConfigValidationError(
                "signals.params for probability_threshold must satisfy lower <= lower_exit <= upper_exit <= upper."
            )
    if signals["kind"] == "probability_vol_adjusted":
        for key in ("prob_col", "vol_col"):
            if key in params and params[key] is not None and not isinstance(params[key], str):
                raise ConfigValidationError(f"signals.params.{key} must be a string.")
        prob_center = _finite_number(params.get("prob_center", 0.5), field="signals.params.prob_center")
        if not 0.0 < prob_center < 1.0:
            raise ConfigValidationError("signals.params.prob_center must be in (0,1).")
        vol_target = _finite_number(params.get("vol_target", 0.001), field="signals.params.vol_target")
        if vol_target <= 0:
            raise ConfigValidationError("signals.params.vol_target must be > 0.")
        clip = _finite_number(params.get("clip", 1.0), field="signals.params.clip")
        if clip <= 0:
            raise ConfigValidationError("signals.params.clip must be > 0.")
        vol_floor = _finite_number(params.get("vol_floor", 1e-6), field="signals.params.vol_floor")
        if vol_floor <= 0:
            raise ConfigValidationError("signals.params.vol_floor must be > 0.")
        min_signal_abs = _finite_number(
            params.get("min_signal_abs", 0.0),
            field="signals.params.min_signal_abs",
        )
        if min_signal_abs < 0:
            raise ConfigValidationError("signals.params.min_signal_abs must be >= 0.")
        if min_signal_abs > clip:
            raise ConfigValidationError("signals.params.min_signal_abs must be <= signals.params.clip.")
        upper = params.get("upper")
        lower = params.get("lower")
        if upper is not None:
            upper = _finite_number(upper, field="signals.params.upper")
            if not 0.0 < upper < 1.0:
                raise ConfigValidationError("signals.params.upper must be in (0,1).")
        if lower is not None:
            lower = _finite_number(lower, field="signals.params.lower")
            if not 0.0 < lower < 1.0:
                raise ConfigValidationError("signals.params.lower must be in (0,1).")
        if upper is None and lower is not None:
            upper = prob_center + (prob_center - lower)
        elif lower is None and upper is not None:
            lower = prob_center - (upper - prob_center)
        if upper is not None and lower is not None and not lower < prob_center < upper:
            raise ConfigValidationError(
                "signals.params must satisfy lower < prob_center < upper for probability_vol_adjusted."
            )
        activation_filters = params.get("activation_filters")
        if activation_filters is not None:
            if not isinstance(activation_filters, list):
                raise ConfigValidationError("signals.params.activation_filters must be a list when provided.")
            allowed_ops = {"gt", "ge", "lt", "le"}
            for idx, raw_filter in enumerate(activation_filters):
                if not isinstance(raw_filter, dict):
                    raise ConfigValidationError(
                        f"signals.params.activation_filters[{idx}] must be a mapping."
                    )
                col = raw_filter.get("col")
                if not isinstance(col, str) or not col:
                    raise ConfigValidationError(
                        f"signals.params.activation_filters[{idx}].col must be a non-empty string."
                    )
                op = str(raw_filter.get("op", "ge"))
                if op not in allowed_ops:
                    raise ConfigValidationError(
                        f"signals.params.activation_filters[{idx}].op must be one of {sorted(allowed_ops)}."
                    )
                if "value" not in raw_filter:
                    raise ConfigValidationError(
                        f"signals.params.activation_filters[{idx}].value is required."
                    )
                _finite_number(
                    raw_filter.get("value"),
                    field=f"signals.params.activation_filters[{idx}].value",
                )
                use_abs = raw_filter.get("use_abs", False)
                if not isinstance(use_abs, bool):
                    raise ConfigValidationError(
                        f"signals.params.activation_filters[{idx}].use_abs must be boolean."
                    )


def validate_risk_block(risk: dict[str, Any]) -> None:
    cpt = _finite_number(risk.get("cost_per_turnover", 0.0), field="risk.cost_per_turnover")
    if cpt < 0:
        raise ConfigValidationError("risk.cost_per_turnover must be >= 0.")
    spt = _finite_number(
        risk.get("slippage_per_turnover", 0.0),
        field="risk.slippage_per_turnover",
    )
    if spt < 0:
        raise ConfigValidationError("risk.slippage_per_turnover must be >= 0.")
    tv = risk.get("target_vol")
    if tv is not None and _finite_number(tv, field="risk.target_vol") <= 0:
        raise ConfigValidationError("risk.target_vol must be > 0 or null.")
    max_lev = _finite_number(risk.get("max_leverage", 3.0), field="risk.max_leverage")
    if max_lev <= 0:
        raise ConfigValidationError("risk.max_leverage must be > 0.")
    dd = risk.get("dd_guard", {})
    if not isinstance(dd, dict):
        raise ConfigValidationError("risk.dd_guard must be a mapping.")
    if "enabled" in dd and not isinstance(dd.get("enabled"), bool):
        raise ConfigValidationError("risk.dd_guard.enabled must be boolean.")
    max_drawdown = _finite_number(dd.get("max_drawdown", 0.2), field="risk.dd_guard.max_drawdown")
    if max_drawdown <= 0:
        raise ConfigValidationError("risk.dd_guard.max_drawdown must be > 0.")
    _non_negative_int(dd.get("cooloff_bars", 0), field="risk.dd_guard.cooloff_bars")
    rearm_drawdown = _finite_number(
        dd.get("rearm_drawdown", max_drawdown),
        field="risk.dd_guard.rearm_drawdown",
    )
    if rearm_drawdown <= 0:
        raise ConfigValidationError("risk.dd_guard.rearm_drawdown must be > 0.")
    if rearm_drawdown > max_drawdown:
        raise ConfigValidationError(
            "risk.dd_guard.rearm_drawdown must be <= risk.dd_guard.max_drawdown."
        )


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
    _non_negative_int(backtest.get("min_holding_bars", 0), field="backtest.min_holding_bars")
    subset = str(backtest.get("subset", "full"))
    if subset not in {"full", "test"}:
        raise ConfigValidationError("backtest.subset must be 'full' or 'test'.")


def validate_portfolio_block(portfolio: dict[str, Any]) -> None:
    if not isinstance(portfolio.get("enabled", False), bool):
        raise ConfigValidationError("portfolio.enabled must be boolean.")
    construction = portfolio.get("construction", "signal_weights")
    if construction not in {"signal_weights", "mean_variance"}:
        raise ConfigValidationError("portfolio.construction must be 'signal_weights' or 'mean_variance'.")
    if _finite_number(portfolio.get("gross_target", 1.0), field="portfolio.gross_target") <= 0:
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
    if _finite_number(portfolio.get("risk_aversion", 0.0), field="portfolio.risk_aversion") < 0:
        raise ConfigValidationError("portfolio.risk_aversion must be >= 0.")
    if _finite_number(portfolio.get("trade_aversion", 0.0), field="portfolio.trade_aversion") < 0:
        raise ConfigValidationError("portfolio.trade_aversion must be >= 0.")
    constraints_cfg = portfolio.get("constraints", {})
    if not isinstance(constraints_cfg, dict):
        raise ConfigValidationError("portfolio.constraints must be a mapping.")
    constraints_cfg = dict(constraints_cfg or {})
    min_weight = _finite_number(
        constraints_cfg.get("min_weight", -1.0),
        field="portfolio.constraints.min_weight",
    )
    max_weight = _finite_number(
        constraints_cfg.get("max_weight", 1.0),
        field="portfolio.constraints.max_weight",
    )
    max_gross_leverage = _finite_number(
        constraints_cfg.get("max_gross_leverage", 1.0),
        field="portfolio.constraints.max_gross_leverage",
    )
    target_net_exposure = _finite_number(
        constraints_cfg.get("target_net_exposure", 0.0),
        field="portfolio.constraints.target_net_exposure",
    )
    turnover_limit_raw = constraints_cfg.get("turnover_limit")
    turnover_limit = (
        None
        if turnover_limit_raw is None
        else _finite_number(turnover_limit_raw, field="portfolio.constraints.turnover_limit")
    )
    group_caps_raw = constraints_cfg.get("group_max_exposure", {})
    if not isinstance(group_caps_raw, dict):
        raise ConfigValidationError("portfolio.constraints.group_max_exposure must be a mapping.")
    group_caps = {}
    for group, cap in dict(group_caps_raw or {}).items():
        if not isinstance(group, str):
            raise ConfigValidationError(
                "portfolio.constraints.group_max_exposure keys must be strings."
            )
        group_caps[group] = _finite_number(
            cap,
            field=f"portfolio.constraints.group_max_exposure[{group}]",
        )
    from src.portfolio.constraints import PortfolioConstraints

    try:
        PortfolioConstraints(
            min_weight=min_weight,
            max_weight=max_weight,
            max_gross_leverage=max_gross_leverage,
            target_net_exposure=target_net_exposure,
            turnover_limit=turnover_limit,
            group_max_exposure=group_caps or None,
        )
    except ValueError as exc:
        raise ConfigValidationError(str(exc)) from exc
    if not isinstance(portfolio.get("asset_groups", {}), dict):
        raise ConfigValidationError("portfolio.asset_groups must be a mapping.")
    for asset, group in portfolio.get("asset_groups", {}).items():
        if not isinstance(asset, str) or not isinstance(group, str):
            raise ConfigValidationError("portfolio.asset_groups must map str -> str.")


def validate_monitoring_block(monitoring: dict[str, Any]) -> None:
    if not isinstance(monitoring.get("enabled", False), bool):
        raise ConfigValidationError("monitoring.enabled must be boolean.")
    if _finite_number(monitoring.get("psi_threshold", 0.2), field="monitoring.psi_threshold") < 0:
        raise ConfigValidationError("monitoring.psi_threshold must be >= 0.")
    n_bins = monitoring.get("n_bins", 10)
    if not isinstance(n_bins, int) or n_bins <= 1:
        raise ConfigValidationError("monitoring.n_bins must be an integer > 1.")


def validate_execution_block(execution: dict[str, Any]) -> None:
    if not isinstance(execution.get("enabled", False), bool):
        raise ConfigValidationError("execution.enabled must be boolean.")
    if execution.get("mode", "paper") != "paper":
        raise ConfigValidationError("execution.mode currently supports only 'paper'.")
    if _finite_number(execution.get("capital", 0.0), field="execution.capital") <= 0:
        raise ConfigValidationError("execution.capital must be > 0.")
    if not isinstance(execution.get("price_col", "close"), str):
        raise ConfigValidationError("execution.price_col must be a string.")
    if _finite_number(
        execution.get("min_trade_notional", 0.0),
        field="execution.min_trade_notional",
    ) < 0:
        raise ConfigValidationError("execution.min_trade_notional must be >= 0.")
    current_weights = execution.get("current_weights", {})
    if not isinstance(current_weights, dict):
        raise ConfigValidationError("execution.current_weights must be a mapping.")
    for asset, value in dict(current_weights or {}).items():
        if not isinstance(asset, str):
            raise ConfigValidationError("execution.current_weights keys must be strings.")
        _finite_number(value, field=f"execution.current_weights[{asset}]")
    current_prices = execution.get("current_prices", {})
    if not isinstance(current_prices, dict):
        raise ConfigValidationError("execution.current_prices must be a mapping.")
    for asset, value in dict(current_prices or {}).items():
        if not isinstance(asset, str):
            raise ConfigValidationError("execution.current_prices keys must be strings.")
        if _finite_number(value, field=f"execution.current_prices[{asset}]") <= 0:
            raise ConfigValidationError(f"execution.current_prices[{asset}] must be > 0.")


def validate_logging_block(logging_cfg: dict[str, Any]) -> None:
    if not isinstance(logging_cfg.get("enabled", False), bool):
        raise ConfigValidationError("logging.enabled must be boolean.")
    if not isinstance(logging_cfg.get("run_name", ""), str) or not logging_cfg.get("run_name", "").strip():
        raise ConfigValidationError("logging.run_name must be a non-empty string.")
    if not isinstance(logging_cfg.get("output_dir", ""), str) or not logging_cfg.get("output_dir", "").strip():
        raise ConfigValidationError("logging.output_dir must be a non-empty string.")
    stage_tails = logging_cfg.get("stage_tails", {})
    if not isinstance(stage_tails, dict):
        raise ConfigValidationError("logging.stage_tails must be a mapping.")
    for key in ("enabled", "stdout", "report"):
        if key in stage_tails and not isinstance(stage_tails.get(key), bool):
            raise ConfigValidationError(f"logging.stage_tails.{key} must be boolean.")
    for key in ("limit", "max_columns", "max_assets"):
        if key in stage_tails:
            if isinstance(stage_tails.get(key), bool) or not isinstance(stage_tails.get(key), int):
                raise ConfigValidationError(f"logging.stage_tails.{key} must be a positive integer.")
            if int(stage_tails.get(key)) <= 0:
                raise ConfigValidationError(f"logging.stage_tails.{key} must be > 0.")


def validate_resolved_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """
    Validate all top-level blocks and normalize the runtime sub-config.
    """
    validate_data_block(cfg["data"])
    validate_features_block(cfg["features"])
    validate_model_stages_block(cfg.get("model_stages"))
    validate_model_block(cfg["model"])
    validate_signals_block(cfg["signals"])
    validate_risk_block(cfg["risk"])
    validate_backtest_block(cfg["backtest"])
    validate_portfolio_block(cfg["portfolio"])
    validate_monitoring_block(cfg["monitoring"])
    validate_execution_block(cfg["execution"])
    validate_logging_block(cfg["logging"])
    cfg["runtime"] = validate_runtime_block(dict(cfg.get("runtime", {}) or {}))

    model_kind = str(cfg["model"].get("kind", "none"))
    if model_kind in RL_MODEL_KINDS:
        expected_signal_col = str(cfg["model"].get("signal_col") or "signal_rl")
        if str(cfg["signals"].get("kind", "none")) != "none":
            raise ConfigValidationError("RL model kinds require signals.kind='none'.")
        if str(cfg["backtest"].get("signal_col")) != expected_signal_col:
            raise ConfigValidationError(
                "RL backtests must use the signal column emitted by the agent "
                f"(expected backtest.signal_col='{expected_signal_col}')."
            )
        if bool(cfg["portfolio"].get("enabled", False)) and str(
            cfg["portfolio"].get("construction", "signal_weights")
        ) != "signal_weights":
            raise ConfigValidationError("RL runs with portfolio.enabled=true require portfolio.construction='signal_weights'.")
        if model_kind in PORTFOLIO_MODEL_KINDS:
            if not bool(cfg["portfolio"].get("enabled", False)):
                raise ConfigValidationError("Portfolio RL model kinds require portfolio.enabled=true.")
            if str(cfg["data"].get("alignment", "inner")) != "inner":
                raise ConfigValidationError("Portfolio RL model kinds currently require data.alignment='inner'.")
        if not bool(cfg["portfolio"].get("enabled", False)) and cfg["risk"].get("target_vol") is not None:
            raise ConfigValidationError("Single-asset RL backtests currently require risk.target_vol=null.")
    if str(cfg["backtest"].get("subset", "full")) == "test" and model_kind == "none":
        raise ConfigValidationError("backtest.subset='test' requires a model that emits an OOS boundary.")
    return cfg


__all__ = [
    "ConfigValidationError",
    "validate_backtest_block",
    "validate_data_block",
    "validate_execution_block",
    "validate_logging_block",
    "validate_features_block",
    "validate_model_block",
    "validate_model_stages_block",
    "validate_monitoring_block",
    "validate_portfolio_block",
    "validate_resolved_config",
    "validate_risk_block",
    "validate_runtime_block",
    "validate_signals_block",
]
