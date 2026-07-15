from __future__ import annotations

import math
import re
from typing import Any

from src.intraday import validate_intraday_normalization_policy
from src.utils.config_kinds import (
    FEATURE_KINDS,
    MODEL_KINDS,
    PORTFOLIO_MODEL_KINDS,
    RL_MODEL_KINDS,
    SIGNAL_KINDS,
    TARGET_KINDS,
)
from src.utils.repro import RuntimeConfigError, validate_runtime_config
from src.signals.panel.global_session_relay_laggard import GLOBAL_SESSION_RELAY_ENABLED_MODULES

_RL_SINGLE_ASSET_DQN_KINDS = {"dqn_agent"}
_RL_PORTFOLIO_DQN_KINDS = {"dqn_portfolio_agent"}
_RL_EXTRACTOR_KINDS = {"flatten", "cnn1d", "lstm", "transformer"}
_CLASSIFIER_MODEL_KINDS = {
    "elastic_net_clf",
    "lightgbm_clf",
    "logistic_regression_clf",
    "xgboost_clf",
}
_EMBEDDING_MODEL_KINDS = {"event_transformer_encoder"}
_DEEP_FORECASTER_MODEL_KINDS = {"lstm_forecaster", "patchtst_forecaster", "tft_forecaster"}
_FOUNDATION_FORECASTER_MODEL_KINDS = {
    "chronos_2_forecaster",
    "chronos_bolt_forecaster",
    "timesfm_1p0_200m_forecaster",
    "timesfm_2p5_200m_forecaster",
}
_EXPERIMENTAL_DISCOVERY_MODEL_KINDS = {"tsfresh_extrema_feature_discovery"}
_FORECASTER_MODEL_KINDS = {
    "sarimax_forecaster",
    "garch_forecaster",
    "lightgbm_regressor",
    "xgboost_regressor",
    *_DEEP_FORECASTER_MODEL_KINDS,
    *_FOUNDATION_FORECASTER_MODEL_KINDS,
}
_REGRESSION_TARGET_KINDS = {
    "future_return_regression",
    "volatility_normalized_future_return",
    "risk_adjusted_future_return",
    "r_multiple_regression",
    "mfe_regression",
    "mae_regression",
    "mfe_mae_ratio_regression",
    "downside_adjusted_future_return",
    "future_trend_slope",
    "future_path_efficiency",
    "excess_return_regression",
    "residual_return_regression",
    "future_range_regression",
    "future_realized_volatility",
    "future_drawdown_regression",
}
_POST_MODEL_TARGET_KINDS = {"path_dependent_r"}
_GARCH_OVERLAY_COMPATIBLE_MODEL_KINDS = {
    "elastic_net_clf",
    "lightgbm_clf",
    "logistic_regression_clf",
    "xgboost_clf",
    "lightgbm_regressor",
    "xgboost_regressor",
    "sarimax_forecaster",
    "lstm_forecaster",
    "patchtst_forecaster",
    "tft_forecaster",
    *_FOUNDATION_FORECASTER_MODEL_KINDS,
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
_FEATURE_SELECTOR_OPERATORS = {"exact", "startswith", "endswith", "contains", "regex"}
_FEATURE_SELECTOR_FAMILIES = {
    "returns_lags",
    "volatility",
    "trend",
    "momentum",
    "regime",
    "session_time",
    "atr_adx_range",
    "cross_asset",
}
_FEATURE_SELECTOR_PROFILES = {
    "ftmo_fx_intraday_balanced_v1",
    "ftmo_fx_intraday_regime_v1",
    "ftmo_fx_intraday_momentum_v1",
}
_FEATURE_TRANSFORM_HELPERS = {
    "between_flag",
    "crossing_flag",
    "difference",
    "lag",
    "ratio",
    "reciprocal",
    "rising_flag",
    "rolling_clip",
    "rolling_linear_regression",
    "rolling_mean",
    "rolling_std",
    "rolling_sum",
    "rolling_zscore",
    "rms",
    "slope",
    "threshold_flag",
}
_FEATURE_NORMALIZATION_HELPERS = {
    "atr_distances",
    "atr_scaled_distance",
    "range_position",
    "realized_vol_percentile",
    "returns",
    "robust_zscore",
    "rolling_beta_residual",
    "rolling_percent_rank",
    "rolling_zscores",
    "volatility",
    "volatility_scaled_return",
    "volume_relative",
}
_TARGET_OUTPUT_KEYS = {
    "label_col",
    "fwd_col",
    "raw_fwd_col",
    "normalizer_col",
    "risk_distance_col",
    "realized_vol_col",
    "mfe_col",
    "mae_col",
    "beta_col",
    "benchmark_fwd_col",
    "event_ret_col",
    "candidate_out_col",
    "r_col",
    "oriented_r_col",
    "trade_r_col",
    "trade_r_clipped_col",
    "entry_price_col",
    "exit_price_col",
    "stop_price_col",
    "take_profit_price_col",
    "exit_reason_col",
    "bars_held_col",
    "hit_step_col",
    "hit_type_col",
    "meta_candidate_col",
    "gross_return_col",
    "net_return_col",
    "gross_r_col",
    "net_r_col",
    "mfe_r_col",
    "mae_r_col",
    "holding_bars_col",
    "positive_label_col",
    "min_025_label_col",
    "min_050_label_col",
    "min_100_label_col",
    "time_to_mfe_col",
    "time_to_mae_col",
    "upper_barrier_col",
    "lower_barrier_col",
    "meta_side_col",
    "oriented_ret_col",
    "vol_source_col",
}
_MODEL_OUTPUT_KEYS = {
    "pred_prob_col",
    "pred_raw_prob_col",
    "pred_ret_col",
    "pred_is_oos_col",
    "returns_input_col",
    "signal_col",
    "action_col",
}


def _validate_foundation_forecaster_params(kind: str, params: dict[str, Any]) -> None:
    if not isinstance(params, dict):
        raise ConfigValidationError("model.params must be a mapping.")
    for key in ("source_col", "context_col", "source_kind", "source_returns_type", "model_id", "checkpoint", "device_map", "torch_dtype", "backend", "freq"):
        value = params.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ConfigValidationError(f"model.params.{key} must be a non-empty string when provided.")
    source_kind = params.get("source_kind")
    if source_kind is not None and str(source_kind) not in {"price", "returns"}:
        raise ConfigValidationError("model.params.source_kind must be one of: price, returns.")
    source_returns_type = params.get("source_returns_type")
    if source_returns_type is not None and str(source_returns_type) not in {"simple", "log"}:
        raise ConfigValidationError("model.params.source_returns_type must be one of: simple, log.")
    for key in ("lookback", "min_context", "prediction_length", "batch_size", "max_context", "max_horizon"):
        if key in params and params[key] is not None:
            _positive_int(params[key], field=f"model.params.{key}")
    if "lookback" in params and "min_context" in params and int(params["min_context"]) > int(params["lookback"]):
        raise ConfigValidationError("model.params.min_context must be <= model.params.lookback.")
    quantiles = params.get("quantiles")
    if quantiles is not None:
        if not isinstance(quantiles, (list, tuple)) or not quantiles:
            raise ConfigValidationError("model.params.quantiles must be a non-empty list.")
        seen: set[float] = set()
        for idx, item in enumerate(quantiles):
            q = _finite_number(item, field=f"model.params.quantiles[{idx}]")
            if not 0.0 < q < 1.0:
                raise ConfigValidationError("model.params.quantiles values must be within (0,1).")
            if q in seen:
                raise ConfigValidationError("model.params.quantiles values must be unique.")
            seen.add(q)
    if kind.startswith("timesfm_"):
        if "frequency" in params:
            frequency = params["frequency"]
            if isinstance(frequency, bool) or not isinstance(frequency, int) or frequency not in {0, 1, 2}:
                raise ConfigValidationError("model.params.frequency must be one of: 0, 1, 2.")
        for key in (
            "normalize_inputs",
            "use_continuous_quantile_head",
            "force_flip_invariance",
            "infer_is_positive",
            "fix_quantile_crossing",
        ):
            if key in params and not isinstance(params[key], bool):
                raise ConfigValidationError(f"model.params.{key} must be boolean.")


def _chronos2_target_output_columns(target: dict[str, Any]) -> set[str]:
    columns = {
        str(value)
        for key, value in target.items()
        if key in _TARGET_OUTPUT_KEYS and isinstance(value, str) and value.strip()
    }
    outputs = target.get("outputs", {}) or {}
    if isinstance(outputs, dict):
        columns.update(
            str(value)
            for key, value in outputs.items()
            if key in _TARGET_OUTPUT_KEYS and isinstance(value, str) and value.strip()
        )
    return columns


def _chronos2_prediction_output_columns(model: dict[str, Any]) -> set[str]:
    output_keys = {"pred_ret_col", "pred_prob_col", "pred_raw_prob_col", "pred_is_oos_col"}
    outputs = model.get("outputs", {}) or {}
    columns = {
        str(value)
        for key, value in dict(outputs).items()
        if key in output_keys and isinstance(value, str) and value.strip()
    }
    columns.update(
        str(model[key])
        for key in output_keys
        if isinstance(model.get(key), str) and str(model[key]).strip()
    )
    columns.update({"pred_ret", "pred_prob", "pred_is_oos"})
    return columns


def _validate_chronos2_covariate_contract(model: dict[str, Any], target: dict[str, Any]) -> None:
    """Validate the explicit part of Chronos-2's past-covariate contract."""
    use_features = model.get("use_features", False)
    if not isinstance(use_features, bool):
        raise ConfigValidationError("model.use_features must be boolean for chronos_2_forecaster.")

    feature_cols = model.get("feature_cols")
    if feature_cols is not None:
        duplicates = sorted({column for column in feature_cols if feature_cols.count(column) > 1})
        if duplicates:
            raise ConfigValidationError(
                "chronos_2_forecaster model.feature_cols must not contain duplicates: "
                f"{duplicates}."
            )

    params = dict(model.get("params", {}) or {})
    source_col = str(
        params.get("source_col")
        or params.get("context_col")
        or target.get("price_col", "close")
    )
    target_outputs = _chronos2_target_output_columns(target)
    explicit_features = [str(column) for column in list(feature_cols or [])]
    invalid_target_features = sorted(set(explicit_features) & target_outputs)
    if invalid_target_features:
        raise ConfigValidationError(
            "chronos_2_forecaster model.feature_cols cannot contain target or label output columns: "
            f"{invalid_target_features}."
        )

    if not use_features:
        return

    prediction_outputs = _chronos2_prediction_output_columns(model)
    excluded = {source_col, *target_outputs, *prediction_outputs}
    if feature_cols is not None and not model.get("feature_selectors"):
        usable_covariates = [column for column in explicit_features if column not in excluded]
        if not usable_covariates:
            raise ConfigValidationError(
                "chronos_2_forecaster with model.use_features=true requires at least one "
                "usable covariate after excluding source and target/prediction outputs."
            )


def _validate_tsfresh_extrema_discovery_params(params: dict[str, Any]) -> None:
    for key in ("high_col", "low_col"):
        value = params.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ConfigValidationError(f"model.params.{key} must be a non-empty string when provided.")

    _positive_int(params.get("window_size", 48), field="model.params.window_size")
    _positive_int(params.get("label_horizon", 8), field="model.params.label_horizon")
    _positive_int(params.get("n_jobs", 1), field="model.params.n_jobs")
    if params.get("chunksize") is not None:
        _positive_int(params.get("chunksize"), field="model.params.chunksize")
    if params.get("n_significant") is not None:
        _positive_int(params.get("n_significant"), field="model.params.n_significant")

    feature_preset = str(params.get("feature_preset", "minimal")).strip().lower()
    if feature_preset not in {"minimal", "efficient", "comprehensive"}:
        raise ConfigValidationError(
            "model.params.feature_preset must be one of: minimal, efficient, comprehensive."
        )

    fdr_level = _finite_number(params.get("fdr_level", 0.05), field="model.params.fdr_level")
    if not 0.0 < fdr_level <= 1.0:
        raise ConfigValidationError("model.params.fdr_level must be in (0,1].")

    if "hypotheses_independent" in params and not isinstance(params.get("hypotheses_independent"), bool):
        raise ConfigValidationError("model.params.hypotheses_independent must be boolean.")
    for key in ("disable_progressbar", "show_warnings"):
        if key in params and not isinstance(params.get(key), bool):
            raise ConfigValidationError(f"model.params.{key} must be boolean.")
    if "include_raw_ohlcv" in params and not isinstance(params.get("include_raw_ohlcv"), bool):
        raise ConfigValidationError("model.params.include_raw_ohlcv must be boolean.")
    kind_to_fc_parameters = params.get("kind_to_fc_parameters")
    if kind_to_fc_parameters is not None:
        if not isinstance(kind_to_fc_parameters, dict):
            raise ConfigValidationError("model.params.kind_to_fc_parameters must be a mapping.")
        for kind_name, calculators in kind_to_fc_parameters.items():
            if not isinstance(kind_name, str) or not kind_name.strip():
                raise ConfigValidationError("model.params.kind_to_fc_parameters keys must be non-empty strings.")
            if not isinstance(calculators, dict):
                raise ConfigValidationError(
                    "model.params.kind_to_fc_parameters values must be mappings of calculator names to parameter specs."
                )
            for calculator_name, raw_spec in calculators.items():
                if not isinstance(calculator_name, str) or not calculator_name.strip():
                    raise ConfigValidationError(
                        "model.params.kind_to_fc_parameters calculator names must be non-empty strings."
                    )
                if raw_spec is None:
                    continue
                if isinstance(raw_spec, dict):
                    continue
                if not isinstance(raw_spec, list):
                    raise ConfigValidationError(
                        "model.params.kind_to_fc_parameters calculator specs must be null, a mapping, or a list of mappings."
                    )
                if any(not isinstance(item, dict) for item in raw_spec):
                    raise ConfigValidationError(
                        "model.params.kind_to_fc_parameters list specs must contain only mappings."
                    )
    if "export_feature_dataset" in params and not isinstance(params.get("export_feature_dataset"), bool):
        raise ConfigValidationError("model.params.export_feature_dataset must be boolean.")
    export_dataset_path = params.get("export_dataset_path")
    if export_dataset_path is not None and (not isinstance(export_dataset_path, str) or not export_dataset_path.strip()):
        raise ConfigValidationError("model.params.export_dataset_path must be a non-empty string when provided.")
    if bool(params.get("export_feature_dataset", False)) and export_dataset_path is None:
        raise ConfigValidationError(
            "model.params.export_dataset_path must be provided when model.params.export_feature_dataset is true."
        )


def _resolve_event_embedding_columns(model: dict[str, Any]) -> list[str]:
    params = dict(model.get("params", {}) or {})
    embedding_dim = int(params.get("embedding_dim", params.get("hidden_dim", 32)))
    embedding_prefix = str(params.get("embedding_prefix", "event_emb"))
    width = max(2, len(str(int(embedding_dim) - 1)))
    return [f"{embedding_prefix}_{idx:0{width}d}" for idx in range(int(embedding_dim))]


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


def _validate_phase_unit(value: Any, *, field: str) -> None:
    if not isinstance(value, str) or value.strip().lower() not in {
        "degrees",
        "degree",
        "deg",
        "radians",
        "radian",
        "rad",
    }:
        raise ConfigValidationError(f"{field} must be one of: degrees, radians.")


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigValidationError(f"{field} must be a positive integer.")
    return value


def _non_negative_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ConfigValidationError(f"{field} must be an integer >= 0.")
    return value


def _validate_string_mapping(
    value: Any,
    *,
    field: str,
    allowed_keys: set[str] | None = None,
) -> dict[str, str]:
    if value in (None, {}):
        return {}
    if not isinstance(value, dict):
        raise ConfigValidationError(f"{field} must be a mapping when provided.")
    out: dict[str, str] = {}
    for key, raw_value in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ConfigValidationError(f"{field} keys must be non-empty strings.")
        if allowed_keys is not None and key not in allowed_keys:
            allowed_display = ", ".join(sorted(allowed_keys))
            raise ConfigValidationError(f"{field}.{key} is not supported. Allowed keys: {allowed_display}.")
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise ConfigValidationError(f"{field}.{key} must be a non-empty string.")
        out[key] = raw_value
    return out


def _validate_string_or_list(value: Any, *, field: str) -> None:
    if isinstance(value, str):
        if not value.strip():
            raise ConfigValidationError(f"{field} must be a non-empty string.")
        return
    if not isinstance(value, list) or not value:
        raise ConfigValidationError(f"{field} must be a non-empty string or list[str].")
    for idx, raw_value in enumerate(value):
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise ConfigValidationError(f"{field}[{idx}] must be a non-empty string.")


def _validate_clock_string(value: Any, *, field: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}", value.strip()):
        raise ConfigValidationError(f"{field} must use HH:MM format.")
    hour, minute = (int(part) for part in value.split(":"))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ConfigValidationError(f"{field} must be a valid HH:MM time.")


def _validate_selector_mapping(value: Any, *, field: str) -> None:
    if not isinstance(value, dict):
        raise ConfigValidationError(f"{field} must be a selector mapping.")
    if len(value) != 1:
        allowed = ", ".join(sorted(_FEATURE_SELECTOR_OPERATORS))
        raise ConfigValidationError(
            f"{field} must contain exactly one selector operator: {allowed}."
        )
    operator, raw_value = next(iter(value.items()))
    if operator not in _FEATURE_SELECTOR_OPERATORS:
        allowed = ", ".join(sorted(_FEATURE_SELECTOR_OPERATORS))
        raise ConfigValidationError(
            f"{field}.{operator} is not supported. Allowed operators: {allowed}."
        )
    _validate_string_or_list(raw_value, field=f"{field}.{operator}")
    if operator == "regex":
        raw_patterns = [raw_value] if isinstance(raw_value, str) else list(raw_value)
        for pattern_idx, pattern in enumerate(raw_patterns):
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ConfigValidationError(
                    f"{field}.regex[{pattern_idx}] is not a valid regex: {exc}"
                ) from exc


def _validate_selector_rule_list(value: Any, *, field: str) -> None:
    if value in (None, []):
        return
    if not isinstance(value, list):
        raise ConfigValidationError(f"{field} must be a list of selector mappings.")
    for idx, raw_rule in enumerate(value):
        rule_field = f"{field}[{idx}]"
        _validate_selector_mapping(raw_rule, field=rule_field)


def _validate_column_ref_or_selector(
    value: dict[str, Any],
    *,
    col_key: str,
    selector_key: str,
    field: str,
) -> None:
    raw_col = value.get(col_key)
    raw_selector = value.get(selector_key)
    has_col = raw_col is not None
    has_selector = raw_selector is not None
    if has_col == has_selector:
        raise ConfigValidationError(f"{field} must define exactly one of {col_key} or {selector_key}.")
    if has_col:
        if not isinstance(raw_col, str) or not raw_col.strip():
            raise ConfigValidationError(f"{field}.{col_key} must be a non-empty string.")
        return
    _validate_selector_mapping(raw_selector, field=f"{field}.{selector_key}")


def _validate_feature_selectors(value: Any, *, field: str) -> None:
    if value in (None, {}):
        return
    if not isinstance(value, dict):
        raise ConfigValidationError(f"{field} must be a mapping when provided.")

    allowed_keys = {"profile", "families", "exact", "include", "exclude", "strict", "drift_filter"}
    unknown = sorted(set(value) - allowed_keys)
    if unknown:
        allowed = ", ".join(sorted(allowed_keys))
        raise ConfigValidationError(f"{field} has unsupported keys: {unknown}. Allowed keys: {allowed}.")

    if "profile" in value:
        profile = value["profile"]
        if not isinstance(profile, str) or not profile.strip():
            raise ConfigValidationError(f"{field}.profile must be a non-empty string.")
        if profile not in _FEATURE_SELECTOR_PROFILES:
            allowed = ", ".join(sorted(_FEATURE_SELECTOR_PROFILES))
            raise ConfigValidationError(
                f"{field}.profile is not supported. Allowed profiles: {allowed}."
            )
    families = value.get("families")
    if families is not None:
        if not isinstance(families, dict):
            raise ConfigValidationError(f"{field}.families must be a mapping when provided.")
        for family, enabled in families.items():
            if family not in _FEATURE_SELECTOR_FAMILIES:
                allowed = ", ".join(sorted(_FEATURE_SELECTOR_FAMILIES))
                raise ConfigValidationError(
                    f"{field}.families.{family} is not supported. Allowed families: {allowed}."
                )
            if not isinstance(enabled, bool):
                raise ConfigValidationError(f"{field}.families.{family} must be boolean.")

    if "exact" in value:
        _validate_string_or_list(value["exact"], field=f"{field}.exact")
    _validate_selector_rule_list(value.get("include"), field=f"{field}.include")
    _validate_selector_rule_list(value.get("exclude"), field=f"{field}.exclude")
    if (
        "profile" not in value
        and value.get("families") in (None, {})
        and "exact" not in value
        and value.get("include") in (None, [])
    ):
        raise ConfigValidationError(f"{field} must define at least one exact column or include rule.")

    strict = value.get("strict", {}) or {}
    if not isinstance(strict, dict):
        raise ConfigValidationError(f"{field}.strict must be a mapping when provided.")
    unknown_strict = sorted(set(strict) - {"min_count"})
    if unknown_strict:
        raise ConfigValidationError(f"{field}.strict has unsupported keys: {unknown_strict}.")
    if "min_count" in strict:
        _non_negative_int(strict["min_count"], field=f"{field}.strict.min_count")

    drift_filter = value.get("drift_filter", {}) or {}
    if drift_filter:
        if not isinstance(drift_filter, dict):
            raise ConfigValidationError(f"{field}.drift_filter must be a mapping when provided.")
        unknown_drift_keys = sorted(
            set(drift_filter)
            - {"enabled", "max_psi", "action", "apply_scope", "family_drift_ratio_threshold"}
        )
        if unknown_drift_keys:
            raise ConfigValidationError(f"{field}.drift_filter has unsupported keys: {unknown_drift_keys}.")
        if "enabled" in drift_filter and not isinstance(drift_filter.get("enabled"), bool):
            raise ConfigValidationError(f"{field}.drift_filter.enabled must be boolean.")
        if "max_psi" in drift_filter:
            max_psi = _finite_number(drift_filter.get("max_psi"), field=f"{field}.drift_filter.max_psi")
            if max_psi <= 0:
                raise ConfigValidationError(f"{field}.drift_filter.max_psi must be > 0.")
        action = str(drift_filter.get("action", "warn"))
        if action not in {"warn", "drop"}:
            raise ConfigValidationError(f"{field}.drift_filter.action must be one of: warn, drop.")
        apply_scope = str(drift_filter.get("apply_scope", "train_only_report"))
        if apply_scope not in {"train_only_report", "train_and_model"}:
            raise ConfigValidationError(
                f"{field}.drift_filter.apply_scope must be one of: train_only_report, train_and_model."
            )
        if "family_drift_ratio_threshold" in drift_filter:
            ratio = _finite_number(
                drift_filter.get("family_drift_ratio_threshold"),
                field=f"{field}.drift_filter.family_drift_ratio_threshold",
            )
            if not 0.0 <= ratio <= 1.0:
                raise ConfigValidationError(
                    f"{field}.drift_filter.family_drift_ratio_threshold must be in [0,1]."
                )


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
        load_paths = storage_for_external_csv.get("load_paths")
        if load_path is not None and load_paths is not None:
            raise ConfigValidationError("Specify either data.storage.load_path or data.storage.load_paths, not both.")
        has_load_path = isinstance(load_path, str) and bool(load_path.strip())
        has_load_paths = isinstance(load_paths, dict) and bool(load_paths)
        allow_missing_load_paths = storage_for_external_csv.get("allow_missing_load_paths", False)
        if "allow_missing_load_paths" in storage_for_external_csv and not isinstance(allow_missing_load_paths, bool):
            raise ConfigValidationError("data.storage.allow_missing_load_paths must be boolean.")
        if not has_load_path and not has_load_paths:
            raise ConfigValidationError(
                "data.storage.load_path or data.storage.load_paths is required when data.source='dukascopy_csv'."
            )
        if load_paths is not None:
            if not isinstance(load_paths, dict) or not load_paths:
                raise ConfigValidationError("data.storage.load_paths must be a non-empty mapping.")
            for asset, path in load_paths.items():
                if not isinstance(asset, str) or not asset.strip():
                    raise ConfigValidationError("data.storage.load_paths keys must be non-empty strings.")
                if not isinstance(path, str) or not path.strip():
                    raise ConfigValidationError("data.storage.load_paths values must be non-empty strings.")
            missing_load_paths = [symbol for symbol in requested_symbols if symbol not in load_paths]
            if missing_load_paths and not bool(allow_missing_load_paths):
                raise ConfigValidationError(
                    f"data.storage.load_paths is missing configured symbols: {missing_load_paths}."
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
        load_paths = storage.get("load_paths")
        if load_path is not None and load_paths is not None:
            raise ConfigValidationError("Specify either data.storage.load_path or data.storage.load_paths, not both.")
        if load_paths is not None:
            if not isinstance(load_paths, dict) or not load_paths:
                raise ConfigValidationError("data.storage.load_paths must be a non-empty mapping.")
            for asset, path in load_paths.items():
                if not isinstance(asset, str) or not asset.strip():
                    raise ConfigValidationError("data.storage.load_paths keys must be non-empty strings.")
                if not isinstance(path, str) or not path.strip():
                    raise ConfigValidationError("data.storage.load_paths values must be non-empty strings.")
        for key in ("raw_dir", "processed_dir"):
            if key in storage and not isinstance(storage[key], str):
                raise ConfigValidationError(f"data.storage.{key} must be a string.")
        for key in ("save_raw", "save_processed"):
            if key in storage and not isinstance(storage[key], bool):
                raise ConfigValidationError(f"data.storage.{key} must be boolean.")
        if "allow_missing_load_paths" in storage and not isinstance(storage["allow_missing_load_paths"], bool):
            raise ConfigValidationError("data.storage.allow_missing_load_paths must be boolean.")


def _validate_roc_long_only_conditions_params(params: dict[str, Any], *, field_prefix: str) -> None:
    nullable_string_keys = {
        "roc_col",
        "regime_vol_ratio_z_col",
        "macro_condition_col",
        "signal_col",
    }
    string_keys = {
        "close_z_col",
        "close_open_ratio_col",
        "mtf_1h_col",
        "mtf_4h_col",
        "is_weekend_col",
        "long_signal_col",
        "score_col",
        "all_conditions_col",
        "vol_adjusted_col",
        "short_signal_col",
        "combined_signal_col",
    }
    for key in nullable_string_keys:
        if key in params and params[key] is not None and not isinstance(params[key], str):
            raise ConfigValidationError(f"{field_prefix}.{key} must be a string or null.")
    for key in string_keys:
        if key in params and not isinstance(params[key], str):
            raise ConfigValidationError(f"{field_prefix}.{key} must be a string.")
    for key in ("roc_window", "vol_short_window", "vol_long_window"):
        if key in params:
            _positive_int(params[key], field=f"{field_prefix}.{key}")
    if "min_score_required" in params:
        _non_negative_int(params["min_score_required"], field=f"{field_prefix}.min_score_required")
    for key in (
        "roc_min",
        "vol_z_min",
        "vol_z_max",
        "close_z_min",
        "close_z_max",
        "close_open_ratio_min",
        "mtf_1h_min",
        "mtf_4h_min",
        "vol_adjustment_strength",
        "min_exposure",
        "max_exposure",
    ):
        if key in params:
            _finite_number(params[key], field=f"{field_prefix}.{key}")
    if float(params.get("vol_z_min", -1.5)) > float(params.get("vol_z_max", 1.75)):
        raise ConfigValidationError(f"{field_prefix}.vol_z_min must be <= {field_prefix}.vol_z_max.")
    if float(params.get("close_z_min", -0.25)) > float(params.get("close_z_max", 2.25)):
        raise ConfigValidationError(f"{field_prefix}.close_z_min must be <= {field_prefix}.close_z_max.")
    if float(params.get("vol_adjustment_strength", 0.9)) < 0.0:
        raise ConfigValidationError(f"{field_prefix}.vol_adjustment_strength must be >= 0.")
    if float(params.get("min_exposure", 0.10)) < 0.0:
        raise ConfigValidationError(f"{field_prefix}.min_exposure must be >= 0.")
    if float(params.get("max_exposure", 1.0)) <= 0.0:
        raise ConfigValidationError(f"{field_prefix}.max_exposure must be > 0.")
    if float(params.get("min_exposure", 0.10)) > float(params.get("max_exposure", 1.0)):
        raise ConfigValidationError(f"{field_prefix}.min_exposure must be <= {field_prefix}.max_exposure.")
    if "require_all_conditions" in params and not isinstance(params["require_all_conditions"], bool):
        raise ConfigValidationError(f"{field_prefix}.require_all_conditions must be boolean.")


def _validate_ppo_adx_stochrsi_trend_params(params: dict[str, Any], *, field_prefix: str) -> None:
    string_keys = {
        "close_col",
        "high_col",
        "low_col",
        "ema_fast_col",
        "ema_slow_col",
        "ppo_col",
        "ppo_signal_col",
        "adx_col",
        "plus_di_col",
        "minus_di_col",
        "atr_col",
        "stoch_k_col",
        "stoch_d_col",
        "signal_col",
        "position_col",
        "entry_long_col",
        "entry_short_col",
        "exit_long_col",
        "exit_short_col",
    }
    for key in string_keys:
        if key in params and (not isinstance(params[key], str) or not params[key].strip()):
            raise ConfigValidationError(f"{field_prefix}.{key} must be a non-empty string.")
    if "mode" in params:
        mode = str(params["mode"])
        if mode not in {"long_only", "short_only", "long_short"}:
            raise ConfigValidationError(
                f"{field_prefix}.mode must be one of: long_only, short_only, long_short."
            )
    if "stoch_entry_mode" in params:
        stoch_entry_mode = str(params["stoch_entry_mode"])
        if stoch_entry_mode not in {"reset", "cross", "reset_or_cross"}:
            raise ConfigValidationError(
                f"{field_prefix}.stoch_entry_mode must be one of: reset, cross, reset_or_cross."
            )
    for key in ("require_adx", "use_atr_trailing_stop"):
        if key in params and not isinstance(params[key], bool):
            raise ConfigValidationError(f"{field_prefix}.{key} must be boolean.")
    for key in (
        "adx_threshold",
        "ppo_slope_threshold",
        "stoch_oversold",
        "stoch_overbought",
        "atr_stop_mult",
        "atr_take_profit_mult",
        "atr_trailing_mult",
    ):
        if key in params:
            value = _finite_number(params[key], field=f"{field_prefix}.{key}")
            if key in {"adx_threshold", "ppo_slope_threshold"} and value < 0.0:
                raise ConfigValidationError(f"{field_prefix}.{key} must be >= 0.")
            if key in {"atr_stop_mult", "atr_take_profit_mult", "atr_trailing_mult"} and value <= 0.0:
                raise ConfigValidationError(f"{field_prefix}.{key} must be > 0.")
    oversold = float(params.get("stoch_oversold", 0.20))
    overbought = float(params.get("stoch_overbought", 0.80))
    if not 0.0 <= oversold <= 1.0:
        raise ConfigValidationError(f"{field_prefix}.stoch_oversold must be in [0,1].")
    if not 0.0 <= overbought <= 1.0:
        raise ConfigValidationError(f"{field_prefix}.stoch_overbought must be in [0,1].")
    if oversold >= overbought:
        raise ConfigValidationError(
            f"{field_prefix}.stoch_oversold must be less than {field_prefix}.stoch_overbought."
        )


def _validate_ema_rms_ppo_vwap_params(params: dict[str, Any], *, field_prefix: str) -> None:
    string_keys = {
        "close_col",
        "atr_col",
        "ema_fast_rms_col",
        "ema_mid_rms_col",
        "ema_slow_rms_col",
        "vwap_col",
        "vwap_rms_col",
        "ppo_col",
        "ppo_signal_col",
        "signal_col",
        "candidate_col",
    }
    for key in string_keys:
        if key in params and (not isinstance(params[key], str) or not params[key].strip()):
            raise ConfigValidationError(f"{field_prefix}.{key} must be a non-empty string.")
    if "mode" in params:
        mode = str(params["mode"])
        if mode not in {"long_only", "short_only", "long_short"}:
            raise ConfigValidationError(
                f"{field_prefix}.mode must be one of: long_only, short_only, long_short."
            )
    for key in ("require_vwap_rms_filter", "require_rms_slope_filter"):
        if key in params and not isinstance(params[key], bool):
            raise ConfigValidationError(f"{field_prefix}.{key} must be boolean.")
    if "max_vwap_distance_atr" in params:
        value = _finite_number(
            params["max_vwap_distance_atr"],
            field=f"{field_prefix}.max_vwap_distance_atr",
        )
        if value <= 0.0:
            raise ConfigValidationError(f"{field_prefix}.max_vwap_distance_atr must be > 0.")
    if "min_rms_slope" in params:
        value = _finite_number(
            params["min_rms_slope"],
            field=f"{field_prefix}.min_rms_slope",
        )
        if value < 0.0:
            raise ConfigValidationError(f"{field_prefix}.min_rms_slope must be >= 0.")


def _validate_vwap_rms_ema_cross_long_params(params: dict[str, Any], *, field_prefix: str) -> None:
    string_keys = {
        "ema_mid_col",
        "ema_slow_col",
        "ema_mid_rms_col",
        "vwap_rms_col",
        "ppo_col",
        "ppo_signal_col",
        "regime_col",
        "short_regime_col",
        "cross_up_col",
        "cross_down_col",
        "ppo_hist_col",
        "ppo_hist_positive_col",
        "ppo_hist_negative_col",
        "ppo_above_signal_col",
        "ppo_below_signal_col",
        "mfi_col",
        "mfi_confirmation_col",
        "long_setup_col",
        "short_setup_col",
        "signal_col",
        "candidate_col",
    }
    for key in string_keys:
        if key in params and (not isinstance(params[key], str) or not params[key].strip()):
            raise ConfigValidationError(f"{field_prefix}.{key} must be a non-empty string.")
    if "mode" in params:
        mode = str(params["mode"])
        if mode not in {"long_only", "short_only", "long_short"}:
            raise ConfigValidationError(
                f"{field_prefix}.mode must be one of: long_only, short_only, long_short."
            )
    for key in (
        "use_ppo_confirmation",
        "use_ema_regime",
        "use_vwap_rms_cross",
        "use_mfi_confirmation",
    ):
        if key in params and not isinstance(params[key], bool):
            raise ConfigValidationError(f"{field_prefix}.{key} must be boolean.")
    if "ppo_hist_min" in params:
        _finite_number(params["ppo_hist_min"], field=f"{field_prefix}.ppo_hist_min")
    mfi_values: dict[str, float] = {}
    for key in ("mfi_lower", "mfi_upper"):
        if key in params:
            mfi_values[key] = _finite_number(params[key], field=f"{field_prefix}.{key}")
    mfi_lower = mfi_values.get("mfi_lower", float(params.get("mfi_lower", 40.0)))
    mfi_upper = mfi_values.get("mfi_upper", float(params.get("mfi_upper", 80.0)))
    if mfi_lower > mfi_upper:
        raise ConfigValidationError(f"{field_prefix}.mfi_lower must be <= {field_prefix}.mfi_upper.")
    if "entry_delay_bars" in params:
        entry_delay = params["entry_delay_bars"]
        if isinstance(entry_delay, bool) or not isinstance(entry_delay, int) or int(entry_delay) < 0:
            raise ConfigValidationError(f"{field_prefix}.entry_delay_bars must be a non-negative integer.")


def _validate_vwap_rms_ema_cross_long_fractal_filter_params(
    params: dict[str, Any],
    *,
    field_prefix: str,
) -> None:
    _validate_vwap_rms_ema_cross_long_params(params, field_prefix=field_prefix)
    for key in ("fractal_col", "fractal_ok_col"):
        if key in params and (not isinstance(params[key], str) or not params[key].strip()):
            raise ConfigValidationError(f"{field_prefix}.{key} must be a non-empty string.")
    if "fractal_max" in params:
        _finite_number(params["fractal_max"], field=f"{field_prefix}.fractal_max")


def _validate_vwap_rms_ema_cross_long_hmm_gate_params(
    params: dict[str, Any],
    *,
    field_prefix: str,
) -> None:
    _validate_vwap_rms_ema_cross_long_params(params, field_prefix=field_prefix)
    for key in ("hmm_regime_col", "hmm_ok_col"):
        if key in params and (not isinstance(params[key], str) or not params[key].strip()):
            raise ConfigValidationError(f"{field_prefix}.{key} must be a non-empty string.")
    if "hmm_min_regime" in params:
        _finite_number(params["hmm_min_regime"], field=f"{field_prefix}.hmm_min_regime")
    hmm_prob_col = params.get("hmm_prob_col")
    hmm_prob_min = params.get("hmm_prob_min")
    if hmm_prob_col is not None and (not isinstance(hmm_prob_col, str) or not hmm_prob_col.strip()):
        raise ConfigValidationError(f"{field_prefix}.hmm_prob_col must be a non-empty string or null.")
    if hmm_prob_min is not None:
        _finite_number(hmm_prob_min, field=f"{field_prefix}.hmm_prob_min")
    if (hmm_prob_col is None) != (hmm_prob_min is None):
        raise ConfigValidationError(
            f"{field_prefix}.hmm_prob_col and {field_prefix}.hmm_prob_min must be set together."
        )


def _validate_stc_roofing_hilbert_params(params: dict[str, Any], *, field_prefix: str) -> None:
    string_keys = {
        "ema_fast_col",
        "ema_slow_col",
        "roofing_col",
        "roofing_slope_col",
        "stc_col",
        "hilbert_cycle_ok_col",
        "hilbert_amplitude_rising_col",
        "zscore_momentum_col",
        "adx_col",
        "volatility_regime_col",
        "long_candidate_col",
        "short_candidate_col",
        "signal_col",
        "candidate_col",
        "hilbert_long_candidate_col",
        "hilbert_short_candidate_col",
        "hilbert_signal_col",
        "ema_bullish_col",
        "ema_bearish_col",
        "roofing_positive_col",
        "roofing_negative_col",
        "roofing_slope_positive_col",
        "roofing_slope_negative_col",
        "stc_cross_up_col",
        "stc_cross_down_col",
        "hilbert_pass_col",
        "zscore_long_pass_col",
        "zscore_short_pass_col",
        "adx_pass_col",
        "volatility_pass_col",
    }
    for key in string_keys:
        if key in params and (not isinstance(params[key], str) or not params[key].strip()):
            raise ConfigValidationError(f"{field_prefix}.{key} must be a non-empty string.")
    if "mode" in params:
        mode = str(params["mode"])
        if mode not in {"long_only", "short_only", "long_short"}:
            raise ConfigValidationError(
                f"{field_prefix}.mode must be one of: long_only, short_only, long_short."
            )
    for key in (
        "use_ema_regime",
        "use_roofing_filter",
        "use_roofing_slope",
        "use_hilbert_filter",
        "use_zscore_filter",
        "use_adx_filter",
        "use_atr_vol_filter",
    ):
        if key in params and not isinstance(params[key], bool):
            raise ConfigValidationError(f"{field_prefix}.{key} must be boolean.")
    for key in ("stc_long_cross_level", "stc_short_cross_level", "adx_min"):
        if key in params:
            value = _finite_number(params[key], field=f"{field_prefix}.{key}")
            if key in {"stc_long_cross_level", "stc_short_cross_level"} and not 0.0 <= value <= 100.0:
                raise ConfigValidationError(f"{field_prefix}.{key} must be in [0, 100].")
            if key == "adx_min" and value < 0.0:
                raise ConfigValidationError(f"{field_prefix}.{key} must be >= 0.")
    long_level = float(params.get("stc_long_cross_level", 25.0))
    short_level = float(params.get("stc_short_cross_level", 75.0))
    if long_level >= short_level:
        raise ConfigValidationError(
            f"{field_prefix}.stc_long_cross_level must be less than {field_prefix}.stc_short_cross_level."
        )
    if "roofing_slope_bars" in params:
        _positive_int(params["roofing_slope_bars"], field=f"{field_prefix}.roofing_slope_bars")
    if "entry_delay_bars" in params:
        _non_negative_int(params["entry_delay_bars"], field=f"{field_prefix}.entry_delay_bars")
    regimes = params.get("allowed_volatility_regimes")
    if regimes is not None:
        if isinstance(regimes, (str, bytes)) or not isinstance(regimes, (list, tuple)) or not regimes:
            raise ConfigValidationError(f"{field_prefix}.allowed_volatility_regimes must be a non-empty list.")
        for idx, regime in enumerate(regimes):
            _finite_number(regime, field=f"{field_prefix}.allowed_volatility_regimes[{idx}]")


def _validate_ehlers_continuation_long_params(params: dict[str, Any], *, field_prefix: str) -> None:
    string_keys = {
        "ema_fast_col",
        "ema_slow_col",
        "mama_col",
        "fama_col",
        "roofing_col",
        "roofing_slope_col",
        "decycler_osc_col",
        "ema_condition_col",
        "mama_condition_col",
        "roofing_positive_col",
        "roofing_slope_positive_col",
        "roofing_gt_slope_col",
        "decycler_positive_col",
        "state_col",
        "entry_col",
        "signal_col",
        "candidate_col",
    }
    for key in string_keys:
        if key in params and (not isinstance(params[key], str) or not params[key].strip()):
            raise ConfigValidationError(f"{field_prefix}.{key} must be a non-empty string.")
    if "entry_mode" in params:
        entry_mode = str(params["entry_mode"])
        if entry_mode not in {"state", "transition"}:
            raise ConfigValidationError(f"{field_prefix}.entry_mode must be one of: state, transition.")
    for key in ("long_only", "use_ema_regime", "use_mama_fama", "use_roofing_gt_slope", "use_decycler"):
        if key in params and not isinstance(params[key], bool):
            raise ConfigValidationError(f"{field_prefix}.{key} must be boolean.")
    if params.get("long_only") is False:
        raise ConfigValidationError(f"{field_prefix}.long_only must be true for ehlers_continuation_long.")
    if "entry_delay_bars" in params:
        _non_negative_int(params["entry_delay_bars"], field=f"{field_prefix}.entry_delay_bars")


def _validate_ehlers_semiscalp_long_params(params: dict[str, Any], *, field_prefix: str) -> None:
    string_keys = {
        "price_col",
        "mama_col",
        "fama_col",
        "decycler_col",
        "roofing_col",
        "laguerre_col",
        "fisher_col",
        "hilbert_amplitude_col",
        "dominant_cycle_period_col",
        "signal_col",
        "candidate_col",
    }
    for key in string_keys:
        if key in params and (not isinstance(params[key], str) or not params[key].strip()):
            raise ConfigValidationError(f"{field_prefix}.{key} must be a non-empty string.")
    if "entry_mode" in params and params["entry_mode"] not in {"state", "transition"}:
        raise ConfigValidationError(f"{field_prefix}.entry_mode must be one of: state, transition.")
    if "roofing_trigger_mode" in params and params["roofing_trigger_mode"] not in {"rising", "cross_up"}:
        raise ConfigValidationError(f"{field_prefix}.roofing_trigger_mode must be one of: rising, cross_up.")
    if "require_mama_rising" in params and not isinstance(params["require_mama_rising"], bool):
        raise ConfigValidationError(f"{field_prefix}.require_mama_rising must be boolean.")
    if "amplitude_lookback" in params:
        _positive_int(params["amplitude_lookback"], field=f"{field_prefix}.amplitude_lookback")
    if "use_cycle_period_filter" in params and not isinstance(params["use_cycle_period_filter"], bool):
        raise ConfigValidationError(f"{field_prefix}.use_cycle_period_filter must be boolean.")
    if "laguerre_min" in params:
        laguerre_min = _finite_number(params["laguerre_min"], field=f"{field_prefix}.laguerre_min")
        if not 0.0 <= laguerre_min <= 1.0:
            raise ConfigValidationError(f"{field_prefix}.laguerre_min must be in [0, 1].")
    for key in ("min_cycle_period", "max_cycle_period"):
        if key in params and _finite_number(params[key], field=f"{field_prefix}.{key}") <= 0.0:
            raise ConfigValidationError(f"{field_prefix}.{key} must be > 0.")
    if float(params.get("min_cycle_period", 10.0)) > float(params.get("max_cycle_period", 48.0)):
        raise ConfigValidationError(f"{field_prefix}.min_cycle_period must be <= max_cycle_period.")


def _validate_ehlers_decycler_continuation_params(params: dict[str, Any], *, field_prefix: str) -> None:
    string_keys = {
        "decycler_osc_col",
        "decycler_ratio_col",
        "signal_col",
        "candidate_col",
    }
    for key in string_keys:
        if key in params and (not isinstance(params[key], str) or not params[key].strip()):
            raise ConfigValidationError(f"{field_prefix}.{key} must be a non-empty string.")
    if "entry_mode" in params and params["entry_mode"] not in {"state", "transition"}:
        raise ConfigValidationError(f"{field_prefix}.entry_mode must be one of: state, transition.")
    for key in ("decycler_osc_min", "decycler_ratio_max"):
        if key in params:
            _finite_number(params[key], field=f"{field_prefix}.{key}")


def _validate_ehlers_ml_long_candidate_params(params: dict[str, Any], *, field_prefix: str) -> None:
    string_keys = {
        "amplitude_col",
        "cycle_period_col",
        "roofing_col",
        "mama_col",
        "fama_col",
        "close_col",
        "decycler_col",
        "instantaneous_trendline_col",
        "frama_col",
        "supersmoother_col",
        "dominant_cycle_phase_col",
        "dominant_cycle_phase_unit",
        "candidate_col",
        "side_col",
    }
    for key in string_keys:
        if key in params and (not isinstance(params[key], str) or not params[key].strip()):
            raise ConfigValidationError(f"{field_prefix}.{key} must be a non-empty string.")
    if "atr_col" in params and params["atr_col"] is not None and (
        not isinstance(params["atr_col"], str) or not params["atr_col"].strip()
    ):
        raise ConfigValidationError(f"{field_prefix}.atr_col must be a non-empty string or null.")
    if "dominant_cycle_phase_unit" in params:
        _validate_phase_unit(params["dominant_cycle_phase_unit"], field=f"{field_prefix}.dominant_cycle_phase_unit")
    for key in ("amplitude_lookback", "slope_bars"):
        if key in params:
            _positive_int(params[key], field=f"{field_prefix}.{key}")
    if "amplitude_min_quantile" in params:
        quantile = _finite_number(params["amplitude_min_quantile"], field=f"{field_prefix}.amplitude_min_quantile")
        if not 0.0 <= quantile <= 1.0:
            raise ConfigValidationError(f"{field_prefix}.amplitude_min_quantile must be in [0, 1].")
    for key in ("min_cycle_period", "max_cycle_period"):
        if key in params and _finite_number(params[key], field=f"{field_prefix}.{key}") <= 0.0:
            raise ConfigValidationError(f"{field_prefix}.{key} must be > 0.")
    if float(params.get("min_cycle_period", 8.0)) > float(params.get("max_cycle_period", 60.0)):
        raise ConfigValidationError(f"{field_prefix}.min_cycle_period must be <= max_cycle_period.")


def _validate_ehlers_continuation_short_params(params: dict[str, Any], *, field_prefix: str) -> None:
    string_keys = {
        "ema_fast_col",
        "ema_slow_col",
        "mama_col",
        "fama_col",
        "roofing_col",
        "roofing_slope_col",
        "decycler_osc_col",
        "ema_condition_col",
        "mama_condition_col",
        "roofing_negative_col",
        "roofing_slope_negative_col",
        "roofing_lt_slope_col",
        "decycler_negative_col",
        "state_col",
        "entry_col",
        "signal_col",
        "candidate_col",
    }
    for key in string_keys:
        if key in params and (not isinstance(params[key], str) or not params[key].strip()):
            raise ConfigValidationError(f"{field_prefix}.{key} must be a non-empty string.")
    if "entry_mode" in params:
        entry_mode = str(params["entry_mode"])
        if entry_mode not in {"state", "transition"}:
            raise ConfigValidationError(f"{field_prefix}.entry_mode must be one of: state, transition.")
    for key in ("short_only", "use_ema_regime", "use_mama_fama", "use_roofing_lt_slope", "use_decycler"):
        if key in params and not isinstance(params[key], bool):
            raise ConfigValidationError(f"{field_prefix}.{key} must be boolean.")
    if params.get("short_only") is False:
        raise ConfigValidationError(f"{field_prefix}.short_only must be true for ehlers_continuation_short.")
    if "entry_delay_bars" in params:
        _non_negative_int(params["entry_delay_bars"], field=f"{field_prefix}.entry_delay_bars")


def _validate_optional_string(value: Any, *, field: str) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ConfigValidationError(f"{field} must be a non-empty string when provided.")


def _validate_bool(value: Any, *, field: str) -> None:
    if not isinstance(value, bool):
        raise ConfigValidationError(f"{field} must be boolean.")


def _helper_param_sets(raw_block: Any, *, field: str) -> list[dict[str, Any]]:
    if raw_block in (None, False):
        return []
    if not isinstance(raw_block, dict):
        raise ConfigValidationError(f"{field} must be a mapping.")
    if "enabled" in raw_block and not isinstance(raw_block["enabled"], bool):
        raise ConfigValidationError(f"{field}.enabled must be boolean.")
    if raw_block.get("enabled", True) is False:
        return []
    params = raw_block.get("params", {}) or {}
    if not isinstance(params, dict):
        raise ConfigValidationError(f"{field}.params must be a mapping when provided.")
    direct = {key: value for key, value in raw_block.items() if key not in {"enabled", "params", "items"}}
    items = raw_block.get("items")
    if items is None:
        return [{**direct, **params}]
    if not isinstance(items, list) or not items:
        raise ConfigValidationError(f"{field}.items must be a non-empty list of mappings.")
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ConfigValidationError(f"{field}.items[{idx}] must be a mapping.")
        out.append({**direct, **params, **item})
    return out


def _validate_feature_transform_params(kind: str, params: dict[str, Any], *, field: str) -> None:
    if kind in {"rms", "slope", "rolling_clip", "rolling_zscore"}:
        _validate_column_ref_or_selector(
            params,
            col_key="source_col",
            selector_key="source_selector",
            field=field,
        )
        _validate_optional_string(params.get("output_col"), field=f"{field}.output_col")
        if "window" in params:
            _positive_int(params["window"], field=f"{field}.window")
            if kind in {"rolling_clip", "rolling_zscore"} and int(params["window"]) <= 1:
                raise ConfigValidationError(f"{field}.window must be > 1.")
        if "shift" in params:
            _non_negative_int(params["shift"], field=f"{field}.shift")
    if kind == "rms":
        _validate_optional_string(params.get("output_prefix"), field=f"{field}.output_prefix")
    if kind == "rolling_clip":
        lower_q = _finite_number(params.get("lower_q", 0.01), field=f"{field}.lower_q")
        upper_q = _finite_number(params.get("upper_q", 0.99), field=f"{field}.upper_q")
        if not 0.0 <= lower_q <= 1.0:
            raise ConfigValidationError(f"{field}.lower_q must be in [0, 1].")
        if not 0.0 <= upper_q <= 1.0:
            raise ConfigValidationError(f"{field}.upper_q must be in [0, 1].")
        if not lower_q < upper_q:
            raise ConfigValidationError(f"{field}.lower_q must be strictly less than {field}.upper_q.")
    if kind == "rolling_zscore" and "ddof" in params:
        _non_negative_int(params["ddof"], field=f"{field}.ddof")
    if kind == "ratio":
        _validate_column_ref_or_selector(
            params,
            col_key="numerator_col",
            selector_key="numerator_selector",
            field=field,
        )
        _validate_column_ref_or_selector(
            params,
            col_key="denominator_col",
            selector_key="denominator_selector",
            field=field,
        )
        _validate_optional_string(params.get("output_col"), field=f"{field}.output_col")
        eps = _finite_number(params.get("eps", 1e-8), field=f"{field}.eps")
        if eps < 0.0:
            raise ConfigValidationError(f"{field}.eps must be >= 0.")
        if "subtract" in params:
            _finite_number(params["subtract"], field=f"{field}.subtract")


def _validate_pairs(value: Any, *, field: str) -> None:
    if not isinstance(value, list):
        raise ConfigValidationError(f"{field} must be a list of mappings.")
    for idx, pair in enumerate(value):
        pair_field = f"{field}[{idx}]"
        if not isinstance(pair, dict):
            raise ConfigValidationError(f"{pair_field} must be a mapping.")
        for key in ("name", "base_col", "ref_col"):
            if not isinstance(pair.get(key), str) or not pair.get(key, "").strip():
                raise ConfigValidationError(f"{pair_field}.{key} must be a non-empty string.")


def _validate_feature_normalization_params(kind: str, params: dict[str, Any], *, field: str) -> None:
    if kind == "returns":
        _validate_optional_string(params.get("close_col"), field=f"{field}.close_col")
        windows = params.get("windows", [1, 4, 8, 20, 48])
        if not isinstance(windows, (list, tuple)) or not windows:
            raise ConfigValidationError(f"{field}.windows must be a non-empty list of positive integers.")
        for idx, window in enumerate(windows):
            _positive_int(window, field=f"{field}.windows[{idx}]")
        if "log_returns" in params:
            _validate_bool(params["log_returns"], field=f"{field}.log_returns")
    elif kind == "atr_distances":
        _validate_optional_string(params.get("atr_col"), field=f"{field}.atr_col")
        _validate_pairs(params.get("pairs", []), field=f"{field}.pairs")
    elif kind == "atr_scaled_distance":
        for key in ("base_col", "ref_col", "atr_col"):
            if not isinstance(params.get(key), str) or not params.get(key, "").strip():
                raise ConfigValidationError(f"{field}.{key} must be a non-empty string.")
        _validate_optional_string(params.get("output_col"), field=f"{field}.output_col")
        if "eps" in params and _finite_number(params["eps"], field=f"{field}.eps") < 0.0:
            raise ConfigValidationError(f"{field}.eps must be >= 0.")
    elif kind == "range_position":
        for key in ("value_col", "high_col", "low_col", "output_col"):
            _validate_optional_string(params.get(key), field=f"{field}.{key}")
        _positive_int(params.get("window", 20), field=f"{field}.window")
        if int(params.get("window", 20)) <= 1:
            raise ConfigValidationError(f"{field}.window must be > 1.")
        if "clip" in params:
            _validate_bool(params["clip"], field=f"{field}.clip")
    elif kind == "realized_vol_percentile":
        if not isinstance(params.get("volatility_col"), str) or not params.get("volatility_col", "").strip():
            raise ConfigValidationError(f"{field}.volatility_col must be a non-empty string.")
        _validate_optional_string(params.get("output_col"), field=f"{field}.output_col")
        _positive_int(params.get("window", 252), field=f"{field}.window")
        if int(params.get("window", 252)) <= 1:
            raise ConfigValidationError(f"{field}.window must be > 1.")
        if params.get("min_periods") is not None:
            _positive_int(params["min_periods"], field=f"{field}.min_periods")
        if "shift_window" in params:
            _validate_bool(params["shift_window"], field=f"{field}.shift_window")
    elif kind == "volatility":
        for key in ("close_col", "atr_col"):
            _validate_optional_string(params.get(key), field=f"{field}.{key}")
        for key in ("add_atr_pct", "add_atr_percentile"):
            if key in params:
                _validate_bool(params[key], field=f"{field}.{key}")
        if "percentile_window" in params:
            _positive_int(params["percentile_window"], field=f"{field}.percentile_window")
            if int(params["percentile_window"]) <= 1:
                raise ConfigValidationError(f"{field}.percentile_window must be > 1.")
    elif kind == "volatility_scaled_return":
        for key in ("return_col", "volatility_col"):
            if not isinstance(params.get(key), str) or not params.get(key, "").strip():
                raise ConfigValidationError(f"{field}.{key} must be a non-empty string.")
        _validate_optional_string(params.get("output_col"), field=f"{field}.output_col")
        if "eps" in params and _finite_number(params["eps"], field=f"{field}.eps") < 0.0:
            raise ConfigValidationError(f"{field}.eps must be >= 0.")
    elif kind == "volume_relative":
        for key in ("volume_col", "output_col", "zscore_col"):
            _validate_optional_string(params.get(key), field=f"{field}.{key}")
        _positive_int(params.get("window", 96), field=f"{field}.window")
        if int(params.get("window", 96)) <= 1:
            raise ConfigValidationError(f"{field}.window must be > 1.")
        if params.get("min_periods") is not None:
            _positive_int(params["min_periods"], field=f"{field}.min_periods")
        if "shift_stats" in params:
            _validate_bool(params["shift_stats"], field=f"{field}.shift_stats")
        if "eps" in params and _finite_number(params["eps"], field=f"{field}.eps") < 0.0:
            raise ConfigValidationError(f"{field}.eps must be >= 0.")
    elif kind in {"rolling_percent_rank", "robust_zscore"}:
        if not isinstance(params.get("source_col"), str) or not params.get("source_col", "").strip():
            raise ConfigValidationError(f"{field}.source_col must be a non-empty string.")
        _validate_optional_string(params.get("output_col"), field=f"{field}.output_col")
        _positive_int(params.get("window", 252), field=f"{field}.window")
        if int(params.get("window", 252)) <= 1:
            raise ConfigValidationError(f"{field}.window must be > 1.")
        if params.get("min_periods") is not None:
            _positive_int(params["min_periods"], field=f"{field}.min_periods")
        if kind == "rolling_percent_rank" and "shift_window" in params:
            _validate_bool(params["shift_window"], field=f"{field}.shift_window")
        if kind == "robust_zscore":
            if "shift_stats" in params:
                _validate_bool(params["shift_stats"], field=f"{field}.shift_stats")
            if "mad_scale" in params and _finite_number(params["mad_scale"], field=f"{field}.mad_scale") <= 0.0:
                raise ConfigValidationError(f"{field}.mad_scale must be > 0.")
    elif kind == "rolling_beta_residual":
        for key in ("asset_return_col", "benchmark_return_col"):
            if not isinstance(params.get(key), str) or not params.get(key, "").strip():
                raise ConfigValidationError(f"{field}.{key} must be a non-empty string.")
        for key in ("residual_col", "beta_col", "alpha_col"):
            _validate_optional_string(params.get(key), field=f"{field}.{key}")
        _positive_int(params.get("window", 252), field=f"{field}.window")
        if int(params.get("window", 252)) <= 1:
            raise ConfigValidationError(f"{field}.window must be > 1.")
        if params.get("min_periods") is not None:
            _positive_int(params["min_periods"], field=f"{field}.min_periods")
        if "shift_stats" in params:
            _validate_bool(params["shift_stats"], field=f"{field}.shift_stats")
        if "eps" in params and _finite_number(params["eps"], field=f"{field}.eps") < 0.0:
            raise ConfigValidationError(f"{field}.eps must be >= 0.")
    elif kind == "rolling_zscores":
        columns = params.get("columns")
        if not isinstance(columns, list) or not columns:
            raise ConfigValidationError(f"{field}.columns must be a non-empty list[str].")
        for idx, column in enumerate(columns):
            if not isinstance(column, str) or not column.strip():
                raise ConfigValidationError(f"{field}.columns[{idx}] must be a non-empty string.")
        _positive_int(params.get("window", 96), field=f"{field}.window")
        if int(params.get("window", 96)) <= 1:
            raise ConfigValidationError(f"{field}.window must be > 1.")
        if params.get("min_periods") is not None:
            _positive_int(params["min_periods"], field=f"{field}.min_periods")
        if "shift_stats" in params:
            _validate_bool(params["shift_stats"], field=f"{field}.shift_stats")


def _validate_feature_helper_section(
    section: Any,
    *,
    field: str,
    allowed: set[str],
    validator: Any,
) -> None:
    if section in (None, {}):
        return
    if not isinstance(section, dict):
        raise ConfigValidationError(f"{field} must be a mapping when provided.")
    unknown = sorted(set(section) - allowed)
    if unknown:
        allowed_display = ", ".join(sorted(allowed))
        raise ConfigValidationError(f"{field} has unsupported helpers: {unknown}. Allowed: {allowed_display}.")
    for helper_name, raw_block in section.items():
        helper_field = f"{field}.{helper_name}"
        for idx, params in enumerate(_helper_param_sets(raw_block, field=helper_field)):
            validator(str(helper_name), params, field=f"{helper_field}.items[{idx}]")


def _validate_feature_helper_sections_by_asset(
    section_by_asset: Any,
    *,
    field: str,
    allowed: set[str],
    validator: Any,
) -> None:
    if section_by_asset in (None, {}):
        return
    if not isinstance(section_by_asset, dict):
        raise ConfigValidationError(f"{field} must be a mapping when provided.")
    for asset, section in section_by_asset.items():
        if not isinstance(asset, str) or not asset.strip():
            raise ConfigValidationError(f"{field} keys must be non-empty strings.")
        _validate_feature_helper_section(
            section,
            field=f"{field}.{asset}",
            allowed=allowed,
            validator=validator,
        )


def _validate_feature_helper_blocks(step: dict[str, Any]) -> None:
    _validate_feature_helper_section(
        step.get("transforms"),
        field="features[].transforms",
        allowed=_FEATURE_TRANSFORM_HELPERS,
        validator=_validate_feature_transform_params,
    )
    _validate_feature_helper_section(
        step.get("normalizations"),
        field="features[].normalizations",
        allowed=_FEATURE_NORMALIZATION_HELPERS,
        validator=_validate_feature_normalization_params,
    )
    _validate_feature_helper_sections_by_asset(
        step.get("transforms_by_asset"),
        field="features[].transforms_by_asset",
        allowed=_FEATURE_TRANSFORM_HELPERS,
        validator=_validate_feature_transform_params,
    )
    _validate_feature_helper_sections_by_asset(
        step.get("normalizations_by_asset"),
        field="features[].normalizations_by_asset",
        allowed=_FEATURE_NORMALIZATION_HELPERS,
        validator=_validate_feature_normalization_params,
    )
    for asset, asset_params in dict(step.get("params_by_asset", {}) or {}).items():
        if not isinstance(asset_params, dict):
            continue
        _validate_feature_helper_section(
            asset_params.get("transforms"),
            field=f"features[].params_by_asset.{asset}.transforms",
            allowed=_FEATURE_TRANSFORM_HELPERS,
            validator=_validate_feature_transform_params,
        )
        _validate_feature_helper_section(
            asset_params.get("normalizations"),
            field=f"features[].params_by_asset.{asset}.normalizations",
            allowed=_FEATURE_NORMALIZATION_HELPERS,
            validator=_validate_feature_normalization_params,
        )


def _iter_feature_param_blocks(step: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    blocks: list[tuple[str, dict[str, Any]]] = []
    params = step.get("params") or {}
    if isinstance(params, dict):
        blocks.append(("features[].params", params))
    for asset, asset_params in dict(step.get("params_by_asset", {}) or {}).items():
        if isinstance(asset_params, dict):
            blocks.append((f"features[].params_by_asset.{asset}", asset_params))
    return blocks


def _reject_derived_feature_param(
    params: dict[str, Any],
    *,
    field_prefix: str,
    flag_key: str,
    output_key: str,
    helper: str,
) -> None:
    if flag_key in params:
        if not isinstance(params[flag_key], bool):
            raise ConfigValidationError(f"{field_prefix}.{flag_key} must be boolean.")
        if params[flag_key] is True:
            raise ConfigValidationError(f"{field_prefix}.{flag_key} is no longer supported; use {helper}.")
    if params.get(output_key) is not None:
        raise ConfigValidationError(f"{field_prefix}.{output_key} is no longer supported; use {helper}.")


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
        if step["step"] not in FEATURE_KINDS:
            raise ConfigValidationError(f"Unknown feature step: {step['step']}")
        if "params" in step and step["params"] is not None and not isinstance(step["params"], dict):
            raise ConfigValidationError("features[].params must be a mapping when provided.")
        params_by_asset = step.get("params_by_asset", {})
        if not isinstance(params_by_asset, dict):
            raise ConfigValidationError("features[].params_by_asset must be a mapping when provided.")
        for asset, asset_params in dict(params_by_asset or {}).items():
            if not isinstance(asset, str) or not asset.strip():
                raise ConfigValidationError("features[].params_by_asset keys must be non-empty strings.")
            if not isinstance(asset_params, dict):
                raise ConfigValidationError("features[].params_by_asset values must be mappings.")
        _validate_string_mapping(step.get("outputs"), field="features[].outputs")
        _validate_feature_helper_blocks(step)
        if step["step"] == "dominant_cycle_phase":
            for field_prefix, params in _iter_feature_param_blocks(step):
                for key in ("price_col", "output_col"):
                    if key in params and params[key] is not None and (
                        not isinstance(params[key], str) or not params[key].strip()
                    ):
                        raise ConfigValidationError(f"{field_prefix}.{key} must be a non-empty string.")
                if "unit" in params:
                    _validate_phase_unit(params["unit"], field=f"{field_prefix}.unit")
        if step["step"] == "impulse_12_96":
            for field_prefix, params in _iter_feature_param_blocks(step):
                for key in ("return_bars", "volatility_window"):
                    if key in params:
                        _positive_int(params[key], field=f"{field_prefix}.{key}")
                for key in ("close_col", "returns_col", "output_col"):
                    if key in params and (not isinstance(params[key], str) or not params[key].strip()):
                        raise ConfigValidationError(f"{field_prefix}.{key} must be a non-empty string.")
        if step["step"] == "roc_long_only_conditions":
            _validate_roc_long_only_conditions_params(step.get("params") or {}, field_prefix="features[].params")
        if step["step"] == "ehlers_semiscalp_long":
            _validate_ehlers_semiscalp_long_params(
                step.get("params") or {},
                field_prefix="features[].params",
            )
        if step["step"] == "ehlers_decycler_continuation":
            _validate_ehlers_decycler_continuation_params(
                step.get("params") or {},
                field_prefix="features[].params",
            )
        if step["step"] == "ehlers_ml_long_candidate":
            _validate_ehlers_ml_long_candidate_params(
                step.get("params") or {},
                field_prefix="features[].params",
            )
        if step["step"] == "roofing_filter":
            params = step.get("params") or {}
            for key in (
                "price_col",
                "output_col",
                "slope_col",
                "positive_col",
                "negative_col",
                "slope_positive_col",
                "slope_negative_col",
                "cross_up_zero_col",
                "cross_down_zero_col",
            ):
                if key in params and params[key] is not None and (
                    not isinstance(params[key], str) or not params[key].strip()
                ):
                    raise ConfigValidationError(f"features[].params.{key} must be a non-empty string.")
            for key in ("high_pass_period", "low_pass_period", "slope_bars"):
                if key in params and params[key] is not None:
                    _positive_int(params[key], field=f"features[].params.{key}")
                    if key in {"high_pass_period", "low_pass_period"} and int(params[key]) <= 1:
                        raise ConfigValidationError(f"features[].params.{key} must be > 1.")
            if "add_derived" in params and not isinstance(params["add_derived"], bool):
                raise ConfigValidationError("features[].params.add_derived must be boolean.")
            if (
                params.get("high_pass_period") is not None
                and params.get("low_pass_period") is not None
                and int(params["high_pass_period"]) <= int(params["low_pass_period"])
            ):
                raise ConfigValidationError("features[].params.high_pass_period must be > low_pass_period.")
        if step["step"] == "hilbert_transform":
            params = step.get("params") or {}
            for key in (
                "price_col",
                "amplitude_col",
                "phase_col",
                "instantaneous_frequency_col",
                "dominant_cycle_col",
                "cycle_ok_col",
                "amplitude_rising_col",
            ):
                if key in params and params[key] is not None and (
                    not isinstance(params[key], str) or not params[key].strip()
                ):
                    raise ConfigValidationError(f"features[].params.{key} must be a non-empty string.")
            if "window" in params and params["window"] is not None:
                _positive_int(params["window"], field="features[].params.window")
                if int(params["window"]) < 4:
                    raise ConfigValidationError("features[].params.window must be >= 4.")
            for key in ("min_cycle", "max_cycle", "amplitude_slope_bars"):
                if key in params and params[key] is not None:
                    _positive_int(params[key], field=f"features[].params.{key}")
            if (
                params.get("min_cycle") is not None
                and params.get("max_cycle") is not None
                and int(params["min_cycle"]) > int(params["max_cycle"])
            ):
                raise ConfigValidationError("features[].params.min_cycle must be <= max_cycle.")
            if "add_derived" in params and not isinstance(params["add_derived"], bool):
                raise ConfigValidationError("features[].params.add_derived must be boolean.")
            if params.get("add_derived") is True or any(
                params.get(key) is not None
                for key in ("dominant_cycle_col", "cycle_ok_col", "amplitude_rising_col")
            ):
                raise ConfigValidationError(
                    "hilbert_transform derived outputs are no longer supported in feature params; "
                    "use transforms.reciprocal, transforms.between_flag, and transforms.rising_flag."
                )
        if step["step"] == "schaff_trend_cycle":
            params = step.get("params") or {}
            for key in (
                "price_col",
                "stc_col",
                "stc_signal_col",
                "cross_up_col",
                "cross_down_col",
                "rising_col",
                "falling_col",
            ):
                if key in params and params[key] is not None and (
                    not isinstance(params[key], str) or not params[key].strip()
                ):
                    raise ConfigValidationError(f"features[].params.{key} must be a non-empty string.")
            for key in ("fast", "slow", "cycle", "smooth"):
                if key in params and params[key] is not None:
                    _positive_int(params[key], field=f"features[].params.{key}")
                    if int(params[key]) <= 1:
                        raise ConfigValidationError(f"features[].params.{key} must be > 1.")
            if (
                params.get("fast") is not None
                and params.get("slow") is not None
                and int(params["fast"]) >= int(params["slow"])
            ):
                raise ConfigValidationError("features[].params.fast must be < slow.")
            if any(
                params.get(key) is not None
                for key in ("cross_up_col", "cross_down_col", "rising_col", "falling_col")
            ):
                raise ConfigValidationError(
                    "schaff_trend_cycle derived outputs are no longer supported in feature params; "
                    "use transforms.crossing_flag, transforms.rising_flag, transforms.difference, "
                    "and transforms.threshold_flag."
                )
            for key in ("long_cross_level", "short_cross_level"):
                if key in params:
                    value = _finite_number(params[key], field=f"features[].params.{key}")
                    if not 0.0 <= value <= 100.0:
                        raise ConfigValidationError(f"features[].params.{key} must be in [0, 100].")
            if float(params.get("long_cross_level", 25.0)) >= float(params.get("short_cross_level", 75.0)):
                raise ConfigValidationError("features[].params.long_cross_level must be < short_cross_level.")
        if step["step"] == "vol_normalized_momentum":
            params = step.get("params") or {}
            for key in ("returns_col", "vol_col"):
                if key in params and params[key] is not None and not isinstance(params[key], str):
                    raise ConfigValidationError(f"features[].params.{key} must be a string when provided.")
            if "vol_window" in params and params["vol_window"] is not None:
                _positive_int(params["vol_window"], field="features[].params.vol_window")
            windows = params.get("windows")
            if windows is not None:
                if not isinstance(windows, (list, tuple)) or not windows:
                    raise ConfigValidationError("features[].params.windows must be a non-empty list of integers.")
                for idx, window in enumerate(windows):
                    _positive_int(window, field=f"features[].params.windows[{idx}]")
        if step["step"] == "multi_timeframe":
            params = step.get("params") or {}
            for key in (
                "price_col",
                "high_col",
                "low_col",
                "open_col",
                "volume_col",
                "returns_col",
                "timezone",
                "timestamp_col",
                "asset_col",
                "timestamp_convention",
            ):
                if key in params and params[key] is not None and not isinstance(params[key], str):
                    raise ConfigValidationError(f"features[].params.{key} must be a string when provided.")
            timestamp_convention = str(params.get("timestamp_convention", "bar_close")).strip().lower()
            if timestamp_convention not in {"bar_start", "bar_close"}:
                raise ConfigValidationError("features[].params.timestamp_convention must be one of: bar_start, bar_close.")
            if "base_interval_minutes" in params:
                _positive_int(params["base_interval_minutes"], field="features[].params.base_interval_minutes")
            timeframes = params.get("timeframes")
            if timeframes is not None:
                if not isinstance(timeframes, (list, tuple)) or not timeframes:
                    raise ConfigValidationError("features[].params.timeframes must be a non-empty list[str].")
                for idx, timeframe in enumerate(timeframes):
                    if not isinstance(timeframe, str) or not timeframe.strip():
                        raise ConfigValidationError(f"features[].params.timeframes[{idx}] must be a non-empty string.")
            for key in (
                "volatility_window",
                "trend_ema_span",
                "trend_sma_window",
                "atr_window",
                "adx_window",
                "regime_short_window",
                "regime_long_window",
            ):
                if key in params and params[key] is not None:
                    _positive_int(params[key], field=f"features[].params.{key}")
            if "shift_to_last_closed" in params and not isinstance(params["shift_to_last_closed"], bool):
                raise ConfigValidationError("features[].params.shift_to_last_closed must be boolean.")
        if step["step"] == "opening_range_breakout":
            params = step.get("params") or {}
            for key in (
                "timestamp_col",
                "timezone_input",
                "price_col",
                "open_col",
                "high_col",
                "low_col",
                "close_col",
                "atr_col",
                "volatility_col",
                "asset_col",
            ):
                if key in params and params[key] is not None and not isinstance(params[key], str):
                    raise ConfigValidationError(f"features[].params.{key} must be a string when provided.")
            sessions = params.get("sessions")
            if sessions is not None:
                if not isinstance(sessions, list) or not sessions:
                    raise ConfigValidationError("features[].params.sessions must be a non-empty list.")
                seen_sessions: set[str] = set()
                for session_idx, raw_session in enumerate(sessions):
                    field_prefix = f"features[].params.sessions[{session_idx}]"
                    if not isinstance(raw_session, dict):
                        raise ConfigValidationError(f"{field_prefix} must be a mapping.")
                    name = raw_session.get("name")
                    if not isinstance(name, str) or not name.strip():
                        raise ConfigValidationError(f"{field_prefix}.name must be a non-empty string.")
                    if name in seen_sessions:
                        raise ConfigValidationError(f"Duplicate ORB session name: {name}.")
                    seen_sessions.add(name)
                    if not isinstance(raw_session.get("timezone"), str) or not raw_session.get("timezone", "").strip():
                        raise ConfigValidationError(f"{field_prefix}.timezone must be a non-empty string.")
                    _validate_clock_string(raw_session.get("session_open_time"), field=f"{field_prefix}.session_open_time")
                    _validate_clock_string(raw_session.get("trade_until_time"), field=f"{field_prefix}.trade_until_time")
                    if raw_session.get("extended_trade_until_time") is not None:
                        _validate_clock_string(
                            raw_session.get("extended_trade_until_time"),
                            field=f"{field_prefix}.extended_trade_until_time",
                        )
                    if "opening_range_bars" in raw_session:
                        _positive_int(raw_session["opening_range_bars"], field=f"{field_prefix}.opening_range_bars")
            enabled_sessions = params.get("enabled_sessions")
            if enabled_sessions is not None:
                if not isinstance(enabled_sessions, (list, tuple)) or not enabled_sessions:
                    raise ConfigValidationError("features[].params.enabled_sessions must be a non-empty list[str].")
                for idx, session_name in enumerate(enabled_sessions):
                    if not isinstance(session_name, str) or not session_name.strip():
                        raise ConfigValidationError(
                            f"features[].params.enabled_sessions[{idx}] must be a non-empty string."
                        )
            for mapping_key in ("asset_session_map", "asset_alias_map"):
                mapping = params.get(mapping_key)
                if mapping is not None:
                    if not isinstance(mapping, dict) or not mapping:
                        raise ConfigValidationError(f"features[].params.{mapping_key} must be a non-empty mapping.")
                    for key, value in mapping.items():
                        if not isinstance(key, str) or not key.strip():
                            raise ConfigValidationError(f"features[].params.{mapping_key} keys must be non-empty strings.")
                        if mapping_key == "asset_alias_map":
                            if not isinstance(value, str) or not value.strip():
                                raise ConfigValidationError(
                                    f"features[].params.{mapping_key}.{key} must be a non-empty string."
                                )
                        else:
                            if not isinstance(value, (list, tuple)) or not value:
                                raise ConfigValidationError(
                                    f"features[].params.{mapping_key}.{key} must be a non-empty list[str]."
                                )
                            for idx, session_name in enumerate(value):
                                if not isinstance(session_name, str) or not session_name.strip():
                                    raise ConfigValidationError(
                                        f"features[].params.{mapping_key}.{key}[{idx}] must be a non-empty string."
                                    )
            for key in ("min_range_atr", "max_range_atr", "breakout_buffer_atr"):
                if params.get(key) is not None:
                    value = _finite_number(params[key], field=f"features[].params.{key}")
                    if key == "max_range_atr" and value <= 0.0:
                        raise ConfigValidationError(f"features[].params.{key} must be > 0.")
                    if key != "max_range_atr" and value < 0.0:
                        raise ConfigValidationError(f"features[].params.{key} must be >= 0.")
            if params.get("min_range_atr") is not None and params.get("max_range_atr") is not None:
                if float(params["min_range_atr"]) > float(params["max_range_atr"]):
                    raise ConfigValidationError("features[].params.min_range_atr must be <= max_range_atr.")
            for key in ("post_breakout_active_bars", "max_breakouts_per_session", "opening_range_bars"):
                if key in params and params[key] is not None:
                    _positive_int(params[key], field=f"features[].params.{key}")
            for key in ("use_close_breakout", "allow_reversal_same_session", "use_extended_trade_until"):
                if key in params and not isinstance(params[key], bool):
                    raise ConfigValidationError(f"features[].params.{key} must be boolean.")
        if step["step"] == "trend":
            for field_prefix, params in _iter_feature_param_blocks(step):
                if "add_ratios" in params:
                    if not isinstance(params["add_ratios"], bool):
                        raise ConfigValidationError(f"{field_prefix}.add_ratios must be boolean.")
                    if params["add_ratios"] is True:
                        raise ConfigValidationError(
                            f"{field_prefix}.add_ratios is no longer supported; use transforms.ratio."
                        )
        if step["step"] in {"atr", "adx"}:
            params = step.get("params") or {}
            if "window" in params and params["window"] is not None:
                _positive_int(params["window"], field="features[].params.window")
            windows = params.get("windows")
            if windows is not None:
                if not isinstance(windows, (list, tuple)) or not windows:
                    raise ConfigValidationError("features[].params.windows must be a non-empty list of integers.")
                for idx, window in enumerate(windows):
                    _positive_int(window, field=f"features[].params.windows[{idx}]")
            if step["step"] == "atr":
                for key in ("atr_col", "over_price_col"):
                    if key in params and params[key] is not None and (
                        not isinstance(params[key], str) or not params[key].strip()
                    ):
                        raise ConfigValidationError(f"features[].params.{key} must be a non-empty string.")
                if windows is not None and len(windows) != 1 and params.get("atr_col") is not None:
                    raise ConfigValidationError(
                        "features[].params stable ATR output columns require exactly one window."
                    )
                if "method" in params and params["method"] not in {"wilder", "simple"}:
                    raise ConfigValidationError("features[].params.method must be one of: wilder, simple.")
                for field_prefix, block in _iter_feature_param_blocks(step):
                    _reject_derived_feature_param(
                        block,
                        field_prefix=field_prefix,
                        flag_key="add_over_price",
                        output_key="over_price_col",
                        helper="transforms.ratio",
                    )
                if params.get("atr_col") is not None and params.get("atr_col") == params.get("over_price_col"):
                    raise ConfigValidationError("features[].params ATR output columns must be unique.")
        if step["step"] == "vwap":
            params = step.get("params") or {}
            for key in ("high_col", "low_col", "close_col", "volume_col"):
                if key in params and params[key] is not None and not isinstance(params[key], str):
                    raise ConfigValidationError(f"features[].params.{key} must be a string when provided.")
            for key in ("vwap_col", "distance_col"):
                if key in params and params[key] is not None and (
                    not isinstance(params[key], str) or not params[key].strip()
                ):
                    raise ConfigValidationError(f"features[].params.{key} must be a non-empty string.")
            if "window" in params and params["window"] is not None:
                _positive_int(params["window"], field="features[].params.window")
            windows = params.get("windows")
            if windows is not None:
                if not isinstance(windows, (list, tuple)) or not windows:
                    raise ConfigValidationError("features[].params.windows must be a non-empty list of integers.")
                for idx, window in enumerate(windows):
                    _positive_int(window, field=f"features[].params.windows[{idx}]")
            if windows is not None and len(windows) != 1 and params.get("vwap_col") is not None:
                raise ConfigValidationError(
                    "features[].params stable VWAP output columns require exactly one window."
                )
            for field_prefix, block in _iter_feature_param_blocks(step):
                _reject_derived_feature_param(
                    block,
                    field_prefix=field_prefix,
                    flag_key="add_distance",
                    output_key="distance_col",
                    helper="transforms.ratio",
                )
            if params.get("vwap_col") is not None and params.get("vwap_col") == params.get("distance_col"):
                raise ConfigValidationError("features[].params VWAP output columns must be unique.")
        if step["step"] == "ppo":
            params = step.get("params") or {}
            for key in ("price_col", "ppo_col", "ppo_signal_col", "ppo_hist_col"):
                if key in params and params[key] is not None and (
                    not isinstance(params[key], str) or not params[key].strip()
                ):
                    raise ConfigValidationError(f"features[].params.{key} must be a non-empty string.")
            for key in ("fast", "slow", "signal"):
                if key in params:
                    _positive_int(params[key], field=f"features[].params.{key}")
            output_cols = [
                params[key]
                for key in ("ppo_col", "ppo_signal_col", "ppo_hist_col")
                if params.get(key) is not None
            ]
            if len(output_cols) != len(set(output_cols)):
                raise ConfigValidationError("features[].params PPO output columns must be unique.")
        if step["step"] == "hmm_regime":
            params = step.get("params") or {}
            feature_cols = params.get("feature_cols")
            if feature_cols is not None:
                if not isinstance(feature_cols, (list, tuple)) or not feature_cols:
                    raise ConfigValidationError("features[].params.feature_cols must be a non-empty list[str].")
                for idx, column in enumerate(feature_cols):
                    if not isinstance(column, str) or not column.strip():
                        raise ConfigValidationError(f"features[].params.feature_cols[{idx}] must be a non-empty string.")
            for key in ("price_col", "returns_col", "output_col", "probability_prefix"):
                if key in params and params[key] is not None and (
                    not isinstance(params[key], str) or not params[key].strip()
                ):
                    raise ConfigValidationError(f"features[].params.{key} must be a non-empty string.")
            for key in ("n_states", "train_size", "min_train_size", "refit_interval", "n_iter"):
                if key in params and params[key] is not None:
                    _positive_int(params[key], field=f"features[].params.{key}")
            if "random_state" in params and params["random_state"] is not None:
                _non_negative_int(params["random_state"], field="features[].params.random_state")
            if "mode" in params and params["mode"] not in {"expanding", "static_train"}:
                raise ConfigValidationError("features[].params.mode must be one of: expanding, static_train.")
            if "covariance_type" in params and not isinstance(params["covariance_type"], str):
                raise ConfigValidationError("features[].params.covariance_type must be a string.")
            for key in ("include_probabilities", "standardize"):
                if key in params and not isinstance(params[key], bool):
                    raise ConfigValidationError(f"features[].params.{key} must be boolean.")
            if "standardize_eps" in params:
                value = _finite_number(params["standardize_eps"], field="features[].params.standardize_eps")
                if value <= 0.0:
                    raise ConfigValidationError("features[].params.standardize_eps must be > 0.")
        if step["step"] == "regime_context":
            params = step.get("params") or {}
            for key in ("vol_short_window", "vol_long_window", "trend_fast_span", "trend_slow_span"):
                if key in params and params[key] is not None:
                    _positive_int(params[key], field=f"features[].params.{key}")
            vol_window_pairs = params.get("vol_window_pairs")
            if vol_window_pairs is not None:
                if not isinstance(vol_window_pairs, (list, tuple)) or not vol_window_pairs:
                    raise ConfigValidationError("features[].params.vol_window_pairs must be a non-empty list.")
                for pair_idx, pair in enumerate(vol_window_pairs):
                    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                        raise ConfigValidationError(
                            f"features[].params.vol_window_pairs[{pair_idx}] must contain exactly two integers."
                        )
                    for value_idx, value in enumerate(pair):
                        _positive_int(value, field=f"features[].params.vol_window_pairs[{pair_idx}][{value_idx}]")
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
        if step["step"] == "support_resistance":
            params = step.get("params") or {}
            for key in ("price_col", "high_col", "low_col", "atr_col"):
                if key in params and params[key] is not None and not isinstance(params[key], str):
                    raise ConfigValidationError(f"features[].params.{key} must be a string when provided.")
            windows = params.get("windows")
            if windows is not None:
                if not isinstance(windows, (list, tuple)) or not windows:
                    raise ConfigValidationError("features[].params.windows must be a non-empty list of integers.")
                for idx, window in enumerate(windows):
                    _positive_int(window, field=f"features[].params.windows[{idx}]")
            if "atr_window" in params and params["atr_window"] is not None:
                _positive_int(params["atr_window"], field="features[].params.atr_window")
            for key in ("include_pct_distance", "include_atr_distance"):
                if key in params and not isinstance(params[key], bool):
                    raise ConfigValidationError(f"features[].params.{key} must be boolean.")
        if step["step"] == "support_resistance_v2":
            params = step.get("params") or {}
            for key in ("price_col", "high_col", "low_col", "atr_col"):
                if key in params and params[key] is not None and not isinstance(params[key], str):
                    raise ConfigValidationError(f"features[].params.{key} must be a string when provided.")
            for key in ("atr_window", "pivot_left_window", "pivot_confirm_bars"):
                if key in params and params[key] is not None:
                    _positive_int(params[key], field=f"features[].params.{key}")
            for key in ("touch_tolerance_atr", "breakout_tolerance_atr"):
                if key in params and params[key] is not None:
                    value = _finite_number(params[key], field=f"features[].params.{key}")
                    if value < 0.0:
                        raise ConfigValidationError(f"features[].params.{key} must be >= 0.")


def _flatten_target_cfg_for_validation(target: dict[str, Any]) -> dict[str, Any]:
    out = dict(target or {})
    params = out.pop("params", None)
    if params is not None:
        if not isinstance(params, dict):
            raise ConfigValidationError("model.target.params must be a mapping when provided.")
        out.update(dict(params))
    return out


def _validate_r_multiple_target_block(target: dict[str, Any]) -> None:
    _validate_string_mapping(
        target.get("outputs"),
        field="model.target.outputs",
        allowed_keys=_TARGET_OUTPUT_KEYS,
    )
    for key in (
        "candidate_col",
        "candidate_out_col",
        "label_col",
        "fwd_col",
        "event_ret_col",
        "r_col",
        "oriented_r_col",
        "trade_r_col",
        "entry_price_col",
        "exit_price_col",
        "stop_price_col",
        "take_profit_price_col",
        "exit_reason_col",
        "bars_held_col",
        "hit_step_col",
        "hit_type_col",
        "price_col",
        "open_col",
        "high_col",
        "low_col",
        "volatility_col",
        "roc_col",
        "regime_vol_ratio_z_col",
    ):
        if key in target and target[key] is not None and not isinstance(target[key], str):
            raise ConfigValidationError(f"model.target.{key} must be a string or null.")
    side = str(target.get("side", "long_only"))
    if side != "long_only":
        raise ConfigValidationError("model.target.side must be 'long_only'.")
    entry_price_mode = str(target.get("entry_price_mode", "next_open"))
    if entry_price_mode not in {"next_open", "current_close"}:
        raise ConfigValidationError("model.target.entry_price_mode must be one of: next_open, current_close.")
    stop_mode = str(target.get("stop_mode", "volatility_stop"))
    if stop_mode not in {"volatility_stop", "fixed_return"}:
        raise ConfigValidationError("model.target.stop_mode must be one of: volatility_stop, fixed_return.")
    tie_break = str(target.get("tie_break", "conservative"))
    if tie_break not in {"conservative", "take_profit", "stop_loss", "closest_to_open"}:
        raise ConfigValidationError(
            "model.target.tie_break must be one of: conservative, take_profit, stop_loss, closest_to_open."
        )
    for key, default in (
        ("target_r_min", 1.0),
        ("take_profit_r", 2.0),
        ("stop_loss_r", 1.0),
        ("stop_loss_return", 0.005),
        ("take_profit_return", 0.010),
    ):
        value = _finite_number(target.get(key, default), field=f"model.target.{key}")
        if key != "target_r_min" and value <= 0:
            raise ConfigValidationError(f"model.target.{key} must be > 0.")
    if "max_holding_bars" in target and target["max_holding_bars"] is not None:
        _positive_int(target["max_holding_bars"], field="model.target.max_holding_bars")
    if "max_holding" in target and target["max_holding"] is not None:
        _positive_int(target["max_holding"], field="model.target.max_holding")
    if "allow_partial_horizon" in target and not isinstance(target.get("allow_partial_horizon"), bool):
        raise ConfigValidationError("model.target.allow_partial_horizon must be boolean.")
    diagnostic_cols = target.get("diagnostic_feature_cols")
    if diagnostic_cols is not None:
        if (
            not isinstance(diagnostic_cols, list)
            or any(not isinstance(col, str) or not col.strip() for col in diagnostic_cols)
        ):
            raise ConfigValidationError("model.target.diagnostic_feature_cols must be a list[str].")


def _validate_candidate_expected_r_target_block(target: dict[str, Any]) -> None:
    _validate_string_mapping(
        target.get("outputs"),
        field="model.target.outputs",
        allowed_keys=_TARGET_OUTPUT_KEYS,
    )
    for key in (
        "candidate_col",
        "side_col",
        "candidate_out_col",
        "label_col",
        "fwd_col",
        "event_ret_col",
        "trade_r_col",
        "trade_r_clipped_col",
        "entry_price_col",
        "exit_price_col",
        "stop_price_col",
        "take_profit_price_col",
        "exit_reason_col",
        "bars_held_col",
        "hit_step_col",
        "hit_type_col",
        "mfe_r_col",
        "mae_r_col",
        "time_to_mfe_col",
        "time_to_mae_col",
        "price_col",
        "open_col",
        "high_col",
        "low_col",
        "close_col",
        "volatility_col",
    ):
        if key in target and target[key] is not None and not isinstance(target[key], str):
            raise ConfigValidationError(f"model.target.{key} must be a string or null.")
    side = str(target.get("side", "long_only"))
    if side != "long_only":
        raise ConfigValidationError("model.target.side must be 'long_only'.")
    entry_price_mode = str(target.get("entry_price_mode", "next_open"))
    if entry_price_mode not in {"next_open", "current_close"}:
        raise ConfigValidationError("model.target.entry_price_mode must be one of: next_open, current_close.")
    stop_mode = str(target.get("stop_mode", "volatility_stop"))
    if stop_mode not in {"volatility_stop", "fixed_return"}:
        raise ConfigValidationError("model.target.stop_mode must be one of: volatility_stop, fixed_return.")
    tie_break = str(target.get("tie_break", "conservative"))
    if tie_break not in {"conservative", "take_profit", "stop_loss", "closest_to_open"}:
        raise ConfigValidationError(
            "model.target.tie_break must be one of: conservative, take_profit, stop_loss, closest_to_open."
        )
    for key, default in (
        ("target_r_min", 0.75),
        ("take_profit_r", 2.5),
        ("stop_loss_r", 1.5),
        ("stop_loss_return", 0.005),
    ):
        value = _finite_number(target.get(key, default), field=f"model.target.{key}")
        if key != "target_r_min" and value <= 0:
            raise ConfigValidationError(f"model.target.{key} must be > 0.")
    if "max_holding_bars" in target and target["max_holding_bars"] is not None:
        _positive_int(target["max_holding_bars"], field="model.target.max_holding_bars")
    clip_r = target.get("clip_r", [-2.0, 3.0])
    if not isinstance(clip_r, list) or len(clip_r) != 2:
        raise ConfigValidationError("model.target.clip_r must be a two-element list.")
    clip_low = _finite_number(clip_r[0], field="model.target.clip_r[0]")
    clip_high = _finite_number(clip_r[1], field="model.target.clip_r[1]")
    if clip_low > clip_high:
        raise ConfigValidationError("model.target.clip_r[0] must be <= model.target.clip_r[1].")
    if "allow_partial_horizon" in target and not isinstance(target.get("allow_partial_horizon"), bool):
        raise ConfigValidationError("model.target.allow_partial_horizon must be boolean.")


def _validate_path_dependent_r_target_block(target: dict[str, Any], *, field_prefix: str = "model.target") -> None:
    _validate_string_mapping(
        target.get("outputs"),
        field=f"{field_prefix}.outputs",
        allowed_keys=_TARGET_OUTPUT_KEYS,
    )
    for key in (
        "candidate_col",
        "side_col",
        "pred_is_oos_col",
        "meta_candidate_col",
        "meta_side_col",
        "entry_price_col",
        "exit_price_col",
        "exit_reason_col",
        "hit_type_col",
        "hit_step_col",
        "holding_bars_col",
        "gross_return_col",
        "net_return_col",
        "gross_r_col",
        "net_r_col",
        "mfe_r_col",
        "mae_r_col",
        "positive_label_col",
        "min_025_label_col",
        "min_050_label_col",
        "min_100_label_col",
        "price_col",
        "open_col",
        "high_col",
        "low_col",
        "close_col",
        "volatility_col",
    ):
        if key in target and target[key] is not None and not isinstance(target[key], str):
            raise ConfigValidationError(f"{field_prefix}.{key} must be a string or null.")
    stop_mode = str(target.get("stop_mode", "volatility_stop"))
    if stop_mode not in {"volatility_stop", "fixed_return"}:
        raise ConfigValidationError(f"{field_prefix}.stop_mode must be one of: volatility_stop, fixed_return.")
    entry_price_mode = str(target.get("entry_price_mode", "next_open"))
    if entry_price_mode not in {"next_open", "current_close"}:
        raise ConfigValidationError(f"{field_prefix}.entry_price_mode must be one of: next_open, current_close.")
    tie_break = str(target.get("tie_break", "conservative"))
    if tie_break not in {"conservative", "take_profit", "stop_loss", "closest_to_open"}:
        raise ConfigValidationError(
            f"{field_prefix}.tie_break must be one of: conservative, take_profit, stop_loss, closest_to_open."
        )
    for key, default in (
        ("take_profit_r", 5.0),
        ("stop_loss_r", 2.0),
        ("risk_per_trade", 0.006),
        ("max_leverage", 1.0),
    ):
        value = _finite_number(target.get(key, default), field=f"{field_prefix}.{key}")
        if value <= 0.0:
            raise ConfigValidationError(f"{field_prefix}.{key} must be > 0.")
    for key in ("cost_per_unit_turnover", "cost_per_turnover", "slippage_per_unit_turnover", "slippage_per_turnover"):
        if key in target and target[key] is not None:
            value = _finite_number(target.get(key), field=f"{field_prefix}.{key}")
            if value < 0.0:
                raise ConfigValidationError(f"{field_prefix}.{key} must be >= 0.")
    if "max_holding_bars" in target and target["max_holding_bars"] is not None:
        _positive_int(target["max_holding_bars"], field=f"{field_prefix}.max_holding_bars")
    if "max_holding" in target and target["max_holding"] is not None:
        _positive_int(target["max_holding"], field=f"{field_prefix}.max_holding")
    for key in ("require_oos", "allow_partial_horizon", "apply_risk_sizing", "legacy_same_bar_stop_reason"):
        if key in target and not isinstance(target.get(key), bool):
            raise ConfigValidationError(f"{field_prefix}.{key} must be boolean.")


def validate_model_block(model: dict[str, Any]) -> None:
    if "kind" not in model:
        raise ConfigValidationError("model.kind is required.")
    if not isinstance(model["kind"], str):
        raise ConfigValidationError("model.kind must be a string.")
    if model["kind"] != "none" and model["kind"] not in MODEL_KINDS:
        raise ConfigValidationError(f"Unknown model kind: {model['kind']}")
    _validate_string_mapping(
        model.get("outputs"),
        field="model.outputs",
        allowed_keys=_MODEL_OUTPUT_KEYS | _TARGET_OUTPUT_KEYS,
    )
    for key in _MODEL_OUTPUT_KEYS:
        if key in model and model[key] is not None and not isinstance(model[key], str):
            raise ConfigValidationError(f"model.{key} must be a string when provided.")

    if model["kind"] == "none":
        target = model.get("target", {}) or {}
        if not isinstance(target, dict):
            raise ConfigValidationError("model.target must be a mapping when provided.")
        if target:
            target_for_validation = _flatten_target_cfg_for_validation(target)
            _validate_string_mapping(
                target_for_validation.get("outputs"),
                field="model.target.outputs",
                allowed_keys=_TARGET_OUTPUT_KEYS,
            )
            target_kind = target_for_validation.get("kind", "forward_return")
            if target_kind not in {"r_multiple", "candidate_expected_r", "path_dependent_r"}:
                raise ConfigValidationError(
                    "model.kind='none' currently supports only model.target.kind='r_multiple' or "
                    "'candidate_expected_r' or 'path_dependent_r' "
                    "for target-only diagnostics."
                )
            if target_kind == "r_multiple":
                _validate_r_multiple_target_block(target_for_validation)
            elif target_kind == "candidate_expected_r":
                _validate_candidate_expected_r_target_block(target_for_validation)
            else:
                _validate_path_dependent_r_target_block(target_for_validation)
        return

    if model["kind"] != "none":
        calibration = model.get("calibration", {}) or {}
        if not isinstance(calibration, dict):
            raise ConfigValidationError("model.calibration must be a mapping when provided.")
        calibration_method = str(calibration.get("method", "none") or "none").strip().lower()
        if calibration_method not in {"none", "sigmoid"}:
            raise ConfigValidationError("model.calibration.method must be one of: none, sigmoid.")
        if calibration_method != "none":
            fraction = _finite_number(calibration.get("fraction", 0.20), field="model.calibration.fraction")
            if not 0.0 < fraction < 0.5:
                raise ConfigValidationError("model.calibration.fraction must be in (0, 0.5).")
            _positive_int(calibration.get("min_rows", 200), field="model.calibration.min_rows")
        feature_cols = model.get("feature_cols")
        if feature_cols is not None:
            if (
                not isinstance(feature_cols, list)
                or (not feature_cols and model["kind"] != "chronos_2_forecaster")
                or any(not isinstance(col, str) or not col.strip() for col in feature_cols)
            ):
                raise ConfigValidationError(
                    "model.feature_cols must be a non-empty list[str] when provided, except that "
                    "chronos_2_forecaster permits [] for univariate mode."
                )
        _validate_feature_selectors(model.get("feature_selectors"), field="model.feature_selectors")

        target = model.get("target", {}) or {}
        if not isinstance(target, dict):
            raise ConfigValidationError("model.target must be a mapping when provided.")
        if model["kind"] in _EXPERIMENTAL_DISCOVERY_MODEL_KINDS:
            if target not in ({}, None):
                raise ConfigValidationError(
                    "tsfresh_extrema_feature_discovery manages its own future-horizon labels; "
                    "do not set model.target."
                )
        else:
            target = _flatten_target_cfg_for_validation(target)
            _validate_string_mapping(
                target.get("outputs"),
                field="model.target.outputs",
                allowed_keys=_TARGET_OUTPUT_KEYS,
            )
            target_kind = target.get("kind", "forward_return")
            if target_kind not in TARGET_KINDS:
                allowed_targets = "', '".join(sorted(TARGET_KINDS))
                raise ConfigValidationError(
                    f"model.target.kind must be one of: '{allowed_targets}'."
                )
            if target_kind == "path_dependent_r":
                raise ConfigValidationError(
                    "model.target.kind='path_dependent_r' is post-model only; configure it as top-level target."
                )
            if model["kind"] in _FOUNDATION_FORECASTER_MODEL_KINDS and target_kind not in {
                "forward_return",
                "future_return_regression",
            }:
                raise ConfigValidationError(
                    "Foundation forecasters currently support only "
                    "model.target.kind='forward_return' or 'future_return_regression'."
                )
            if target_kind == "r_multiple":
                if model["kind"] not in _CLASSIFIER_MODEL_KINDS:
                    raise ConfigValidationError(
                        "model.target.kind='r_multiple' is currently supported only for classifiers "
                        "or model.kind='none' target-only diagnostics."
                    )
                _validate_r_multiple_target_block(target)
            if target_kind == "candidate_expected_r":
                if model["kind"] not in _CLASSIFIER_MODEL_KINDS:
                    raise ConfigValidationError(
                        "model.target.kind='candidate_expected_r' is currently supported only for classifiers "
                        "or model.kind='none' target-only diagnostics."
                    )
                _validate_candidate_expected_r_target_block(target)
            if target_kind in {"triple_barrier", "directional_triple_barrier"} and model["kind"] not in _CLASSIFIER_MODEL_KINDS:
                if model["kind"] not in _EMBEDDING_MODEL_KINDS and model["kind"] not in _FORECASTER_MODEL_KINDS:
                    raise ConfigValidationError(
                        "model.target.kind='triple_barrier' or 'directional_triple_barrier' is currently "
                        "supported only for classifiers, event_transformer_encoder, and regression "
                        "forecasters with a target_col."
                    )
                if model["kind"] in _FORECASTER_MODEL_KINDS:
                    regression_target_col = target.get("target_col", target.get("regression_target_col"))
                    if regression_target_col is None:
                        raise ConfigValidationError(
                            "regression forecasters using target.kind='triple_barrier' or "
                            "'directional_triple_barrier' must set model.target.target_col or "
                            "model.target.regression_target_col."
                        )
                    if not isinstance(regression_target_col, str) or not regression_target_col.strip():
                        raise ConfigValidationError(
                            "model.target.target_col must be a non-empty string when provided."
                        )
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
            if target_kind in _REGRESSION_TARGET_KINDS:
                if model["kind"] not in _FORECASTER_MODEL_KINDS:
                    raise ConfigValidationError(
                        f"model.target.kind='{target_kind}' is supported only for regression forecasters."
                    )
                _positive_int(
                    target.get("horizon_bars", target.get("horizon", 1)),
                    field="model.target.horizon_bars",
                )
                for key in (
                    "price_col",
                    "returns_col",
                    "benchmark_price_col",
                    "benchmark_returns_col",
                    "volatility_col",
                    "high_col",
                    "low_col",
                    "label_col",
                    "fwd_col",
                    "raw_fwd_col",
                    "normalizer_col",
                    "risk_distance_col",
                    "realized_vol_col",
                    "mfe_col",
                    "mae_col",
                    "beta_col",
                    "benchmark_fwd_col",
                ):
                    if key in target and target[key] is not None and not isinstance(target[key], str):
                        raise ConfigValidationError(f"model.target.{key} must be a string or null.")
                returns_type = str(target.get("returns_type", "simple"))
                if returns_type not in {"simple", "log"}:
                    raise ConfigValidationError("model.target.returns_type must be 'simple' or 'log'.")
                if (
                    target_kind
                    in {
                        "future_return_regression",
                        "volatility_normalized_future_return",
                        "risk_adjusted_future_return",
                        "r_multiple_regression",
                    }
                    and target.get("returns_col") is None
                    and returns_type != "simple"
                ):
                    raise ConfigValidationError("model.target.returns_type='log' requires model.target.returns_col.")
                if target_kind in {"excess_return_regression", "residual_return_regression"}:
                    if returns_type == "log" and (
                        target.get("returns_col") is None or target.get("benchmark_returns_col") is None
                    ):
                        raise ConfigValidationError(
                            "model.target.returns_type='log' requires model.target.returns_col "
                            "and model.target.benchmark_returns_col."
                        )
                for key in ("normalize_by_volatility", "normalize_by_price", "annualize", "signed"):
                    if key in target and not isinstance(target[key], bool):
                        raise ConfigValidationError(f"model.target.{key} must be boolean.")
                clip = target.get("clip")
                if clip is not None:
                    if not isinstance(clip, (list, tuple)) or len(clip) != 2:
                        raise ConfigValidationError("model.target.clip must be a [low, high] pair.")
                    if float(clip[0]) >= float(clip[1]):
                        raise ConfigValidationError("model.target.clip must satisfy low < high.")
            quantiles = target.get("quantiles")
            if quantiles is not None:
                if not isinstance(quantiles, (list, tuple)) or len(quantiles) != 2:
                    raise ConfigValidationError("model.target.quantiles must be a [low, high] pair.")
                q_low, q_high = float(quantiles[0]), float(quantiles[1])
                if not (0.0 <= q_low < q_high <= 1.0):
                    raise ConfigValidationError("model.target.quantiles must satisfy 0 <= low < high <= 1.")
                if target_kind != "forward_return":
                    raise ConfigValidationError("model.target.quantiles are only supported for target.kind='forward_return'.")
        if model["kind"] not in _EXPERIMENTAL_DISCOVERY_MODEL_KINDS and target_kind == "triple_barrier":
            for key in (
                "open_col",
                "high_col",
                "low_col",
                "returns_col",
                "volatility_col",
                "label_col",
                "event_ret_col",
                "fwd_col",
                "r_col",
                "oriented_r_col",
                "hit_step_col",
                "hit_type_col",
                "upper_barrier_col",
                "lower_barrier_col",
                "meta_side_col",
                "oriented_ret_col",
                "vol_source_col",
                "target_col",
                "regression_target_col",
            ):
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
            entry_price_mode = target.get("entry_price_mode", "current_close")
            if entry_price_mode not in {"current_close", "next_open"}:
                raise ConfigValidationError(
                    "model.target.entry_price_mode must be one of: current_close, next_open."
                )
            label_mode = target.get("label_mode")
            if label_mode is not None and label_mode not in {"binary", "ternary", "meta"}:
                raise ConfigValidationError("model.target.label_mode must be one of: binary, ternary, meta.")
            if label_mode == "meta" and target.get("side_col") is None:
                raise ConfigValidationError("model.target.label_mode='meta' requires model.target.side_col.")
            if "add_r_multiple" in target and not isinstance(target.get("add_r_multiple"), bool):
                raise ConfigValidationError("model.target.add_r_multiple must be boolean.")
            if target.get("r_clip") is not None:
                r_clip = target.get("r_clip")
                if isinstance(r_clip, bool):
                    raise ConfigValidationError("model.target.r_clip must be a finite number or [low, high] pair.")
                if isinstance(r_clip, (int, float)):
                    if _finite_number(r_clip, field="model.target.r_clip") <= 0:
                        raise ConfigValidationError("model.target.r_clip must be > 0 when scalar.")
                elif isinstance(r_clip, (list, tuple)) and len(r_clip) == 2:
                    low = _finite_number(r_clip[0], field="model.target.r_clip[0]")
                    high = _finite_number(r_clip[1], field="model.target.r_clip[1]")
                    if low >= high:
                        raise ConfigValidationError("model.target.r_clip must satisfy low < high.")
                else:
                    raise ConfigValidationError("model.target.r_clip must be a finite number or [low, high] pair.")
            candidate_mode = str(target.get("candidate_mode", "all_nonzero"))
            if candidate_mode not in {"all_nonzero", "side_change"}:
                raise ConfigValidationError("model.target.candidate_mode must be one of: all_nonzero, side_change.")
        if model["kind"] not in _EXPERIMENTAL_DISCOVERY_MODEL_KINDS and target_kind == "directional_triple_barrier":
            for key in (
                "open_col",
                "high_col",
                "low_col",
                "volatility_col",
                "label_col",
                "event_ret_col",
                "fwd_col",
                "r_col",
                "oriented_r_col",
                "hit_step_col",
                "hit_type_col",
                "upper_barrier_col",
                "lower_barrier_col",
                "meta_side_col",
                "oriented_ret_col",
                "direction_col",
                "side_col",
                "candidate_col",
                "candidate_out_col",
            ):
                if key in target and target[key] is not None and not isinstance(target[key], str):
                    raise ConfigValidationError(f"model.target.{key} must be a string or null.")
            _positive_int(
                target.get("vertical_barrier_bars", target.get("max_holding", target.get("horizon", 4))),
                field="model.target.vertical_barrier_bars",
            )
            for key in ("profit_barrier_r", "stop_barrier_r", "min_vol"):
                default = 1.4 if key == "profit_barrier_r" else 1.0
                if key == "min_vol":
                    default = 1e-12
                value = _finite_number(target.get(key, default), field=f"model.target.{key}")
                if value <= 0:
                    raise ConfigValidationError(f"model.target.{key} must be > 0.")
            neutral_label = target.get("neutral_label", "drop")
            if neutral_label not in {"drop", "profit", "stop"}:
                raise ConfigValidationError("model.target.neutral_label must be one of: drop, profit, stop.")
            tie_break = target.get("tie_break", "closest_to_open")
            if tie_break not in {"closest_to_open", "profit", "stop"}:
                raise ConfigValidationError("model.target.tie_break must be one of: closest_to_open, profit, stop.")
            entry_price_mode = target.get("entry_price_mode", "current_close")
            if entry_price_mode not in {"current_close", "next_open"}:
                raise ConfigValidationError(
                    "model.target.entry_price_mode must be one of: current_close, next_open."
                )
            if "add_r_multiple" in target and not isinstance(target.get("add_r_multiple"), bool):
                raise ConfigValidationError("model.target.add_r_multiple must be boolean.")
            if target.get("r_clip") is not None:
                r_clip = target.get("r_clip")
                if isinstance(r_clip, bool):
                    raise ConfigValidationError("model.target.r_clip must be a finite number or [low, high] pair.")
                if isinstance(r_clip, (int, float)):
                    if _finite_number(r_clip, field="model.target.r_clip") <= 0:
                        raise ConfigValidationError("model.target.r_clip must be > 0 when scalar.")
                elif isinstance(r_clip, (list, tuple)) and len(r_clip) == 2:
                    low = _finite_number(r_clip[0], field="model.target.r_clip[0]")
                    high = _finite_number(r_clip[1], field="model.target.r_clip[1]")
                    if low >= high:
                        raise ConfigValidationError("model.target.r_clip must satisfy low < high.")
                else:
                    raise ConfigValidationError("model.target.r_clip must be a finite number or [low, high] pair.")
        if model["kind"] in _EMBEDDING_MODEL_KINDS:
            if target_kind != "triple_barrier":
                raise ConfigValidationError(
                    "event_transformer_encoder requires model.target.kind='triple_barrier'."
                )
            if target.get("candidate_col") is None:
                raise ConfigValidationError(
                    "event_transformer_encoder requires model.target.candidate_col for event-driven training."
                )
            if target.get("side_col") is None:
                raise ConfigValidationError(
                    "event_transformer_encoder requires model.target.side_col for contrarian event labeling."
                )

        preprocessing = model.get("preprocessing", {}) or {}
        if preprocessing:
            if model["kind"] in _EXPERIMENTAL_DISCOVERY_MODEL_KINDS:
                raise ConfigValidationError(
                    "tsfresh_extrema_feature_discovery does not support model.preprocessing."
                )
            if not isinstance(preprocessing, dict):
                raise ConfigValidationError("model.preprocessing must be a mapping when provided.")
            scaler = str(preprocessing.get("scaler", "none"))
            if scaler not in {"none", "standard", "robust"}:
                raise ConfigValidationError("model.preprocessing.scaler must be one of: none, standard, robust.")

        overlay = model.get("overlay", {}) or {}
        if overlay:
            if model["kind"] in _EXPERIMENTAL_DISCOVERY_MODEL_KINDS:
                raise ConfigValidationError(
                    "tsfresh_extrema_feature_discovery does not support model.overlay."
                )
            if not isinstance(overlay, dict):
                raise ConfigValidationError("model.overlay must be a mapping when provided.")
            if model["kind"] not in _GARCH_OVERLAY_COMPATIBLE_MODEL_KINDS:
                raise ConfigValidationError(
                    "model.overlay is currently supported only for elastic_net_clf, lightgbm_clf, "
                    "logistic_regression_clf, xgboost_clf, sarimax_forecaster, lstm_forecaster, "
                    "patchtst_forecaster, tft_forecaster, and foundation forecasters."
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

        if model["kind"] in (_DEEP_FORECASTER_MODEL_KINDS | _EMBEDDING_MODEL_KINDS):
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
        if model["kind"] in _EMBEDDING_MODEL_KINDS:
            params = dict(model.get("params", {}) or {})
            if "embedding_dim" in params:
                _positive_int(params["embedding_dim"], field="model.params.embedding_dim")
            if "min_train_samples" in params:
                _positive_int(params["min_train_samples"], field="model.params.min_train_samples")
            if "embedding_prefix" in params:
                prefix = params["embedding_prefix"]
                if not isinstance(prefix, str) or not prefix.strip():
                    raise ConfigValidationError("model.params.embedding_prefix must be a non-empty string.")
        if model["kind"] in _FOUNDATION_FORECASTER_MODEL_KINDS:
            _validate_foundation_forecaster_params(model["kind"], dict(model.get("params", {}) or {}))
        if model["kind"] == "chronos_2_forecaster":
            _validate_chronos2_covariate_contract(model, target)

        params = model.get("params", {}) or {}
        if not isinstance(params, dict):
            raise ConfigValidationError("model.params must be a mapping.")
        if model["kind"] in _EXPERIMENTAL_DISCOVERY_MODEL_KINDS:
            _validate_tsfresh_extrema_discovery_params(params)
        if model["kind"] == "elastic_net_clf":
            penalty = str(params.get("penalty", "elasticnet"))
            if penalty != "elasticnet":
                raise ConfigValidationError("elastic_net_clf requires model.params.penalty='elasticnet'.")
            solver = str(params.get("solver", "saga"))
            if solver != "saga":
                raise ConfigValidationError("elastic_net_clf requires model.params.solver='saga'.")
            if "l1_ratio" in params:
                l1_ratio = _finite_number(params["l1_ratio"], field="model.params.l1_ratio")
                if not 0.0 <= l1_ratio <= 1.0:
                    raise ConfigValidationError("model.params.l1_ratio must be in [0,1].")
            if "C" in params:
                regularization_c = _finite_number(params["C"], field="model.params.C")
                if regularization_c <= 0.0:
                    raise ConfigValidationError("model.params.C must be > 0.")
            if "max_iter" in params:
                _positive_int(params["max_iter"], field="model.params.max_iter")
        if model["kind"] in {"xgboost_clf", "xgboost_regressor"}:
            invalid_keys = [
                key
                for key in _XGBOOST_UNSUPPORTED_PARAM_KEYS
                if key in params and params[key] is not None
            ]
            if invalid_keys:
                joined = ", ".join(sorted(invalid_keys))
                raise ConfigValidationError(
                    f"{model['kind']} does not support LightGBM-only params: "
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
    if "synchronize_assets" in split and not isinstance(split["synchronize_assets"], bool):
        raise ConfigValidationError("model.split.synchronize_assets must be boolean.")


def validate_standalone_target_block(target: Any) -> None:
    if target in (None, {}):
        return
    if not isinstance(target, dict):
        raise ConfigValidationError("target must be a mapping when provided.")
    target_cfg = _flatten_target_cfg_for_validation(target)
    _validate_string_mapping(
        target_cfg.get("outputs"),
        field="target.outputs",
        allowed_keys=_TARGET_OUTPUT_KEYS,
    )
    target_kind = target_cfg.get("kind", "forward_return")
    if target_kind not in TARGET_KINDS:
        allowed_targets = "', '".join(sorted(TARGET_KINDS))
        raise ConfigValidationError(
            f"target.kind must be one of: '{allowed_targets}'."
        )
    if target_kind in _POST_MODEL_TARGET_KINDS:
        _validate_path_dependent_r_target_block(target_cfg, field_prefix="target")
        return
    validate_model_block(
        {
            "kind": "lightgbm_regressor" if target_kind in _REGRESSION_TARGET_KINDS else "xgboost_clf",
            "feature_cols": ["__standalone_target_validation__"],
            "target": target_cfg,
        }
    )


def _model_emitted_columns(model: dict[str, Any]) -> dict[str, str]:
    kind = str(model.get("kind", "none"))
    pred_is_oos_col = str(model.get("pred_is_oos_col") or "pred_is_oos")
    explicit_oos = model.get("pred_is_oos_col") is not None
    if kind in _CLASSIFIER_MODEL_KINDS:
        emitted = {
            "pred_prob_col": str(model.get("pred_prob_col") or "pred_prob"),
        }
        if explicit_oos:
            emitted["pred_is_oos_col"] = pred_is_oos_col
        return emitted
    if kind in _EMBEDDING_MODEL_KINDS:
        emitted = {
            f"embedding_col_{idx}": col
            for idx, col in enumerate(_resolve_event_embedding_columns(model))
        }
        if explicit_oos:
            emitted["pred_is_oos_col"] = pred_is_oos_col
        if model.get("pred_prob_col") is not None:
            emitted["pred_prob_col"] = str(model.get("pred_prob_col"))
        return emitted
    if kind in _FORECASTER_MODEL_KINDS:
        emitted = {
            "pred_ret_col": str(model.get("pred_ret_col") or "pred_ret"),
            "pred_prob_col": str(model.get("pred_prob_col") or "pred_prob"),
        }
        if explicit_oos:
            emitted["pred_is_oos_col"] = pred_is_oos_col
        return emitted
    if kind in RL_MODEL_KINDS:
        emitted = {
            "signal_col": str(model.get("signal_col") or "signal_rl"),
            "action_col": str(model.get("action_col") or "action_rl"),
        }
        if explicit_oos:
            emitted["pred_is_oos_col"] = pred_is_oos_col
        return emitted
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
        if kind in RL_MODEL_KINDS or kind in PORTFOLIO_MODEL_KINDS or kind in _EXPERIMENTAL_DISCOVERY_MODEL_KINDS:
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


def _validate_c1_trend_pullback_vwap_params(params: dict[str, Any], *, field_prefix: str) -> None:
    string_keys = {
        "trend_regime_col",
        "long_trigger_col",
        "short_trigger_col",
        "ppo_hist_col",
        "ppo_above_signal_col",
        "ppo_below_signal_col",
        "mfi_col",
        "stoch_k_col",
        "stoch_d_col",
        "zscore_momentum_col",
        "volatility_regime_col",
        "trend_quality_col",
        "long_candidate_col",
        "short_candidate_col",
        "long_candidate_strict_col",
        "short_candidate_strict_col",
        "signal_col",
        "candidate_col",
    }
    for key in string_keys:
        if key in params and params[key] is not None and not isinstance(params[key], str):
            raise ConfigValidationError(f"{field_prefix}.{key} must be a string.")
    if "mode" in params and params.get("mode") is not None:
        mode = str(params.get("mode"))
        if mode not in {"long_only", "short_only", "long_short"}:
            raise ConfigValidationError(
                f"{field_prefix}.mode must be one of: long_only, short_only, long_short."
            )
    if "use_strict_signal" in params and not isinstance(params["use_strict_signal"], bool):
        raise ConfigValidationError(f"{field_prefix}.use_strict_signal must be boolean.")

    numeric_keys = {
        "mfi_long_min",
        "mfi_long_max",
        "mfi_short_min",
        "mfi_short_max",
        "long_zscore_min",
        "short_zscore_max",
        "max_volatility_regime",
        "strict_trend_quality_min",
        "strict_mfi_long_min",
        "strict_mfi_short_max",
        "strict_long_zscore_min",
        "strict_short_zscore_max",
    }
    values: dict[str, float] = {}
    for key in numeric_keys:
        if key in params:
            values[key] = _finite_number(params[key], field=f"{field_prefix}.{key}")

    mfi_long_min = values.get("mfi_long_min", float(params.get("mfi_long_min", 40.0)))
    mfi_long_max = values.get("mfi_long_max", float(params.get("mfi_long_max", 80.0)))
    if mfi_long_min > mfi_long_max:
        raise ConfigValidationError(f"{field_prefix}.mfi_long_min must be <= {field_prefix}.mfi_long_max.")
    mfi_short_min = values.get("mfi_short_min", float(params.get("mfi_short_min", 20.0)))
    mfi_short_max = values.get("mfi_short_max", float(params.get("mfi_short_max", 60.0)))
    if mfi_short_min > mfi_short_max:
        raise ConfigValidationError(f"{field_prefix}.mfi_short_min must be <= {field_prefix}.mfi_short_max.")

    trend_quality_min = values.get(
        "strict_trend_quality_min",
        float(params.get("strict_trend_quality_min", 0.35)),
    )
    if not 0.0 <= trend_quality_min <= 1.0:
        raise ConfigValidationError(f"{field_prefix}.strict_trend_quality_min must be in [0,1].")


def validate_signals_block(signals: dict[str, Any]) -> None:
    if "kind" not in signals:
        raise ConfigValidationError("signals.kind is required.")
    if not isinstance(signals["kind"], str):
        raise ConfigValidationError("signals.kind must be a string.")
    if signals["kind"] != "none" and signals["kind"] not in SIGNAL_KINDS:
        raise ConfigValidationError(f"Unknown signals kind: {signals['kind']}")
    params = signals.get("params", {}) or {}
    if not isinstance(params, dict):
        raise ConfigValidationError("signals.params must be a mapping when provided.")
    params_by_asset = signals.get("params_by_asset", {})
    if not isinstance(params_by_asset, dict):
        raise ConfigValidationError("signals.params_by_asset must be a mapping when provided.")
    for asset, asset_params in dict(params_by_asset or {}).items():
        if not isinstance(asset, str) or not asset.strip():
            raise ConfigValidationError("signals.params_by_asset keys must be non-empty strings.")
        if not isinstance(asset_params, dict):
            raise ConfigValidationError("signals.params_by_asset values must be mappings.")
    _validate_string_mapping(
        signals.get("outputs"),
        field="signals.outputs",
    )
    if "signal_name" in params:
        raise ConfigValidationError("signals.params.signal_name is no longer supported; use signals.params.signal_col.")
    if "signal_col" in params and params["signal_col"] is not None and not isinstance(params["signal_col"], str):
        raise ConfigValidationError("signals.params.signal_col must be a string.")
    if signals["kind"] == "dense_return_forecast":
        for key in ("forecast_col", "expected_net_return_col", "estimated_cost_col", "volatility_col", "price_col"):
            if key in params and params[key] is not None and not isinstance(params[key], str):
                raise ConfigValidationError(f"signals.params.{key} must be a string.")
        for key in ("cost_per_turnover", "slippage_per_turnover", "cost_round_trip_mult", "volatility_floor"):
            if key in params and _finite_number(params[key], field=f"signals.params.{key}") < 0:
                raise ConfigValidationError(f"signals.params.{key} must be >= 0.")
        if "volatility_floor" in params and float(params["volatility_floor"]) <= 0.0:
            raise ConfigValidationError("signals.params.volatility_floor must be > 0.")
        if "forecast_is_vol_normalized" in params and not isinstance(params["forecast_is_vol_normalized"], bool):
            raise ConfigValidationError("signals.params.forecast_is_vol_normalized must be boolean.")
        if "signed_cost_adjustment" in params and not isinstance(params["signed_cost_adjustment"], bool):
            raise ConfigValidationError("signals.params.signed_cost_adjustment must be boolean.")
        if "clip" in params and params["clip"] is not None and _finite_number(params["clip"], field="signals.params.clip") <= 0:
            raise ConfigValidationError("signals.params.clip must be > 0 when provided.")
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
        vol_target = params.get("vol_target", 0.001)
        if vol_target is not None:
            vol_target = _finite_number(vol_target, field="signals.params.vol_target")
        if vol_target is not None and vol_target <= 0:
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
        for key in ("top_quantile", "max_trade_rate"):
            if params.get(key) is not None:
                value = _finite_number(params.get(key), field=f"signals.params.{key}")
                if not 0.0 < value <= 1.0:
                    raise ConfigValidationError(f"signals.params.{key} must be in (0,1].")
        if params.get("top_quantile_window") is not None:
            _positive_int(params.get("top_quantile_window"), field="signals.params.top_quantile_window")
            if int(params.get("top_quantile_window")) <= 1:
                raise ConfigValidationError("signals.params.top_quantile_window must be > 1.")
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
                _validate_column_ref_or_selector(
                    raw_filter,
                    col_key="col",
                    selector_key="selector",
                    field=f"signals.params.activation_filters[{idx}]",
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
    if signals["kind"] == "forecast_threshold_hysteresis":
        for key in ("forecast_col", "signal_col"):
            if key in params and params[key] is not None and not isinstance(params[key], str):
                raise ConfigValidationError(f"signals.params.{key} must be a string or null.")
        long_entry = _finite_number(params.get("long_entry", 0.75), field="signals.params.long_entry")
        long_exit = _finite_number(params.get("long_exit", 0.25), field="signals.params.long_exit")
        short_entry = _finite_number(params.get("short_entry", -0.75), field="signals.params.short_entry")
        short_exit = _finite_number(params.get("short_exit", -0.25), field="signals.params.short_exit")
        if not long_exit < long_entry:
            raise ConfigValidationError("signals.params.long_exit must be < signals.params.long_entry.")
        if not short_entry < short_exit:
            raise ConfigValidationError("signals.params.short_entry must be < signals.params.short_exit.")
        _non_negative_int(params.get("cooldown_bars", 0), field="signals.params.cooldown_bars")
        _non_negative_int(params.get("min_holding_bars", 0), field="signals.params.min_holding_bars")
    if signals["kind"] == "meta_probability_side":
        for key in ("prob_col", "side_col", "candidate_col", "pred_is_oos_col", "expected_value_col", "signal_col"):
            if key in params and params[key] is not None and not isinstance(params[key], str):
                raise ConfigValidationError(f"signals.params.{key} must be a string or null.")
        if "mode" in params and params.get("mode") is not None:
            mode = str(params.get("mode"))
            if mode not in {"long_only", "short_only", "long_short"}:
                raise ConfigValidationError(
                    "signals.params.mode must be one of: long_only, short_only, long_short."
                )
        threshold = params.get("threshold", params.get("upper", 0.5))
        threshold = _finite_number(threshold, field="signals.params.threshold")
        if not 0.0 < threshold < 1.0:
            raise ConfigValidationError("signals.params.threshold must be in (0,1).")
        if "upper" in params and params.get("upper") is not None:
            upper = _finite_number(params.get("upper"), field="signals.params.upper")
            if not 0.0 < upper < 1.0:
                raise ConfigValidationError("signals.params.upper must be in (0,1).")
        clip = _finite_number(params.get("clip", 1.0), field="signals.params.clip")
        if clip <= 0:
            raise ConfigValidationError("signals.params.clip must be > 0.")
        if params.get("min_expected_value_r") is not None:
            _finite_number(params.get("min_expected_value_r"), field="signals.params.min_expected_value_r")
        for key in ("profit_barrier_r", "stop_barrier_r"):
            value = _finite_number(params.get(key, 1.0), field=f"signals.params.{key}")
            if value <= 0:
                raise ConfigValidationError(f"signals.params.{key} must be > 0.")
    if signals["kind"] == "orb_candidate_side":
        for key in ("candidate_col", "side_col", "signal_col"):
            if key in params and params[key] is not None and not isinstance(params[key], str):
                raise ConfigValidationError(f"signals.params.{key} must be a string or null.")
        if "mode" in params and params.get("mode") is not None:
            mode = str(params.get("mode"))
            if mode not in {"long_only", "short_only", "long_short"}:
                raise ConfigValidationError(
                    "signals.params.mode must be one of: long_only, short_only, long_short."
                )
    if signals["kind"] == "manual_long_model_filter":
        for key in (
            "prob_col",
            "candidate_col",
            "base_signal_col",
            "signal_col",
            "gate_col",
            "expected_value_col",
            "volatility_col",
        ):
            if key in params and params[key] is not None and not isinstance(params[key], str):
                raise ConfigValidationError(f"signals.params.{key} must be a string or null.")
        if params.get("gate_cols_any") is not None:
            gate_cols_any = params.get("gate_cols_any")
            if not isinstance(gate_cols_any, list):
                raise ConfigValidationError("signals.params.gate_cols_any must be a list when provided.")
            if any(not isinstance(col, str) or not col.strip() for col in gate_cols_any):
                raise ConfigValidationError("signals.params.gate_cols_any entries must be non-empty strings.")
        threshold = _finite_number(params.get("threshold", 0.55), field="signals.params.threshold")
        if not 0.0 < threshold < 1.0:
            raise ConfigValidationError("signals.params.threshold must be in (0,1).")
        min_signal_abs = _finite_number(
            params.get("min_signal_abs", 0.0),
            field="signals.params.min_signal_abs",
        )
        if min_signal_abs < 0.0:
            raise ConfigValidationError("signals.params.min_signal_abs must be >= 0.")
        if params.get("min_expected_value_r") is not None:
            _finite_number(params.get("min_expected_value_r"), field="signals.params.min_expected_value_r")
        for key in ("round_trip_cost_return", "cost_buffer_r"):
            value = _finite_number(params.get(key, 0.0), field=f"signals.params.{key}")
            if value < 0.0:
                raise ConfigValidationError(f"signals.params.{key} must be >= 0.")
        if float(params.get("round_trip_cost_return", 0.0) or 0.0) > 0.0 and not params.get("volatility_col"):
            raise ConfigValidationError(
                "signals.params.volatility_col is required when round_trip_cost_return > 0."
            )
        for key in ("profit_barrier_r", "stop_barrier_r"):
            value = _finite_number(params.get(key, 1.0), field=f"signals.params.{key}")
            if value <= 0.0:
                raise ConfigValidationError(f"signals.params.{key} must be > 0.")
    if signals["kind"] == "roc_long_only_conditions":
        nullable_string_keys = {
            "roc_col",
            "regime_vol_ratio_z_col",
            "macro_condition_col",
            "signal_col",
        }
        string_keys = {
            "close_z_col",
            "close_open_ratio_col",
            "mtf_1h_col",
            "mtf_4h_col",
            "is_weekend_col",
            "long_signal_col",
            "score_col",
            "all_conditions_col",
            "vol_adjusted_col",
            "short_signal_col",
            "combined_signal_col",
        }
        for key in nullable_string_keys:
            if key in params and params[key] is not None and not isinstance(params[key], str):
                raise ConfigValidationError(f"signals.params.{key} must be a string or null.")
        for key in string_keys:
            if key in params and not isinstance(params[key], str):
                raise ConfigValidationError(f"signals.params.{key} must be a string.")
        for key in ("roc_window", "vol_short_window", "vol_long_window"):
            if key in params:
                _positive_int(params[key], field=f"signals.params.{key}")
        if "min_score_required" in params:
            _non_negative_int(params["min_score_required"], field="signals.params.min_score_required")
        for key in (
            "roc_min",
            "vol_z_min",
            "vol_z_max",
            "close_z_min",
            "close_z_max",
            "close_open_ratio_min",
            "mtf_1h_min",
            "mtf_4h_min",
            "vol_adjustment_strength",
            "min_exposure",
            "max_exposure",
        ):
            if key in params:
                _finite_number(params[key], field=f"signals.params.{key}")
        if float(params.get("vol_z_min", -1.5)) > float(params.get("vol_z_max", 1.75)):
            raise ConfigValidationError("signals.params.vol_z_min must be <= signals.params.vol_z_max.")
        if float(params.get("close_z_min", -0.25)) > float(params.get("close_z_max", 2.25)):
            raise ConfigValidationError("signals.params.close_z_min must be <= signals.params.close_z_max.")
        if float(params.get("vol_adjustment_strength", 0.9)) < 0.0:
            raise ConfigValidationError("signals.params.vol_adjustment_strength must be >= 0.")
        if float(params.get("min_exposure", 0.10)) < 0.0:
            raise ConfigValidationError("signals.params.min_exposure must be >= 0.")
        if float(params.get("max_exposure", 1.0)) <= 0.0:
            raise ConfigValidationError("signals.params.max_exposure must be > 0.")
        if float(params.get("min_exposure", 0.10)) > float(params.get("max_exposure", 1.0)):
            raise ConfigValidationError("signals.params.min_exposure must be <= signals.params.max_exposure.")
        if "require_all_conditions" in params and not isinstance(params["require_all_conditions"], bool):
            raise ConfigValidationError("signals.params.require_all_conditions must be boolean.")
    if signals["kind"] == "ppo_adx_stochrsi_trend":
        _validate_ppo_adx_stochrsi_trend_params(params, field_prefix="signals.params")
    if signals["kind"] == "c1_trend_pullback_vwap":
        _validate_c1_trend_pullback_vwap_params(params, field_prefix="signals.params")
    if signals["kind"] == "stc_roofing_hilbert":
        _validate_stc_roofing_hilbert_params(params, field_prefix="signals.params")
    if signals["kind"] in {"ehlers_continuation_long", "ehlers_continuation_long_signal"}:
        _validate_ehlers_continuation_long_params(params, field_prefix="signals.params")
    if signals["kind"] == "ehlers_semiscalp_long":
        _validate_ehlers_semiscalp_long_params(params, field_prefix="signals.params")
    if signals["kind"] == "ehlers_decycler_continuation":
        _validate_ehlers_decycler_continuation_params(params, field_prefix="signals.params")
    if signals["kind"] in {"ehlers_continuation_short", "ehlers_continuation_short_signal"}:
        _validate_ehlers_continuation_short_params(params, field_prefix="signals.params")
    if signals["kind"] == "ema_rms_ppo_vwap":
        _validate_ema_rms_ppo_vwap_params(params, field_prefix="signals.params")
    if signals["kind"] == "vwap_rms_ema_cross_long":
        _validate_vwap_rms_ema_cross_long_params(params, field_prefix="signals.params")
    if signals["kind"] == "vwap_rms_ema_cross_long_fractal_filter":
        _validate_vwap_rms_ema_cross_long_fractal_filter_params(params, field_prefix="signals.params")
    if signals["kind"] == "vwap_rms_ema_cross_long_hmm_gate":
        _validate_vwap_rms_ema_cross_long_hmm_gate_params(params, field_prefix="signals.params")


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
    portfolio_guard = risk.get("portfolio_guard", {})
    if not isinstance(portfolio_guard, dict):
        raise ConfigValidationError("risk.portfolio_guard must be a mapping.")
    if "enabled" in portfolio_guard and not isinstance(portfolio_guard.get("enabled"), bool):
        raise ConfigValidationError("risk.portfolio_guard.enabled must be boolean.")
    for key in ("weekly_return_target", "max_daily_loss", "weekly_drawdown", "max_total_loss"):
        value = portfolio_guard.get(key)
        if value is None:
            continue
        numeric = _finite_number(value, field=f"risk.portfolio_guard.{key}")
        if numeric <= 0:
            raise ConfigValidationError(f"risk.portfolio_guard.{key} must be > 0 when provided.")
    if "cooloff_bars" in portfolio_guard:
        _non_negative_int(portfolio_guard.get("cooloff_bars", 0), field="risk.portfolio_guard.cooloff_bars")
    if "rearm_on_new_period" in portfolio_guard and not isinstance(
        portfolio_guard.get("rearm_on_new_period"),
        bool,
    ):
        raise ConfigValidationError("risk.portfolio_guard.rearm_on_new_period must be boolean.")
    for key in ("daily_soft_stop", "daily_hard_stop", "weekly_profit_lock"):
        value = portfolio_guard.get(key)
        if value is None:
            continue
        numeric = _finite_number(value, field=f"risk.portfolio_guard.{key}")
        if numeric <= 0:
            raise ConfigValidationError(f"risk.portfolio_guard.{key} must be > 0 when provided.")
    for key in ("after_target_risk_multiplier", "daily_soft_stop_risk_multiplier"):
        value = portfolio_guard.get(key)
        if value is None:
            continue
        numeric = _finite_number(value, field=f"risk.portfolio_guard.{key}")
        if not 0.0 <= numeric <= 1.0:
            raise ConfigValidationError(f"risk.portfolio_guard.{key} must be in [0,1].")
    after_target_mode = str(portfolio_guard.get("after_target_mode", "reduce_risk"))
    if after_target_mode not in {"reduce_risk", "flatten"}:
        raise ConfigValidationError("risk.portfolio_guard.after_target_mode must be reduce_risk or flatten.")
    weekly_anchor = portfolio_guard.get("weekly_anchor", "W-FRI")
    if not isinstance(weekly_anchor, str) or not weekly_anchor.strip():
        raise ConfigValidationError("risk.portfolio_guard.weekly_anchor must be a non-empty string.")
    if "max_open_trades" in portfolio_guard and portfolio_guard.get("max_open_trades") is not None:
        _positive_int(portfolio_guard["max_open_trades"], field="risk.portfolio_guard.max_open_trades")
    group_max_open = portfolio_guard.get("group_max_open_trades", {})
    if not isinstance(group_max_open, dict):
        raise ConfigValidationError("risk.portfolio_guard.group_max_open_trades must be a mapping.")
    for group, value in dict(group_max_open or {}).items():
        if not isinstance(group, str) or not group.strip():
            raise ConfigValidationError("risk.portfolio_guard.group_max_open_trades keys must be non-empty strings.")
        _positive_int(value, field=f"risk.portfolio_guard.group_max_open_trades.{group}")
    for key in ("kill_switch_max_drawdown", "max_drawdown"):
        value = portfolio_guard.get(key)
        if value is None:
            continue
        numeric = _finite_number(value, field=f"risk.portfolio_guard.{key}")
        if numeric <= 0:
            raise ConfigValidationError(f"risk.portfolio_guard.{key} must be > 0 when provided.")

    sizing = risk.get("sizing", {}) or {}
    if sizing:
        if not isinstance(sizing, dict):
            raise ConfigValidationError("risk.sizing must be a mapping when provided.")
        kind = str(sizing.get("kind", "none"))
        if kind not in {"none", "ftmo_risk_per_trade"}:
            raise ConfigValidationError("risk.sizing.kind must be one of: none, ftmo_risk_per_trade.")
        if kind == "ftmo_risk_per_trade":
            for key in ("vol_col", "confidence_col", "output_col"):
                if key in sizing and sizing[key] is not None and not isinstance(sizing[key], str):
                    raise ConfigValidationError(f"risk.sizing.{key} must be a string or null.")
            confidence_mode = str(sizing.get("confidence_mode", "directional_class1"))
            if confidence_mode not in {"directional_class1", "meta_success"}:
                raise ConfigValidationError(
                    "risk.sizing.confidence_mode must be one of: directional_class1, meta_success."
                )
            if not isinstance(sizing.get("vol_col"), str) or not sizing.get("vol_col", "").strip():
                raise ConfigValidationError("risk.sizing.vol_col is required for ftmo_risk_per_trade.")
            for key, default in (
                ("risk_per_trade", 0.0025),
                ("stop_mult", 1.0),
                ("max_leverage", 3.0),
                ("min_leverage", 0.0),
                ("min_abs_signal", 0.0),
                ("confidence_power", 1.0),
            ):
                value = _finite_number(sizing.get(key, default), field=f"risk.sizing.{key}")
                if key in {"risk_per_trade", "stop_mult", "confidence_power"} and value <= 0:
                    raise ConfigValidationError(f"risk.sizing.{key} must be > 0.")
                if key in {"max_leverage", "min_leverage", "min_abs_signal"} and value < 0:
                    raise ConfigValidationError(f"risk.sizing.{key} must be >= 0.")
            if (
                _finite_number(sizing.get("min_leverage", 0.0), field="risk.sizing.min_leverage")
                > _finite_number(sizing.get("max_leverage", 3.0), field="risk.sizing.max_leverage")
            ):
                raise ConfigValidationError("risk.sizing.min_leverage must be <= risk.sizing.max_leverage.")
            target_vol_sizing = sizing.get("target_vol")
            if target_vol_sizing is not None and _finite_number(target_vol_sizing, field="risk.sizing.target_vol") <= 0:
                raise ConfigValidationError("risk.sizing.target_vol must be > 0 or null.")
            confidence_floor = sizing.get("confidence_floor")
            if confidence_floor is not None:
                floor = _finite_number(confidence_floor, field="risk.sizing.confidence_floor")
                if not 0.0 <= floor < 1.0:
                    raise ConfigValidationError("risk.sizing.confidence_floor must be in [0,1).")

    drawdown_sizing = risk.get("drawdown_sizing", {}) or {}
    if drawdown_sizing:
        if not isinstance(drawdown_sizing, dict):
            raise ConfigValidationError("risk.drawdown_sizing must be a mapping when provided.")
        if "enabled" in drawdown_sizing and not isinstance(drawdown_sizing.get("enabled"), bool):
            raise ConfigValidationError("risk.drawdown_sizing.enabled must be boolean.")
        levels = drawdown_sizing.get("levels", []) or []
        if levels and not isinstance(levels, list):
            raise ConfigValidationError("risk.drawdown_sizing.levels must be a list.")
        last_dd = -1.0
        for idx, raw_level in enumerate(levels):
            if not isinstance(raw_level, dict):
                raise ConfigValidationError(f"risk.drawdown_sizing.levels[{idx}] must be a mapping.")
            max_dd = _finite_number(raw_level.get("max_dd"), field=f"risk.drawdown_sizing.levels[{idx}].max_dd")
            multiplier = _finite_number(
                raw_level.get("multiplier"),
                field=f"risk.drawdown_sizing.levels[{idx}].multiplier",
            )
            if max_dd <= 0:
                raise ConfigValidationError(f"risk.drawdown_sizing.levels[{idx}].max_dd must be > 0.")
            if max_dd <= last_dd:
                raise ConfigValidationError("risk.drawdown_sizing.levels must be sorted by increasing max_dd.")
            if not 0.0 <= multiplier <= 1.0:
                raise ConfigValidationError(
                    f"risk.drawdown_sizing.levels[{idx}].multiplier must be in [0,1]."
                )
            last_dd = max_dd


def validate_backtest_block(backtest: dict[str, Any]) -> None:
    for key in ("returns_col", "signal_col"):
        if key not in backtest or not isinstance(backtest[key], str):
            raise ConfigValidationError(f"backtest.{key} (str) is required.")
    engine = str(backtest.get("engine", "vectorized"))
    if engine not in {"vectorized", "manual_barrier", "portfolio_barrier"}:
        raise ConfigValidationError("backtest.engine must be 'vectorized', 'manual_barrier', or 'portfolio_barrier'.")
    stop_mode = str(backtest.get("stop_mode", "fixed_return"))
    if stop_mode not in {"fixed_return", "volatility_stop"}:
        raise ConfigValidationError("backtest.stop_mode must be 'fixed_return' or 'volatility_stop'.")
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
    if engine == "manual_barrier":
        if subset != "full":
            raise ConfigValidationError("backtest.engine='manual_barrier' requires backtest.subset='full'.")
        if "allow_short" in backtest and not isinstance(backtest.get("allow_short"), bool):
            raise ConfigValidationError("backtest.allow_short must be boolean.")
        for key in ("open_col", "high_col", "low_col", "close_col", "vol_col"):
            if key in backtest and not isinstance(backtest[key], str):
                if key != "vol_col" or backtest[key] is not None:
                    raise ConfigValidationError(f"backtest.{key} must be a string or null.")
        if stop_mode == "volatility_stop" and not backtest.get("vol_col"):
            raise ConfigValidationError("backtest.stop_mode='volatility_stop' requires backtest.vol_col.")
        for key in ("take_profit_r", "stop_loss_r", "risk_per_trade"):
            value = _finite_number(backtest.get(key), field=f"backtest.{key}")
            if value <= 0.0:
                raise ConfigValidationError(f"backtest.{key} must be > 0.")
        max_holding_bars = backtest.get("max_holding_bars", 16)
        if max_holding_bars is not None:
            _positive_int(max_holding_bars, field="backtest.max_holding_bars")
        dynamic_exits = backtest.get("dynamic_exits", {}) or {}
        _validate_dynamic_exits_block(dynamic_exits)
        partial_exits = backtest.get("partial_exits", {}) or {}
        _validate_partial_exits_block(partial_exits)
        atr_trailing_enabled = bool(dict(dynamic_exits).get("enabled", False)) and bool(
            dict(dict(dynamic_exits).get("atr_trailing", {}) or {}).get("enabled", False)
        )
        if atr_trailing_enabled and not backtest.get("vol_col"):
            raise ConfigValidationError("backtest.dynamic_exits.atr_trailing requires backtest.vol_col.")
    if engine == "portfolio_barrier":
        if "allow_short" in backtest and not isinstance(backtest.get("allow_short"), bool):
            raise ConfigValidationError("backtest.allow_short must be boolean.")
        for key in ("open_col", "high_col", "low_col", "close_col", "volatility_col"):
            if key in backtest and not isinstance(backtest[key], str):
                raise ConfigValidationError(f"backtest.{key} must be a string.")
            if key == "volatility_col" and not str(backtest.get(key, "")).strip():
                raise ConfigValidationError("backtest.volatility_col must be a non-empty string.")
        entry_price_mode = str(backtest.get("entry_price_mode", "next_open"))
        if entry_price_mode not in {"current_close", "next_open"}:
            raise ConfigValidationError("backtest.entry_price_mode must be 'current_close' or 'next_open'.")
        annualization_mode = str(backtest.get("annualization_mode", "fixed_periods"))
        if annualization_mode not in {"fixed_periods", "calendar_daily"}:
            raise ConfigValidationError(
                "backtest.annualization_mode must be 'fixed_periods' or 'calendar_daily'."
            )
        tie_break = str(backtest.get("tie_break", "closest_to_open"))
        if tie_break not in {"closest_to_open", "profit", "stop"}:
            raise ConfigValidationError("backtest.tie_break must be 'closest_to_open', 'profit', or 'stop'.")
        event_time_remap_policy = str(backtest.get("event_time_remap_policy", "next_aligned"))
        if event_time_remap_policy not in {"next_aligned", "skip"}:
            raise ConfigValidationError(
                "backtest.event_time_remap_policy must be 'next_aligned' or 'skip'."
            )
        if backtest.get("max_cost_r") is not None:
            max_cost_r = _finite_number(backtest.get("max_cost_r"), field="backtest.max_cost_r")
            if max_cost_r <= 0.0:
                raise ConfigValidationError("backtest.max_cost_r must be > 0.")
        for key in ("profit_barrier_r", "stop_barrier_r"):
            value = _finite_number(backtest.get(key), field=f"backtest.{key}")
            if value <= 0.0:
                raise ConfigValidationError(f"backtest.{key} must be > 0.")
        if backtest.get("vertical_barrier_bars") is not None:
            _positive_int(backtest.get("vertical_barrier_bars"), field="backtest.vertical_barrier_bars")
        asset_params = backtest.get("asset_params", {})
        if not isinstance(asset_params, dict):
            raise ConfigValidationError("backtest.asset_params must be a mapping when provided.")
        for asset, params in dict(asset_params or {}).items():
            if not isinstance(asset, str) or not asset.strip():
                raise ConfigValidationError("backtest.asset_params keys must be non-empty strings.")
            if not isinstance(params, dict):
                raise ConfigValidationError("backtest.asset_params values must be mappings.")
            for key in ("volatility_col", "vol_col"):
                if key in params and params[key] is not None and not isinstance(params[key], str):
                    raise ConfigValidationError(f"backtest.asset_params.{asset}.{key} must be a string or null.")
            for key in ("profit_barrier_r", "stop_barrier_r", "take_profit_r", "stop_loss_r", "risk_per_trade"):
                if key not in params or params[key] is None:
                    continue
                value = _finite_number(params[key], field=f"backtest.asset_params.{asset}.{key}")
                if value <= 0.0:
                    raise ConfigValidationError(f"backtest.asset_params.{asset}.{key} must be > 0.")
            if params.get("max_cost_r") is not None:
                value = _finite_number(params["max_cost_r"], field=f"backtest.asset_params.{asset}.max_cost_r")
                if value <= 0.0:
                    raise ConfigValidationError(f"backtest.asset_params.{asset}.max_cost_r must be > 0.")
            if params.get("vertical_barrier_bars") is not None:
                _positive_int(
                    params.get("vertical_barrier_bars"),
                    field=f"backtest.asset_params.{asset}.vertical_barrier_bars",
                )
        if int(backtest.get("min_holding_bars", 0) or 0) != 0:
            raise ConfigValidationError(
                "backtest.engine='portfolio_barrier' uses vertical_barrier_bars and requires min_holding_bars=0."
            )
        _validate_portfolio_barrier_dynamic_exit(backtest.get("dynamic_exit", {}) or {})
        _validate_correlation_guard(backtest.get("correlation_guard", {}) or {})


def _validate_portfolio_barrier_dynamic_exit(dynamic_exit: Any) -> None:
    if dynamic_exit in ({}, None):
        return
    if not isinstance(dynamic_exit, dict):
        raise ConfigValidationError("backtest.dynamic_exit must be a mapping when provided.")
    if "enabled" in dynamic_exit and not isinstance(dynamic_exit.get("enabled"), bool):
        raise ConfigValidationError("backtest.dynamic_exit.enabled must be boolean.")
    if not bool(dynamic_exit.get("enabled", False)):
        return
    if dynamic_exit.get("execution", "next_open") != "next_open":
        raise ConfigValidationError("backtest.dynamic_exit.execution currently supports only 'next_open'.")
    for key in ("long_exit_col", "short_exit_col"):
        value = dynamic_exit.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ConfigValidationError(f"backtest.dynamic_exit.{key} must be a non-empty string.")
    modules = dynamic_exit.get("module_exit_columns", {}) or {}
    if not isinstance(modules, dict):
        raise ConfigValidationError("backtest.dynamic_exit.module_exit_columns must be a mapping.")
    for module, values in modules.items():
        if not isinstance(module, str) or not module.strip() or not isinstance(values, dict):
            raise ConfigValidationError("backtest.dynamic_exit.module_exit_columns must map non-empty names to mappings.")
    legacy_reason = dynamic_exit.get("reason_col")
    side_reasons = (dynamic_exit.get("long_reason_col"), dynamic_exit.get("short_reason_col"))
    if not (
        isinstance(legacy_reason, str)
        and legacy_reason.strip()
    ) and not all(isinstance(value, str) and value.strip() for value in side_reasons):
        raise ConfigValidationError(
            "backtest.dynamic_exit requires reason_col or both long_reason_col and short_reason_col."
        )
    for key in ("reason_col", "long_reason_col", "short_reason_col"):
        if key in dynamic_exit and (
            not isinstance(dynamic_exit[key], str) or not dynamic_exit[key].strip()
        ):
            raise ConfigValidationError(f"backtest.dynamic_exit.{key} must be a non-empty string.")
    for module, values in modules.items():
        for key in ("long_exit_col", "short_exit_col", "reason_col", "long_reason_col", "short_reason_col"):
            if key in values and (not isinstance(values[key], str) or not values[key].strip()):
                raise ConfigValidationError(
                    f"backtest.dynamic_exit.module_exit_columns.{module}.{key} must be a non-empty string."
                )


def _validate_correlation_guard(correlation_guard: Any) -> None:
    if correlation_guard in ({}, None):
        return
    if not isinstance(correlation_guard, dict):
        raise ConfigValidationError("backtest.correlation_guard must be a mapping when provided.")
    if "enabled" in correlation_guard and not isinstance(correlation_guard.get("enabled"), bool):
        raise ConfigValidationError("backtest.correlation_guard.enabled must be boolean.")
    if not bool(correlation_guard.get("enabled", False)):
        return
    returns_col = correlation_guard.get("returns_col", "close_ret")
    if not isinstance(returns_col, str) or not returns_col.strip():
        raise ConfigValidationError("backtest.correlation_guard.returns_col must be a non-empty string.")
    window = _positive_int(correlation_guard.get("window_bars", 960), field="backtest.correlation_guard.window_bars")
    minimum = _positive_int(
        correlation_guard.get("minimum_observations", 240), field="backtest.correlation_guard.minimum_observations"
    )
    if minimum > window:
        raise ConfigValidationError("backtest.correlation_guard.minimum_observations must be <= window_bars.")
    threshold = _finite_number(
        correlation_guard.get("maximum_abs_correlation", 0.80),
        field="backtest.correlation_guard.maximum_abs_correlation",
    )
    if not 0.0 < threshold <= 1.0:
        raise ConfigValidationError("backtest.correlation_guard.maximum_abs_correlation must be in (0, 1].")
    if "same_direction_only" in correlation_guard and not isinstance(correlation_guard["same_direction_only"], bool):
        raise ConfigValidationError("backtest.correlation_guard.same_direction_only must be boolean.")
    if correlation_guard.get("action", "reject") != "reject":
        raise ConfigValidationError("backtest.correlation_guard.action currently supports only 'reject'.")


def _validate_dynamic_exits_block(dynamic_exits: Any) -> None:
    if dynamic_exits in ({}, None):
        return
    if not isinstance(dynamic_exits, dict):
        raise ConfigValidationError("backtest.dynamic_exits must be a mapping when provided.")
    if "enabled" in dynamic_exits and not isinstance(dynamic_exits.get("enabled"), bool):
        raise ConfigValidationError("backtest.dynamic_exits.enabled must be boolean.")
    enabled = bool(dynamic_exits.get("enabled", False))
    section_specs = {
        "signal_off_exit": {"enabled": bool, "min_bars_held": int, "exit_price": str},
        "breakeven": {"enabled": bool, "trigger_r": float, "lock_r": float},
        "profit_lock": {"enabled": bool, "trigger_r": float, "lock_r": float},
        "atr_trailing": {"enabled": bool, "activation_r": float, "distance_mult": float},
        "no_progress": {"enabled": bool, "bars": int, "min_favorable_r": float, "exit_price": str},
    }
    for section_name, spec in section_specs.items():
        raw_section = dynamic_exits.get(section_name, {}) or {}
        if not isinstance(raw_section, dict):
            raise ConfigValidationError(f"backtest.dynamic_exits.{section_name} must be a mapping.")
        if "enabled" in raw_section and not isinstance(raw_section.get("enabled"), bool):
            raise ConfigValidationError(f"backtest.dynamic_exits.{section_name}.enabled must be boolean.")
        if not enabled:
            continue
        for key, expected in spec.items():
            if key not in raw_section:
                continue
            field = f"backtest.dynamic_exits.{section_name}.{key}"
            value = raw_section.get(key)
            if expected is int:
                if key == "min_bars_held":
                    _non_negative_int(value, field=field)
                else:
                    _positive_int(value, field=field)
            elif expected is float:
                numeric = _finite_number(value, field=field)
                if key == "trigger_r" and numeric <= 0.0:
                    raise ConfigValidationError(f"{field} must be > 0.")
                if key in {"lock_r", "min_favorable_r", "activation_r"} and numeric < 0.0:
                    raise ConfigValidationError(f"{field} must be >= 0.")
                if key == "distance_mult" and numeric <= 0.0:
                    raise ConfigValidationError(f"{field} must be > 0.")
            elif expected is str:
                if value not in {"close", "next_open"}:
                    raise ConfigValidationError(f"{field} must be 'close' or 'next_open'.")


def _validate_partial_exits_block(partial_exits: Any) -> None:
    if partial_exits in ({}, None):
        return
    if not isinstance(partial_exits, dict):
        raise ConfigValidationError("backtest.partial_exits must be a mapping when provided.")
    if "enabled" in partial_exits and not isinstance(partial_exits.get("enabled"), bool):
        raise ConfigValidationError("backtest.partial_exits.enabled must be boolean.")
    enabled = bool(partial_exits.get("enabled", False))
    raw_rules = partial_exits.get("rules", []) or []
    if not enabled:
        return
    if not isinstance(raw_rules, list):
        raise ConfigValidationError("backtest.partial_exits.rules must be a list.")
    total_fraction = 0.0
    for idx, raw_rule in enumerate(raw_rules):
        field = f"backtest.partial_exits.rules[{idx}]"
        if not isinstance(raw_rule, dict):
            raise ConfigValidationError(f"{field} must be a mapping.")
        trigger_r = _finite_number(raw_rule.get("trigger_r"), field=f"{field}.trigger_r")
        if trigger_r <= 0.0:
            raise ConfigValidationError(f"{field}.trigger_r must be > 0.")
        fraction = _finite_number(raw_rule.get("fraction"), field=f"{field}.fraction")
        if not 0.0 < fraction < 1.0:
            raise ConfigValidationError(f"{field}.fraction must be in (0, 1).")
        total_fraction += fraction
        exit_price = raw_rule.get("exit_price", "trigger")
        if exit_price not in {"trigger", "close", "next_open"}:
            raise ConfigValidationError(f"{field}.exit_price must be one of: trigger, close, next_open.")
    if total_fraction >= 1.0:
        raise ConfigValidationError("backtest.partial_exits.rules fractions must sum to < 1.0.")


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
    selection_cfg = portfolio.get("selection", {})
    if not isinstance(selection_cfg, dict):
        raise ConfigValidationError("portfolio.selection must be a mapping.")
    selection_cfg = dict(selection_cfg or {})
    if not isinstance(selection_cfg.get("enabled", False), bool):
        raise ConfigValidationError("portfolio.selection.enabled must be boolean.")
    if bool(selection_cfg.get("enabled", False)):
        top_k = selection_cfg.get("top_k", 1)
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
            raise ConfigValidationError("portfolio.selection.top_k must be a positive integer.")
        if _finite_number(
            selection_cfg.get("min_expected_net_return", 0.0),
            field="portfolio.selection.min_expected_net_return",
        ) < 0:
            raise ConfigValidationError("portfolio.selection.min_expected_net_return must be >= 0.")
        if not isinstance(selection_cfg.get("rank_by_abs", True), bool):
            raise ConfigValidationError("portfolio.selection.rank_by_abs must be boolean.")
        weighting = str(selection_cfg.get("weighting", "score"))
        if weighting not in {"equal", "score"}:
            raise ConfigValidationError("portfolio.selection.weighting must be 'equal' or 'score'.")
        rebalance_every_n_bars = selection_cfg.get("rebalance_every_n_bars", 1)
        if (
            isinstance(rebalance_every_n_bars, bool)
            or not isinstance(rebalance_every_n_bars, int)
            or rebalance_every_n_bars <= 0
        ):
            raise ConfigValidationError("portfolio.selection.rebalance_every_n_bars must be a positive integer.")
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
    enforce_target_net_exposure = constraints_cfg.get("enforce_target_net_exposure", True)
    if not isinstance(enforce_target_net_exposure, bool):
        raise ConfigValidationError("portfolio.constraints.enforce_target_net_exposure must be boolean.")
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
    if min_weight > max_weight:
        raise ConfigValidationError("min_weight must be <= max_weight.")
    if max_gross_leverage <= 0:
        raise ConfigValidationError("max_gross_leverage must be > 0.")
    if turnover_limit is not None and turnover_limit < 0:
        raise ConfigValidationError("turnover_limit must be >= 0 when provided.")
    for group, cap in group_caps.items():
        if cap <= 0:
            raise ConfigValidationError(f"group_max_exposure[{group!r}] must be > 0.")
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


def validate_diagnostics_block(diagnostics: dict[str, Any]) -> None:
    if not isinstance(diagnostics, dict):
        raise ConfigValidationError("diagnostics must be a mapping.")
    if not isinstance(diagnostics.get("enabled", False), bool):
        raise ConfigValidationError("diagnostics.enabled must be boolean.")
    model = diagnostics.get("model", {})
    if not isinstance(model, dict):
        raise ConfigValidationError("diagnostics.model must be a mapping.")
    if not isinstance(model.get("enabled", False), bool):
        raise ConfigValidationError("diagnostics.model.enabled must be boolean.")
    shap_cfg = model.get("shap", {})
    if not isinstance(shap_cfg, dict):
        raise ConfigValidationError("diagnostics.model.shap must be a mapping.")
    if not isinstance(shap_cfg.get("enabled", False), bool):
        raise ConfigValidationError("diagnostics.model.shap.enabled must be boolean.")
    shap_defaults = {
        "max_rows": 200,
        "top_n_features": 12,
        "per_prediction_top_k": 5,
        "per_prediction_row_limit": 3,
    }
    for key, default in shap_defaults.items():
        value = shap_cfg.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ConfigValidationError(f"diagnostics.model.shap.{key} must be an integer > 0.")
    random_state = shap_cfg.get("random_state", 42)
    if isinstance(random_state, bool) or not isinstance(random_state, int) or random_state < 0:
        raise ConfigValidationError("diagnostics.model.shap.random_state must be an integer >= 0.")

    forecast = diagnostics.get("forecast", {})
    if not isinstance(forecast, dict):
        raise ConfigValidationError("diagnostics.forecast must be a mapping.")
    quantiles = forecast.get("quantiles", 10)
    if isinstance(quantiles, bool) or not isinstance(quantiles, int) or quantiles < 2:
        raise ConfigValidationError("diagnostics.forecast.quantiles must be an integer >= 2.")
    lags = forecast.get("autocorrelation_lags", [])
    if not isinstance(lags, list) or any(isinstance(lag, bool) or not isinstance(lag, int) or lag <= 0 for lag in lags):
        raise ConfigValidationError("diagnostics.forecast.autocorrelation_lags must be a list of positive integers.")
    volatility_col = forecast.get("volatility_col", "atr_pct_rank_100")
    if volatility_col is not None and (not isinstance(volatility_col, str) or not volatility_col.strip()):
        raise ConfigValidationError("diagnostics.forecast.volatility_col must be null or a non-empty string.")
    robustness = diagnostics.get("robustness", {})
    if not isinstance(robustness, dict):
        raise ConfigValidationError("diagnostics.robustness must be a mapping.")
    if not isinstance(robustness.get("enabled", False), bool):
        raise ConfigValidationError("diagnostics.robustness.enabled must be boolean.")
    if not isinstance(robustness.get("strict_no_remap", False), bool):
        raise ConfigValidationError("diagnostics.robustness.strict_no_remap must be boolean.")
    for key in (
        "cost_multipliers",
        "entry_delay_bars",
        "combined_cost_multipliers",
        "gross_cap_values",
        "cost_filter_max_cost_r_values",
    ):
        value = robustness.get(key, [])
        if value is None:
            continue
        if not isinstance(value, list):
            raise ConfigValidationError(f"diagnostics.robustness.{key} must be a list.")
        for idx, item in enumerate(value):
            if key == "entry_delay_bars":
                _positive_int(item, field=f"diagnostics.robustness.{key}[{idx}]")
            else:
                numeric = _finite_number(item, field=f"diagnostics.robustness.{key}[{idx}]")
                if key in {"gross_cap_values", "cost_filter_max_cost_r_values"}:
                    if numeric <= 0.0:
                        raise ConfigValidationError(f"diagnostics.robustness.{key}[{idx}] must be > 0.")
                elif numeric < 0.0:
                    raise ConfigValidationError(f"diagnostics.robustness.{key}[{idx}] must be >= 0.")
    frequency = robustness.get("walk_forward_frequency", "YE")
    if frequency is not None and (not isinstance(frequency, str) or not frequency.strip()):
        raise ConfigValidationError("diagnostics.robustness.walk_forward_frequency must be a non-empty string.")
    if _finite_number(
        robustness.get("gap_loss_per_exposure", 0.0),
        field="diagnostics.robustness.gap_loss_per_exposure",
    ) < 0:
        raise ConfigValidationError("diagnostics.robustness.gap_loss_per_exposure must be >= 0.")
    if _finite_number(
        robustness.get("max_gap_multiple", 3.0),
        field="diagnostics.robustness.max_gap_multiple",
    ) <= 1.0:
        raise ConfigValidationError("diagnostics.robustness.max_gap_multiple must be > 1.")

    baselines = diagnostics.get("baselines", {})
    if not isinstance(baselines, dict):
        raise ConfigValidationError("diagnostics.baselines must be a mapping.")
    if not isinstance(baselines.get("enabled", False), bool):
        raise ConfigValidationError("diagnostics.baselines.enabled must be boolean.")
    _non_negative_int(baselines.get("random_seed", 7), field="diagnostics.baselines.random_seed")

    threshold_grid = diagnostics.get("threshold_grid", {})
    if not isinstance(threshold_grid, dict):
        raise ConfigValidationError("diagnostics.threshold_grid must be a mapping.")
    if not isinstance(threshold_grid.get("enabled", False), bool):
        raise ConfigValidationError("diagnostics.threshold_grid.enabled must be boolean.")
    forecast_col = threshold_grid.get("forecast_col", "pred_ret")
    if forecast_col is not None and (not isinstance(forecast_col, str) or not forecast_col.strip()):
        raise ConfigValidationError("diagnostics.threshold_grid.forecast_col must be null or a non-empty string.")
    symmetric = threshold_grid.get("symmetric_thresholds", [])
    if not isinstance(symmetric, list):
        raise ConfigValidationError("diagnostics.threshold_grid.symmetric_thresholds must be a list.")
    for idx, item in enumerate(symmetric):
        value = _finite_number(item, field=f"diagnostics.threshold_grid.symmetric_thresholds[{idx}]")
        if value <= 0.0:
            raise ConfigValidationError("diagnostics.threshold_grid.symmetric_thresholds values must be > 0.")
    asymmetric = threshold_grid.get("asymmetric_thresholds", [])
    if not isinstance(asymmetric, list):
        raise ConfigValidationError("diagnostics.threshold_grid.asymmetric_thresholds must be a list.")
    for idx, raw_pair in enumerate(asymmetric):
        if not isinstance(raw_pair, dict):
            raise ConfigValidationError(f"diagnostics.threshold_grid.asymmetric_thresholds[{idx}] must be a mapping.")
        upper = _finite_number(raw_pair.get("upper"), field=f"diagnostics.threshold_grid.asymmetric_thresholds[{idx}].upper")
        lower = _finite_number(raw_pair.get("lower"), field=f"diagnostics.threshold_grid.asymmetric_thresholds[{idx}].lower")
        if not lower < upper:
            raise ConfigValidationError(
                f"diagnostics.threshold_grid.asymmetric_thresholds[{idx}] must satisfy lower < upper."
            )
        if "name" in raw_pair and raw_pair["name"] is not None and not isinstance(raw_pair["name"], str):
            raise ConfigValidationError(
                f"diagnostics.threshold_grid.asymmetric_thresholds[{idx}].name must be a string."
            )

    regime_performance = diagnostics.get("regime_performance", {})
    if not isinstance(regime_performance, dict):
        raise ConfigValidationError("diagnostics.regime_performance must be a mapping.")
    if not isinstance(regime_performance.get("enabled", False), bool):
        raise ConfigValidationError("diagnostics.regime_performance.enabled must be boolean.")

    trade_path = diagnostics.get("trade_path", {})
    if not isinstance(trade_path, dict):
        raise ConfigValidationError("diagnostics.trade_path must be a mapping.")
    for key in (
        "enabled",
        "include_executed_trades",
        "include_target_trades",
        "include_probability_quality",
        "include_counterfactuals",
        "write_trade_paths",
        "write_probability_quality",
    ):
        if not isinstance(trade_path.get(key, False), bool):
            raise ConfigValidationError(f"diagnostics.trade_path.{key} must be boolean.")
    thresholds = trade_path.get("thresholds_r", [0.5, 1.0, 1.5, 2.0])
    if not isinstance(thresholds, list) or not thresholds:
        raise ConfigValidationError("diagnostics.trade_path.thresholds_r must be a non-empty list.")
    for idx, item in enumerate(thresholds):
        numeric = _finite_number(item, field=f"diagnostics.trade_path.thresholds_r[{idx}]")
        if numeric <= 0.0:
            raise ConfigValidationError("diagnostics.trade_path.thresholds_r values must be > 0.")
    buckets = trade_path.get("bars_held_buckets", [1, 2, 4, 8, 16])
    if not isinstance(buckets, list) or not buckets:
        raise ConfigValidationError("diagnostics.trade_path.bars_held_buckets must be a non-empty list.")
    previous = 0
    for idx, item in enumerate(buckets):
        value = _positive_int(item, field=f"diagnostics.trade_path.bars_held_buckets[{idx}]")
        if value <= previous:
            raise ConfigValidationError("diagnostics.trade_path.bars_held_buckets must be strictly increasing.")
        previous = value
    plots = trade_path.get("plots", {})
    if not isinstance(plots, dict):
        raise ConfigValidationError("diagnostics.trade_path.plots must be a mapping.")
    if not isinstance(plots.get("enabled", True), bool):
        raise ConfigValidationError("diagnostics.trade_path.plots.enabled must be boolean.")
    for key in ("max_trades", "max_path_points"):
        _positive_int(plots.get(key, 500 if key == "max_trades" else 200000), field=f"diagnostics.trade_path.plots.{key}")


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
    hysteresis_cfg = execution.get("hysteresis", {})
    if not isinstance(hysteresis_cfg, dict):
        raise ConfigValidationError("execution.hysteresis must be a mapping.")
    hysteresis_cfg = dict(hysteresis_cfg or {})
    if not isinstance(hysteresis_cfg.get("enabled", False), bool):
        raise ConfigValidationError("execution.hysteresis.enabled must be boolean.")
    entry_threshold = _finite_number(
        hysteresis_cfg.get("entry_threshold", 0.0),
        field="execution.hysteresis.entry_threshold",
    )
    exit_threshold = _finite_number(
        hysteresis_cfg.get("exit_threshold", 0.0),
        field="execution.hysteresis.exit_threshold",
    )
    if entry_threshold < 0 or exit_threshold < 0:
        raise ConfigValidationError("execution.hysteresis thresholds must be >= 0.")
    if bool(hysteresis_cfg.get("enabled", False)) and exit_threshold > entry_threshold:
        raise ConfigValidationError(
            "execution.hysteresis.exit_threshold must be <= entry_threshold when hysteresis is enabled."
        )
    min_holding_bars = hysteresis_cfg.get("min_holding_bars", 0)
    if isinstance(min_holding_bars, bool) or not isinstance(min_holding_bars, int) or min_holding_bars < 0:
        raise ConfigValidationError("execution.hysteresis.min_holding_bars must be an integer >= 0.")
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
    if "save_model" in logging_cfg and not isinstance(logging_cfg["save_model"], bool):
        raise ConfigValidationError("logging.save_model must be boolean.")
    if "install_model" in logging_cfg and not isinstance(logging_cfg["install_model"], bool):
        raise ConfigValidationError("logging.install_model must be boolean.")
    for key in ("model_name", "model_artifact_name", "model_filename", "model_install_dir", "installed_model_dir", "model_registry_dir"):
        if key in logging_cfg and logging_cfg[key] is not None:
            value = logging_cfg[key]
            if not isinstance(value, str) or not value.strip():
                raise ConfigValidationError(f"logging.{key} must be a non-empty string when provided.")
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
    execution_source_audit = logging_cfg.get("execution_source_audit", {})
    if not isinstance(execution_source_audit, dict):
        raise ConfigValidationError("logging.execution_source_audit must be a mapping.")
    if "enabled" in execution_source_audit and not isinstance(execution_source_audit.get("enabled"), bool):
        raise ConfigValidationError("logging.execution_source_audit.enabled must be boolean.")


def _barrier_parity_equal(left: Any, right: Any) -> bool:
    if not isinstance(left, bool) and not isinstance(right, bool):
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)
    return str(left) == str(right)


def _require_barrier_parity(left_path: str, left_value: Any, right_path: str, right_value: Any) -> None:
    if not _barrier_parity_equal(left_value, right_value):
        raise ConfigValidationError(
            "portfolio_barrier parity mismatch: "
            f"{right_path}={right_value!r} must match {left_path}={left_value!r}."
        )


def _validate_portfolio_barrier_parity(cfg: dict[str, Any]) -> None:
    model = dict(cfg.get("model", {}) or {})
    target = dict(model.get("target", {}) or {})
    if str(target.get("kind", "none")) != "directional_triple_barrier":
        return

    backtest = dict(cfg.get("backtest", {}) or {})
    signals = dict(cfg.get("signals", {}) or {})
    signal_params = dict(signals.get("params", {}) or {})

    target_profit = target.get("profit_barrier_r", target.get("upper_mult", 1.4))
    target_stop = target.get("stop_barrier_r", target.get("lower_mult", 1.0))
    target_vertical = target.get("vertical_barrier_bars", target.get("max_holding", target.get("horizon", 4)))

    comparisons = [
        ("model.target.profit_barrier_r", target_profit, "backtest.profit_barrier_r", backtest.get("profit_barrier_r", 1.4)),
        ("model.target.stop_barrier_r", target_stop, "backtest.stop_barrier_r", backtest.get("stop_barrier_r", 1.0)),
        (
            "model.target.vertical_barrier_bars",
            target_vertical,
            "backtest.vertical_barrier_bars",
            backtest.get("vertical_barrier_bars", 4),
        ),
        (
            "model.target.entry_price_mode",
            target.get("entry_price_mode", "current_close"),
            "backtest.entry_price_mode",
            backtest.get("entry_price_mode", "next_open"),
        ),
        (
            "model.target.volatility_col",
            target.get("volatility_col", "atr_14"),
            "backtest.volatility_col",
            backtest.get("volatility_col", "atr_14"),
        ),
        ("model.target.price_col", target.get("price_col", "close"), "backtest.close_col", backtest.get("close_col", "close")),
        ("model.target.open_col", target.get("open_col", "open"), "backtest.open_col", backtest.get("open_col", "open")),
        ("model.target.high_col", target.get("high_col", "high"), "backtest.high_col", backtest.get("high_col", "high")),
        ("model.target.low_col", target.get("low_col", "low"), "backtest.low_col", backtest.get("low_col", "low")),
        (
            "model.target.tie_break",
            target.get("tie_break", "closest_to_open"),
            "backtest.tie_break",
            backtest.get("tie_break", "closest_to_open"),
        ),
    ]
    for left_path, left_value, right_path, right_value in comparisons:
        _require_barrier_parity(left_path, left_value, right_path, right_value)

    if str(signals.get("kind", "none")) == "meta_probability_side":
        _require_barrier_parity(
            "model.target.profit_barrier_r",
            target_profit,
            "signals.params.profit_barrier_r",
            signal_params.get("profit_barrier_r", 1.0),
        )
        _require_barrier_parity(
            "model.target.stop_barrier_r",
            target_stop,
            "signals.params.stop_barrier_r",
            signal_params.get("stop_barrier_r", 1.0),
        )


def _validate_session_time(value: Any, *, field: str, allow_24: bool = False) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}", value):
        raise ConfigValidationError(f"{field} must be a HH:MM string.")
    hour, minute = (int(part) for part in value.split(":"))
    if allow_24 and hour == 24 and minute == 0:
        return
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ConfigValidationError(f"{field} must be a valid HH:MM time.")


def _validate_panel_step_list(value: Any, *, field: str, supported: set[str]) -> list[dict[str, Any]]:
    if value in (None, []):
        return []
    if not isinstance(value, list):
        raise ConfigValidationError(f"{field} must be a list of steps.")
    steps: list[dict[str, Any]] = []
    for idx, step in enumerate(value):
        if not isinstance(step, dict) or not isinstance(step.get("step"), str) or not step["step"].strip():
            raise ConfigValidationError(f"{field}[{idx}].step must be a non-empty string.")
        if step["step"] not in supported:
            raise ConfigValidationError(f"Unknown {field} step: {step['step']}")
        if "enabled" in step and not isinstance(step["enabled"], bool):
            raise ConfigValidationError(f"{field}[{idx}].enabled must be boolean when provided.")
        if "params" in step and step["params"] is not None and not isinstance(step["params"], dict):
            raise ConfigValidationError(f"{field}[{idx}].params must be a mapping when provided.")
        steps.append(step)
    return steps


def _validate_cluster_definitions(clusters: Any, *, symbols: set[str], field: str) -> None:
    if not isinstance(clusters, dict) or not clusters:
        raise ConfigValidationError(f"{field} must be a non-empty mapping.")
    for cluster, spec in clusters.items():
        if not isinstance(cluster, str) or not cluster.strip() or not isinstance(spec, dict):
            raise ConfigValidationError(f"{field} must map non-empty cluster names to mappings.")
        members = spec.get("assets", [])
        if not isinstance(members, list) or not members or any(not isinstance(asset, str) or not asset.strip() for asset in members):
            raise ConfigValidationError(f"{field}.{cluster}.assets must be a non-empty list[str].")
        unknown = sorted(set(members) - symbols)
        if unknown:
            raise ConfigValidationError(f"{field}.{cluster}.assets contains assets absent from data.symbols: {unknown}")
        minimum = spec.get("minimum_active_assets")
        if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum <= 0:
            raise ConfigValidationError(f"{field}.{cluster}.minimum_active_assets must be a positive integer.")
        if minimum > len(members):
            raise ConfigValidationError(f"{field}.{cluster}.minimum_active_assets cannot exceed cluster size.")
        if "require_all_assets" in spec and not isinstance(spec["require_all_assets"], bool):
            raise ConfigValidationError(f"{field}.{cluster}.require_all_assets must be boolean.")


def validate_panel_features_block(panel_features: Any, *, symbols: set[str]) -> None:
    steps = _validate_panel_step_list(panel_features, field="panel_features", supported={"global_session_relay"})
    for step in steps:
        params = dict(step.get("params", {}) or {})
        if "clusters" in params:
            _validate_cluster_definitions(params["clusters"], symbols=symbols, field="panel_features[].params.clusters")
        if params.get("universe_mode", "fixed") not in {"fixed", "dynamic"}:
            raise ConfigValidationError("panel_features[].params.universe_mode must be 'fixed' or 'dynamic'.")
        for key in ("interval_minutes", "entry_window_bars"):
            if key in params:
                _positive_int(params[key], field=f"panel_features[].params.{key}")
        for key in ("cluster_context_max_age_bars", "relay_context_max_age_bars", "macro_context_max_age_bars"):
            if key in params and _finite_number(params[key], field=f"panel_features[].params.{key}") <= 0.0:
                raise ConfigValidationError(f"panel_features[].params.{key} must be > 0.")
        sessions = params.get("sessions", {}) or {}
        if not isinstance(sessions, dict):
            raise ConfigValidationError("panel_features[].params.sessions must be a mapping.")
        for asset, session in sessions.items():
            if asset not in symbols:
                raise ConfigValidationError("panel_features[].params.sessions assets must exist in data.symbols.")
            if not isinstance(session, dict):
                raise ConfigValidationError("panel_features[].params.sessions values must be mappings.")
            timezone = session.get("timezone")
            if not isinstance(timezone, str) or not timezone.strip():
                raise ConfigValidationError("panel_features[].params.sessions.*.timezone must be a non-empty string.")
            _validate_session_time(session.get("open"), field="panel_features[].params.sessions.*.open")
            _validate_session_time(session.get("close"), field="panel_features[].params.sessions.*.close", allow_24=True)


def validate_panel_signals_block(panel_signals: Any, *, symbols: set[str]) -> None:
    steps = _validate_panel_step_list(panel_signals, field="panel_signals", supported={"global_session_relay_laggard"})
    for step in steps:
        params = dict(step.get("params", {}) or {})
        if "clusters" in params:
            _validate_cluster_definitions(params["clusters"], symbols=symbols, field="panel_signals[].params.clusters")
        for key in ("impulse_col", "atr_col", "volatility_col", "signal_col"):
            if key in params and (not isinstance(params[key], str) or not params[key].strip()):
                raise ConfigValidationError(f"panel_signals[].params.{key} must be a non-empty string.")
        context_only = params.get("context_only_assets", ["ETHUSD", "EURUSD"])
        if not isinstance(context_only, (list, tuple)) or any(not isinstance(asset, str) or not asset.strip() for asset in context_only):
            raise ConfigValidationError("panel_signals[].params.context_only_assets must be a list[str].")
        unknown = sorted(set(context_only) - symbols)
        if unknown:
            raise ConfigValidationError(f"context-only assets must exist in data.symbols: {unknown}")
        if "clusters" in params:
            cluster_members = {
                str(asset)
                for spec in dict(params["clusters"] or {}).values()
                if isinstance(spec, dict)
                for asset in list(spec.get("assets", []) or [])
            }
            overlap = sorted(cluster_members & set(context_only))
            if overlap:
                raise ConfigValidationError(f"context-only assets cannot be configured as tradable cluster members: {overlap}")
        veto = params.get("macro_veto", {}) or {}
        if not isinstance(veto, dict) or ("enabled" in veto and not isinstance(veto["enabled"], bool)):
            raise ConfigValidationError("panel_signals[].params.macro_veto.enabled must be boolean.")
        if bool(veto.get("enabled", False)):
            missing = sorted({"ETHUSD", "XAUUSD", "BRENT"} - symbols)
            if missing:
                raise ConfigValidationError(f"macro veto requires assets in data.symbols: {missing}")
        enabled_modules = params.get("enabled_modules", {}) or {}
        if not isinstance(enabled_modules, dict) or any(not isinstance(value, bool) for value in enabled_modules.values()):
            raise ConfigValidationError("panel_signals[].params.enabled_modules must map names to booleans.")
        unknown_modules = sorted(set(enabled_modules) - GLOBAL_SESSION_RELAY_ENABLED_MODULES)
        if unknown_modules:
            raise ConfigValidationError(
                f"panel_signals[].params.enabled_modules has unsupported modules: {unknown_modules}."
            )


def validate_resolved_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """
    Validate all top-level blocks and normalize the runtime sub-config.
    """
    validate_data_block(cfg["data"])
    validate_features_block(cfg["features"])
    symbols = {str(symbol) for symbol in list(cfg["data"].get("symbols", []) or [])}
    validate_panel_features_block(cfg.get("panel_features", []), symbols=symbols)
    validate_model_stages_block(cfg.get("model_stages"))
    validate_model_block(cfg["model"])
    if cfg.get("target") not in (None, {}):
        target_kind = _flatten_target_cfg_for_validation(dict(cfg.get("target", {}) or {})).get("kind", "forward_return")
        if str(cfg["model"].get("kind", "none")) != "none" and target_kind not in _POST_MODEL_TARGET_KINDS:
            raise ConfigValidationError("Top-level target diagnostics require model.kind='none'.")
        if cfg["model"].get("target") not in (None, {}) and target_kind not in _POST_MODEL_TARGET_KINDS:
            raise ConfigValidationError("Specify either top-level target or model.target, not both.")
        validate_standalone_target_block(cfg["target"])
    validate_signals_block(cfg["signals"])
    validate_panel_signals_block(cfg.get("panel_signals", []), symbols=symbols)
    validate_risk_block(cfg["risk"])
    validate_backtest_block(cfg["backtest"])
    validate_portfolio_block(cfg["portfolio"])
    if (
        str(cfg["backtest"].get("engine", "vectorized")) == "portfolio_barrier"
        and bool(cfg["portfolio"].get("long_short", True))
        and not bool(cfg["backtest"].get("allow_short", False))
        and any(
            str(step.get("step", "")) == "global_session_relay_laggard"
            for step in list(cfg.get("panel_signals", []) or [])
            if isinstance(step, dict)
        )
    ):
        raise ConfigValidationError(
            "portfolio.long_short=true is incompatible with backtest.allow_short=false for "
            "global_session_relay_laggard, which can emit negative signals."
        )
    validate_monitoring_block(cfg["monitoring"])
    validate_diagnostics_block(cfg.get("diagnostics", {}))
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
    if str(cfg["backtest"].get("engine", "vectorized")) == "manual_barrier":
        if bool(cfg["portfolio"].get("enabled", False)):
            raise ConfigValidationError("backtest.engine='manual_barrier' currently supports single-asset runs only.")
        if cfg["risk"].get("target_vol") is not None:
            raise ConfigValidationError("backtest.engine='manual_barrier' requires risk.target_vol=null.")
        if dict(cfg["risk"].get("sizing", {}) or {}):
            raise ConfigValidationError("backtest.engine='manual_barrier' requires risk.sizing={}; size via signal params.")
        if bool(dict(cfg["risk"].get("dd_guard", {}) or {}).get("enabled", True)):
            raise ConfigValidationError("backtest.engine='manual_barrier' requires risk.dd_guard.enabled=false.")
    if str(cfg["backtest"].get("engine", "vectorized")) == "portfolio_barrier":
        if not bool(cfg["portfolio"].get("enabled", False)):
            raise ConfigValidationError("backtest.engine='portfolio_barrier' requires portfolio.enabled=true.")
        if str(cfg["data"].get("alignment", "inner")) not in {"inner", "outer"}:
            raise ConfigValidationError("backtest.engine='portfolio_barrier' requires data.alignment='inner' or 'outer'.")
        if str(cfg["portfolio"].get("construction", "signal_weights")) != "signal_weights":
            raise ConfigValidationError(
                "backtest.engine='portfolio_barrier' requires portfolio.construction='signal_weights'."
            )
        if cfg["risk"].get("target_vol") is not None:
            raise ConfigValidationError("backtest.engine='portfolio_barrier' requires risk.target_vol=null.")
        sizing_cfg = dict(cfg["risk"].get("sizing", {}) or {})
        if sizing_cfg and str(sizing_cfg.get("kind", "none")) != "ftmo_risk_per_trade":
            raise ConfigValidationError(
                "backtest.engine='portfolio_barrier' supports only risk.sizing.kind='ftmo_risk_per_trade'."
            )
        _validate_portfolio_barrier_parity(cfg)
    return cfg


__all__ = [
    "ConfigValidationError",
    "validate_backtest_block",
    "validate_data_block",
    "validate_diagnostics_block",
    "validate_execution_block",
    "validate_logging_block",
    "validate_features_block",
    "validate_model_block",
    "validate_model_stages_block",
    "validate_standalone_target_block",
    "validate_monitoring_block",
    "validate_panel_features_block",
    "validate_panel_signals_block",
    "validate_portfolio_block",
    "validate_resolved_config",
    "validate_risk_block",
    "validate_runtime_block",
    "validate_signals_block",
]
