from __future__ import annotations

import inspect
import math
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Callable, Mapping

import pandas as pd

from app.core.paths import get_paths
from app.schemas.market import NamedSeries
from app.schemas.transforms import (
    BuilderDefinition,
    ParameterDefinition,
    TransformSeriesRequest,
    TransformSeriesResponse,
    TransformStepConfig,
    TransformStepResult,
)
from app.services.data_loader import DataLoader
from app.services.schema_mapper import frame_to_series


PROJECT_ROOT = get_paths().project_root
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.features import (  # noqa: E402
    TSFRESH_ROLLING_CALCULATORS,
    add_adx_features,
    add_autocorrelation_periodogram,
    add_atr_features,
    add_bollinger_features,
    add_center_of_gravity,
    add_close_returns,
    add_cyber_cycle,
    add_decycler,
    add_decycler_oscillator,
    add_dominant_cycle_period,
    add_dominant_cycle_phase,
    add_even_better_sinewave,
    ehlers_ml_long_candidate_feature,
    add_fama,
    add_feature_transforms,
    add_fisher_transform,
    add_fractal_dimension,
    add_frama,
    add_garman_klass_volatility,
    add_hilbert_transform,
    add_homodyne_discriminator,
    add_hmm_regime,
    add_hurst_exponent,
    add_instantaneous_trendline,
    add_indicator_pullback_features,
    add_inverse_fisher_transform,
    add_lagged_features,
    add_laguerre_rsi,
    add_macd_features,
    add_macro_context_features,
    add_mama,
    add_mfi_features,
    add_multi_timeframe_features,
    add_opening_range_breakout_features,
    add_order_flow_imbalance,
    add_parkinson_volatility,
    add_permutation_entropy,
    add_ppo_features,
    add_price_momentum_features,
    add_regime_context_features,
    add_return_momentum_features,
    add_roofing_filter,
    add_rolling_r2_trend_quality,
    add_schaff_trend_cycle_features,
    add_roc_features,
    add_rsi_features,
    add_session_context_features,
    add_shannon_entropy,
    add_shock_context_features,
    add_sinewave_indicator,
    add_supersmoother,
    add_stochastic_features,
    add_stochastic_rsi_features,
    add_support_resistance_features,
    add_support_resistance_v2_features,
    add_trend_slope_volatility,
    add_volatility_of_volatility,
    add_volatility_regime,
    add_vol_normalized_momentum_features,
    add_volatility_features,
    add_volume_features,
    add_vpin,
    add_vwap_features,
    add_yang_zhang_volatility,
    add_zscore_momentum,
    swing_extrema_context,
)
from src.features.technical.trend import add_trend_features, add_trend_regime_features  # noqa: E402
from src.signals.registry import SIGNAL_REGISTRY as EXPERIMENT_SIGNAL_REGISTRY  # noqa: E402
from src.signals import (  # noqa: E402
    ehlers_semiscalp_long_feature,
    ema_stoch_rsi_pullback_signal,
    indicator_model_adaptive_pullback_signal,
    regime_filtered_signal,
    roc_long_only_conditions_signal,
    vwap_rms_ema_cross_long_signal,
)
from src.targets.classifier import build_classifier_target  # noqa: E402
from src.targets.forward_return import build_forward_return_target  # noqa: E402
from src.targets.r_multiple import build_r_multiple_target  # noqa: E402
from src.targets.triple_barrier import build_triple_barrier_target  # noqa: E402
from app.services.transform_dependencies import call_with_materialized_dependencies  # noqa: E402


BuilderFn = Callable[..., Any]
FeatureFn = Callable[..., pd.DataFrame]
SignalFn = Callable[..., pd.DataFrame | pd.Series]

FEATURE_REGISTRY: Mapping[str, FeatureFn] = {
    "returns": add_close_returns,
    "volatility": add_volatility_features,
    "trend": add_trend_features,
    "trend_regime": add_trend_regime_features,
    "lags": add_lagged_features,
    "bollinger": add_bollinger_features,
    "macd": add_macd_features,
    "ppo": add_ppo_features,
    "roc": add_roc_features,
    "atr": add_atr_features,
    "adx": add_adx_features,
    "volume_features": add_volume_features,
    "vwap": add_vwap_features,
    "mfi": add_mfi_features,
    "rsi": add_rsi_features,
    "stochastic": add_stochastic_features,
    "stochastic_rsi": add_stochastic_rsi_features,
    "price_momentum": add_price_momentum_features,
    "return_momentum": add_return_momentum_features,
    "vol_normalized_momentum": add_vol_normalized_momentum_features,
    "session_context": add_session_context_features,
    "regime_context": add_regime_context_features,
    "shock_context": add_shock_context_features,
    "hmm_regime": add_hmm_regime,
    "support_resistance": add_support_resistance_features,
    "support_resistance_v2": add_support_resistance_v2_features,
    "macro_context": add_macro_context_features,
    "feature_transforms": add_feature_transforms,
    "multi_timeframe": add_multi_timeframe_features,
    "opening_range_breakout": add_opening_range_breakout_features,
    "swing_extrema_context": swing_extrema_context,
    "roc_long_only_conditions": roc_long_only_conditions_signal,
    "ema_stoch_rsi_pullback": ema_stoch_rsi_pullback_signal,
    "indicator_pullback": add_indicator_pullback_features,
    "indicator_model_adaptive_pullback": indicator_model_adaptive_pullback_signal,
    "ehlers_semiscalp_long": ehlers_semiscalp_long_feature,
    "ehlers_ml_long_candidate": ehlers_ml_long_candidate_feature,
    "mama": add_mama,
    "fama": add_fama,
    "dominant_cycle_period": add_dominant_cycle_period,
    "dominant_cycle_phase": add_dominant_cycle_phase,
    "instantaneous_trendline": add_instantaneous_trendline,
    "fisher_transform": add_fisher_transform,
    "inverse_fisher_transform": add_inverse_fisher_transform,
    "sinewave_indicator": add_sinewave_indicator,
    "cyber_cycle": add_cyber_cycle,
    "decycler": add_decycler,
    "decycler_oscillator": add_decycler_oscillator,
    "laguerre_rsi": add_laguerre_rsi,
    "frama": add_frama,
    "center_of_gravity": add_center_of_gravity,
    "even_better_sinewave": add_even_better_sinewave,
    "autocorrelation_periodogram": add_autocorrelation_periodogram,
    "homodyne_discriminator": add_homodyne_discriminator,
    "parkinson_volatility": add_parkinson_volatility,
    "garman_klass_volatility": add_garman_klass_volatility,
    "yang_zhang_volatility": add_yang_zhang_volatility,
    "hurst_exponent": add_hurst_exponent,
    "fractal_dimension": add_fractal_dimension,
    "zscore_momentum": add_zscore_momentum,
    "rolling_r2_trend_quality": add_rolling_r2_trend_quality,
    "trend_slope_volatility": add_trend_slope_volatility,
    "volatility_of_volatility": add_volatility_of_volatility,
    "volatility_regime": add_volatility_regime,
    "hilbert_transform": add_hilbert_transform,
    "roofing_filter": add_roofing_filter,
    "schaff_trend_cycle": add_schaff_trend_cycle_features,
    "supersmoother": add_supersmoother,
    "shannon_entropy": add_shannon_entropy,
    "permutation_entropy": add_permutation_entropy,
    "vpin": add_vpin,
    "order_flow_imbalance": add_order_flow_imbalance,
    "vwap_rms_ema_cross_long": vwap_rms_ema_cross_long_signal,
}

SIGNAL_REGISTRY: Mapping[str, SignalFn] = {
    **{
        name: fn
        for name, fn in EXPERIMENT_SIGNAL_REGISTRY.items()
        if not (name.endswith("_signal") and name.removesuffix("_signal") in EXPERIMENT_SIGNAL_REGISTRY)
    },
    "regime_filtered": regime_filtered_signal,
}

TARGET_REGISTRY: dict[str, Callable[[pd.DataFrame, dict[str, Any] | None], tuple[pd.DataFrame, str, str, dict[str, Any]]]] = {
    "forward_return": build_forward_return_target,
    "triple_barrier": build_triple_barrier_target,
    "r_multiple": build_r_multiple_target,
    "classifier": build_classifier_target,
}

TARGET_PARAM_DEFAULTS: dict[str, dict[str, Any]] = {
    "forward_return": {
        "price_col": "close",
        "returns_col": None,
        "returns_type": "simple",
        "horizon": 1,
        "fwd_col": "target_fwd_1",
        "label_col": "label",
        "threshold": 0.0,
        "quantiles": None,
    },
    "triple_barrier": {
        "price_col": "close",
        "open_col": "open",
        "high_col": "high",
        "low_col": "low",
        "returns_col": None,
        "volatility_col": None,
        "label_col": "label",
        "event_ret_col": "tb_event_ret",
        "max_holding": 24,
        "upper_mult": 2.0,
        "lower_mult": 2.0,
        "neutral_label": "drop",
        "tie_break": "closest_to_open",
        "vol_window": 24,
        "min_vol": 1e-4,
        "side_col": None,
        "candidate_col": None,
        "candidate_mode": "all_nonzero",
        "entry_price_mode": "current_close",
        "label_mode": None,
        "add_r_multiple": False,
        "r_col": "tb_event_r",
        "oriented_r_col": "tb_oriented_r",
        "r_clip": None,
    },
    "r_multiple": {
        "candidate_col": "manual_long_signal",
        "label_col": "label",
        "fwd_col": "r_target_event_ret",
        "candidate_out_col": "r_target_candidate",
        "price_col": "close",
        "open_col": "open",
        "high_col": "high",
        "low_col": "low",
        "volatility_col": "vol_rolling_24",
        "entry_price_mode": "next_open",
        "side": "long_only",
        "target_r_min": 1.0,
        "take_profit_r": 2.0,
        "stop_loss_r": 1.0,
        "max_holding_bars": 16,
        "stop_mode": "volatility_stop",
        "stop_loss_return": 0.005,
        "take_profit_return": 0.010,
        "tie_break": "conservative",
        "allow_partial_horizon": False,
        "diagnostic_feature_cols": None,
    },
    "classifier": {
        "kind": "forward_return",
        "price_col": "close",
        "returns_col": None,
        "returns_type": "simple",
        "horizon": 1,
        "fwd_col": "target_fwd_1",
        "label_col": "label",
        "threshold": 0.0,
        "quantiles": None,
    },
}

PARAM_OPTIONS: dict[str, list[Any]] = {
    "returns_type": ["simple", "log"],
    "method": ["wilder", "sma", "ema"],
    "mode": ["long_short_hold", "long_short"],
    "neutral_label": ["drop", "lower", "upper"],
    "tie_break": ["closest_to_open", "upper", "lower", "conservative", "take_profit", "stop_loss"],
    "candidate_mode": ["all_nonzero", "side_change"],
    "entry_price_mode": ["current_close", "next_open"],
    "label_mode": ["binary", "ternary", "meta"],
    "side": ["long_only"],
    "stop_mode": ["volatility_stop", "fixed_return"],
    "kind": ["forward_return", "triple_barrier", "r_multiple"],
    "timestamp_convention": ["bar_close", "bar_start"],
}

SKIPPED_RUNTIME_PARAMETERS = {"df"}
FEATURE_PARAM_DEFAULTS: dict[str, dict[str, Any]] = {
    "mama": {
        "price_col": "close",
        "fast_limit": 0.5,
        "slow_limit": 0.05,
        "output_col": "mama",
    },
    "fama": {
        "price_col": "close",
        "fast_limit": 0.5,
        "slow_limit": 0.05,
        "output_col": "fama",
    },
    "dominant_cycle_period": {
        "price_col": "close",
        "output_col": "dominant_cycle_period",
    },
    "dominant_cycle_phase": {
        "price_col": "close",
        "output_col": "dominant_cycle_phase",
    },
    "instantaneous_trendline": {
        "price_col": "close",
        "alpha": 0.07,
        "output_col": "instantaneous_trendline",
        "trigger_col": "instantaneous_trendline_trigger",
        "add_trigger": True,
    },
    "fisher_transform": {
        "price_col": "close",
        "window": 10,
        "clip": 0.999,
        "output_col": "fisher_transform_10",
        "signal_col": "fisher_transform_10_signal",
        "add_signal": True,
    },
    "inverse_fisher_transform": {
        "input_col": "close",
        "window": 10,
        "scale": 1.0,
        "normalize": True,
        "output_col": "inverse_fisher_transform_10",
    },
    "sinewave_indicator": {
        "price_col": "close",
        "lead_degrees": 45.0,
        "output_col": "sinewave",
        "lead_output_col": "lead_sinewave",
    },
    "cyber_cycle": {
        "price_col": "close",
        "alpha": 0.07,
        "output_col": "cyber_cycle",
        "trigger_col": "cyber_cycle_trigger",
        "add_trigger": True,
    },
    "decycler": {
        "price_col": "close",
        "period": 60,
        "output_col": "decycler_60",
    },
    "decycler_oscillator": {
        "price_col": "close",
        "fast_period": 30,
        "slow_period": 60,
        "output_col": "decycler_oscillator_30_60",
    },
    "laguerre_rsi": {
        "price_col": "close",
        "gamma": 0.5,
        "output_col": "laguerre_rsi",
        "as_percent": False,
    },
    "frama": {
        "price_col": "close",
        "high_col": "high",
        "low_col": "low",
        "window": 16,
        "fast_period": 4,
        "slow_period": 300,
        "output_col": "frama_16",
        "alpha_col": "frama_16_alpha",
        "fractal_dimension_col": "frama_16_fractal_dimension",
        "add_diagnostics": False,
    },
    "center_of_gravity": {
        "price_col": "close",
        "window": 10,
        "output_col": "center_of_gravity_10",
    },
    "even_better_sinewave": {
        "price_col": "close",
        "duration": 40,
        "smoothing_period": 10,
        "power_window": 3,
        "output_col": "even_better_sinewave",
    },
    "autocorrelation_periodogram": {
        "price_col": "close",
        "min_period": 10,
        "max_period": 48,
        "window": 96,
        "output_col": "autocorrelation_periodogram_10_48",
        "power_col": "autocorrelation_periodogram_10_48_power",
        "add_power": False,
    },
    "homodyne_discriminator": {
        "price_col": "close",
        "use_smoothed_period": False,
        "output_col": "homodyne_discriminator",
    },
    "feature_transforms": {
        "transforms": [
            {
                "kind": "rolling_stat",
                "source_col": "close_logret",
                "mode": "root_mean_square",
                "window": 48,
                "shift": 0,
                "output_col": "close_logret__root_mean_square",
            }
        ]
    },
    "hmm_regime": {
        "feature_cols": ["close_logret"],
        "n_states": 2,
        "mode": "expanding",
        "min_train_size": 35,
        "refit_interval": 25,
        "covariance_type": "diag",
        "n_iter": 50,
        "random_state": 0,
        "output_col": "hmm_regime",
        "include_probabilities": False,
    },
    "rolling_r2_trend_quality": {
        "price_col": "close",
        "window": 96,
        "output_col": "rolling_r2_96",
        "slope_col": "rolling_r2_slope_96",
        "intercept_col": "rolling_r2_intercept_96",
        "rising_col": "rolling_r2_96_rising",
        "trend_quality_col": "rolling_r2_96_ok",
        "trend_quality_threshold": 0.60,
    },
    "trend_slope_volatility": {
        "price_col": "close",
        "volatility_col": "atr_over_price_20",
        "window": 96,
        "annualize": False,
        "periods_per_year": None,
        "slope_col": "trend_slope_96",
        "volatility_used_col": "trend_vol_used_96",
        "slope_vol_ratio_col": "trend_slope_vol_ratio_96",
        "positive_col": "trend_slope_vol_ratio_96_positive",
        "rising_col": "trend_slope_vol_ratio_96_rising",
        "strong_trend_col": "trend_slope_vol_ratio_96_strong",
        "strong_threshold": 1.0,
    },
    "volatility_of_volatility": {
        "volatility_col": "atr_over_price_20",
        "window": 96,
        "mean_window": 192,
        "output_col": "vov_atr_96",
        "mean_col": "vov_atr_96_mean_192",
        "ratio_col": "vov_atr_96_ratio_192",
        "rising_col": "vov_atr_96_rising",
        "high_vov_col": "vov_atr_96_high",
        "high_vov_mult": 1.10,
    },
}
FEATURE_PARAM_OPTIONS: dict[str, dict[str, list[Any]]] = {
    "hmm_regime": {
        "mode": ["expanding", "static_train"],
        "covariance_type": ["diag", "full", "tied", "spherical"],
    }
}

FEATURE_METADATA: dict[str, dict[str, Any]] = {
    "mama": {
        "display_name": "MAMA",
        "description": "Mesa Adaptive Moving Average from John Ehlers.",
        "category": "Ehlers",
    },
    "fama": {
        "display_name": "FAMA",
        "description": "Following Adaptive Moving Average paired with MAMA.",
        "category": "Ehlers",
    },
    "dominant_cycle_period": {
        "display_name": "Dominant Cycle Period",
        "description": "Causal MESA estimate of the current dominant cycle length.",
        "category": "Ehlers",
    },
    "dominant_cycle_phase": {
        "display_name": "Dominant Cycle Phase",
        "description": "Causal MESA estimate of cycle phase in degrees.",
        "category": "Ehlers",
    },
    "instantaneous_trendline": {
        "display_name": "Instantaneous Trendline",
        "description": "Ehlers low-lag instantaneous trendline with optional trigger.",
        "category": "Ehlers",
    },
    "fisher_transform": {
        "display_name": "Fisher Transform",
        "description": "Trailing-range Fisher Transform oscillator.",
        "category": "Ehlers",
    },
    "inverse_fisher_transform": {
        "display_name": "Inverse Fisher Transform",
        "description": "Bounded inverse Fisher transform for normalized inputs.",
        "category": "Ehlers",
    },
    "sinewave_indicator": {
        "display_name": "Sinewave Indicator",
        "description": "Cycle sine and lead-sine values derived from causal MESA phase.",
        "category": "Ehlers",
    },
    "cyber_cycle": {
        "display_name": "Cyber Cycle",
        "description": "Ehlers Cyber Cycle oscillator with optional trigger.",
        "category": "Ehlers",
    },
    "decycler": {
        "display_name": "Decycler",
        "description": "Ehlers decycler trend filter using a causal high-pass removal.",
        "category": "Ehlers",
    },
    "decycler_oscillator": {
        "display_name": "Decycler Oscillator",
        "description": "Difference between fast and slow decyclers scaled by price.",
        "category": "Ehlers",
    },
    "laguerre_rsi": {
        "display_name": "Laguerre RSI",
        "description": "Ehlers Laguerre-filtered RSI oscillator.",
        "category": "Ehlers",
    },
    "frama": {
        "display_name": "FRAMA",
        "description": "Fractal Adaptive Moving Average with optional alpha diagnostics.",
        "category": "Ehlers",
    },
    "center_of_gravity": {
        "display_name": "Center of Gravity",
        "description": "Ehlers Center of Gravity oscillator over a trailing window.",
        "category": "Ehlers",
    },
    "even_better_sinewave": {
        "display_name": "Even Better Sinewave",
        "description": "High-pass plus SuperSmoother normalized sinewave oscillator.",
        "category": "Ehlers",
    },
    "autocorrelation_periodogram": {
        "display_name": "Autocorrelation Periodogram",
        "description": "Causal autocorrelation-based dominant-period estimate.",
        "category": "Ehlers",
    },
    "homodyne_discriminator": {
        "display_name": "Homodyne Discriminator",
        "description": "Homodyne discriminator period estimate from in-phase/quadrature components.",
        "category": "Ehlers",
    },
}
SIGNAL_PARAM_DEFAULTS: dict[str, dict[str, Any]] = {
    "ema_rms_ppo_vwap": {
        "close_col": "close",
        "atr_col": "atr_14",
        "ema_fast_rms_col": "ema_20__root_mean_square",
        "ema_mid_rms_col": "ema_50__root_mean_square",
        "ema_slow_rms_col": "ema_100__root_mean_square",
        "vwap_col": "vwap_20",
        "vwap_rms_col": "vwap_20__root_mean_square",
        "ppo_col": "ppo",
        "ppo_signal_col": "ppo_signal",
        "mode": "long_short",
        "require_vwap_rms_filter": False,
        "require_rms_slope_filter": False,
        "max_vwap_distance_atr": 1.0,
        "min_rms_slope": 0.0,
        "signal_col": "signal_side",
        "candidate_col": "signal_candidate",
    },
    "vwap_rms_ema_cross_long": {
        "ema_mid_col": "ema_50",
        "ema_slow_col": "ema_100",
        "ema_mid_rms_col": "ema_50__root_mean_square",
        "vwap_rms_col": "vwap_20__root_mean_square",
        "ppo_col": "ppo",
        "ppo_signal_col": "ppo_signal",
        "ppo_hist_min": 0.0,
        "signal_col": "signal_side",
        "candidate_col": "signal_candidate",
    },
    "momentum": {"momentum_col": "close_mom_20"},
    "rsi": {"rsi_col": "close_rsi_14"},
    "stochastic": {"k_col": "close_stoch_k_14"},
    "trend_state": {"state_col": "close_trend_state_sma_20_50"},
    "volatility_regime": {"vol_col": "vol_rolling_20"},
}


def get_feature_fn(name: str) -> FeatureFn:
    if name not in FEATURE_REGISTRY:
        raise KeyError(f"Unknown feature step: {name}")
    return FEATURE_REGISTRY[name]


def get_signal_fn(name: str) -> SignalFn:
    if name not in SIGNAL_REGISTRY:
        raise KeyError(f"Unknown signal kind: {name}")
    return SIGNAL_REGISTRY[name]


def _safe_value(value: Any) -> Any:
    if value is inspect._empty:
        return None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_safe_value(item) for item in value]
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    if isinstance(value, set):
        return sorted(_safe_value(item) for item in value)
    if isinstance(value, dict):
        return {str(key): _safe_value(item) for key, item in value.items()}
    if hasattr(value, "item"):
        return _safe_value(value.item())
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _annotation_text(annotation: Any) -> str | None:
    if annotation is inspect._empty:
        return None
    if isinstance(annotation, str):
        return annotation
    return getattr(annotation, "__name__", str(annotation))


def _infer_kind(default: Any, annotation: Any) -> str:
    if default is not inspect._empty and default is not None:
        if isinstance(default, bool):
            return "boolean"
        if isinstance(default, int) and not isinstance(default, bool):
            return "integer"
        if isinstance(default, float):
            return "number"
        if isinstance(default, str):
            return "string"
        if isinstance(default, (list, tuple, set)):
            return "list"
        if isinstance(default, dict):
            return "object"

    annotation_lower = (_annotation_text(annotation) or "").lower()
    if "mapping" in annotation_lower or "dict" in annotation_lower:
        return "object"
    if "sequence" in annotation_lower or "iterable" in annotation_lower or "list" in annotation_lower or "tuple" in annotation_lower:
        return "list"
    if "bool" in annotation_lower:
        return "boolean"
    if "int" in annotation_lower:
        return "integer"
    if "float" in annotation_lower:
        return "number"
    if "str" in annotation_lower:
        return "string"
    return "any"


def _callable_import_path(fn: BuilderFn) -> str | None:
    module = getattr(fn, "__module__", None)
    name = getattr(fn, "__qualname__", getattr(fn, "__name__", None))
    if not module or not name:
        return None
    return f"{module}.{name}"


def _callable_default_overrides(fn: BuilderFn) -> dict[str, Any]:
    module = inspect.getmodule(fn)
    defaults = getattr(module, "_DEFAULT_CFG", None) if module is not None else None
    if not isinstance(defaults, Mapping):
        return {}
    return dict(defaults)


def _parameter_definitions(
    fn: BuilderFn,
    *,
    default_overrides: dict[str, Any] | None = None,
    option_overrides: dict[str, list[Any]] | None = None,
) -> list[ParameterDefinition]:
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return []
    parameters: list[ParameterDefinition] = []
    overrides = dict(default_overrides or {})
    options = dict(option_overrides or {})
    defined_names: set[str] = set()
    accepts_keyword_params = False
    for name, param in signature.parameters.items():
        if name in SKIPPED_RUNTIME_PARAMETERS:
            continue
        if param.kind is inspect.Parameter.VAR_KEYWORD:
            accepts_keyword_params = True
            continue
        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            continue
        default = overrides.get(name, param.default)
        parameters.append(
            ParameterDefinition(
                name=name,
                kind=_infer_kind(default, param.annotation),
                required=param.default is inspect._empty and name not in overrides,
                default_value=_safe_value(default),
                annotation=_annotation_text(param.annotation),
                options=options.get(name, PARAM_OPTIONS.get(name)),
            )
        )
        defined_names.add(name)
    if accepts_keyword_params:
        for name, default in overrides.items():
            if name in defined_names:
                continue
            parameters.append(
                ParameterDefinition(
                    name=name,
                    kind=_infer_kind(default, inspect._empty),
                    required=False,
                    default_value=_safe_value(default),
                    options=options.get(name, PARAM_OPTIONS.get(name)),
                )
            )
    return parameters


def _target_parameter_definitions(name: str) -> list[ParameterDefinition]:
    params = TARGET_PARAM_DEFAULTS.get(name, {})
    definitions: list[ParameterDefinition] = []
    for key, default in params.items():
        definitions.append(
            ParameterDefinition(
                name=key,
                kind=_infer_kind(default, inspect._empty),
                required=False,
                default_value=_safe_value(default),
                options=PARAM_OPTIONS.get(key),
            )
        )
    return definitions


def _docstring(fn: BuilderFn) -> str | None:
    raw = inspect.getdoc(fn)
    if not raw:
        return None
    return raw.strip()


def _apply_output_mapping(
    df: pd.DataFrame,
    outputs: dict[str, Any] | None,
    *,
    owner: str,
    ignore_missing_keys: set[str] | None = None,
) -> pd.DataFrame:
    if not outputs:
        return df
    if not isinstance(outputs, dict):
        raise TypeError(f"{owner}.outputs must be a mapping when provided.")

    rename_map: dict[str, str] = {}
    ignored = set(ignore_missing_keys or set())
    for source_col, target_col in outputs.items():
        if not isinstance(source_col, str) or not source_col.strip():
            raise ValueError(f"{owner}.outputs keys must be non-empty strings.")
        if not isinstance(target_col, str) or not target_col.strip():
            raise ValueError(f"{owner}.outputs values must be non-empty strings.")
        if source_col not in df.columns:
            if source_col in ignored:
                continue
            raise KeyError(
                f"{owner}.outputs refers to source column '{source_col}' which was not emitted by the step."
            )
        rename_map[source_col] = target_col

    renamed = df.rename(columns=rename_map)
    if len(set(renamed.columns)) != len(renamed.columns):
        duplicates = renamed.columns[renamed.columns.duplicated()].unique().tolist()
        raise ValueError(
            f"{owner}.outputs resolves to duplicate column names after renaming: {duplicates}."
        )
    return renamed


def _call_feature_fn(fn: FeatureFn, df: pd.DataFrame, params: dict[str, Any], *, asset: str | None) -> pd.DataFrame:
    call_params = dict(params)
    if asset is not None and "asset" not in call_params:
        try:
            accepts_asset = "asset" in inspect.signature(fn).parameters
        except (TypeError, ValueError):
            accepts_asset = False
        if accepts_asset:
            call_params["asset"] = asset
    return fn(df, **call_params)


def apply_feature_steps(
    df: pd.DataFrame,
    steps: list[dict[str, Any]],
    *,
    asset: str | None = None,
) -> pd.DataFrame:
    out = df
    for idx, step in enumerate(steps):
        if "step" not in step:
            raise ValueError("Each feature step must include a 'step' key.")
        if step.get("enabled", True) is False:
            continue
        name = step["step"]
        params = step.get("params", {}) or {}
        fn = get_feature_fn(name)
        out = _call_feature_fn(fn, out, params, asset=asset)
        out = _apply_output_mapping(out, step.get("outputs"), owner=f"features[{idx}]")
    return out


def apply_signal_step(df: pd.DataFrame, signals_cfg: dict[str, Any]) -> pd.DataFrame:
    kind = signals_cfg.get("kind", "none")
    if kind == "none":
        params = signals_cfg.get("params", {}) or {}
        signal_col = params.get("signal_col")
        if signal_col not in (None, ""):
            frame = df.copy()
            frame[str(signal_col)] = 0.0
            return _apply_output_mapping(
                frame,
                signals_cfg.get("outputs"),
                owner="signals",
                ignore_missing_keys={"signal_col"},
            )
        return df
    params = signals_cfg.get("params", {}) or {}
    fn = get_signal_fn(kind)
    out = fn(df, **params)
    if isinstance(out, pd.DataFrame):
        return _apply_output_mapping(
            out,
            signals_cfg.get("outputs"),
            owner="signals",
            ignore_missing_keys={"signal_col"},
        )
    if isinstance(out, pd.Series):
        frame = df.copy()
        frame[out.name] = out
        return _apply_output_mapping(
            frame,
            signals_cfg.get("outputs"),
            owner="signals",
            ignore_missing_keys={"signal_col"},
        )
    raise TypeError(f"Signal function for kind='{kind}' returned unsupported type: {type(out)}")


def _definitions_from_registry(
    *,
    registry: dict[str, Any],
    source_type: str,
    resolver: Callable[[str], BuilderFn],
) -> list[BuilderDefinition]:
    definitions: list[BuilderDefinition] = []
    for name in sorted(registry):
        fn = resolver(name)
        definitions.append(
            BuilderDefinition(
                name=name,
                source_type=source_type,  # type: ignore[arg-type]
                import_path=_callable_import_path(fn),
                parameters=_parameter_definitions(fn),
                docstring=_docstring(fn),
            )
        )
    return definitions


def feature_builders() -> list[BuilderDefinition]:
    definitions: list[BuilderDefinition] = []
    for name in sorted(FEATURE_REGISTRY):
        fn = get_feature_fn(name)
        feature_meta = dict(FEATURE_METADATA.get(name, {}))
        display_name = feature_meta.pop("display_name", None)
        description = feature_meta.pop("description", None)
        definitions.append(
            BuilderDefinition(
                name=name,
                display_name=display_name,
                description=description,
                source_type="feature",
                import_path=_callable_import_path(fn),
                parameters=_parameter_definitions(
                    fn,
                    default_overrides={
                        **_callable_default_overrides(fn),
                        **FEATURE_PARAM_DEFAULTS.get(name, {}),
                    },
                    option_overrides=FEATURE_PARAM_OPTIONS.get(name),
                ),
                docstring=_docstring(fn),
                metadata=feature_meta,
            )
        )
    return definitions


def signal_builders() -> list[BuilderDefinition]:
    definitions: list[BuilderDefinition] = []
    for name in sorted(SIGNAL_REGISTRY):
        fn = get_signal_fn(name)
        definitions.append(
            BuilderDefinition(
                name=name,
                source_type="signal",
                import_path=_callable_import_path(fn),
                parameters=_parameter_definitions(
                    fn,
                    default_overrides={
                        **_callable_default_overrides(fn),
                        **SIGNAL_PARAM_DEFAULTS.get(name, {}),
                    },
                ),
                docstring=_docstring(fn),
            )
        )
    return definitions


def target_builders() -> list[BuilderDefinition]:
    definitions: list[BuilderDefinition] = []
    for name in sorted(TARGET_REGISTRY):
        fn = TARGET_REGISTRY[name]
        definitions.append(
            BuilderDefinition(
                name=name,
                source_type="target",
                import_path=_callable_import_path(fn),
                parameters=_target_parameter_definitions(name),
                docstring=_docstring(fn),
            )
        )
    return definitions


def _new_columns(before: Iterable[str], after: Iterable[str]) -> list[str]:
    before_set = set(before)
    return [str(column) for column in after if column not in before_set]


def _configured_output_columns(
    *,
    before: Iterable[str],
    after: Iterable[str],
    outputs: dict[str, str] | None,
    meta: dict[str, Any] | None = None,
    preferred: Iterable[str] = (),
    exclude: Iterable[str] = (),
) -> list[str]:
    after_list = [str(column) for column in after]
    candidates: list[str] = []
    if outputs:
        candidates.extend(str(value) for value in outputs.values())
    if meta:
        raw_outputs = meta.get("output_cols")
        if isinstance(raw_outputs, list):
            candidates.extend(str(value) for value in raw_outputs)
        for key in ("label_col", "fwd_col", "event_ret_col", "candidate_col", "oriented_r_col", "r_col"):
            value = meta.get(key)
            if value is not None:
                candidates.append(str(value))
    candidates.extend(str(value) for value in preferred)
    candidates.extend(_new_columns(before, after_list))
    seen: set[str] = set()
    excluded = set(exclude)
    selected: list[str] = []
    for column in candidates:
        if column in seen or column in excluded or column not in after_list:
            continue
        selected.append(column)
        seen.add(column)
    return selected


def _numeric_columns(frame: pd.DataFrame, columns: Iterable[str]) -> list[str]:
    numeric: list[str] = []
    for column in columns:
        if column not in frame.columns:
            continue
        if pd.api.types.is_numeric_dtype(frame[column]) or pd.api.types.is_bool_dtype(frame[column]):
            numeric.append(column)
    return numeric


def _series_response_items(frame: pd.DataFrame, source_type: str, columns: list[str]) -> list[NamedSeries]:
    numeric_columns = _numeric_columns(frame, columns)
    payload = frame_to_series(frame, numeric_columns) if numeric_columns else {}
    return [
        NamedSeries(series_id=name, source_type=source_type, points=points)
        for name, points in payload.items()
    ]


def _step_dict(step: TransformStepConfig) -> dict[str, Any]:
    params = dict(step.params)
    if step.step != "feature_transforms":
        params.pop("transforms", None)
    payload: dict[str, Any] = {
        "step": step.step,
        "params": params,
        "enabled": step.enabled,
    }
    if step.outputs:
        payload["outputs"] = step.outputs
    return payload


def _signal_step_dict(step: TransformStepConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": step.step,
        "params": {**SIGNAL_PARAM_DEFAULTS.get(step.step, {}), **step.params},
        "enabled": step.enabled,
    }
    if step.outputs:
        payload["outputs"] = step.outputs
    return payload


def _post_feature_transforms(step: TransformStepConfig) -> list[dict[str, object]]:
    if step.step == "feature_transforms":
        return []
    raw = step.params.get("transforms")
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise TypeError(f"{step.step}.params.transforms must be a list of transform mappings.")

    transforms: list[dict[str, object]] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise TypeError(f"{step.step}.params.transforms[{idx}] must be a transform mapping.")
        transforms.append(dict(item))
    return transforms


def _bulk_transform_output_col(kind: str, source_col: str, transform: dict[str, object]) -> str | None:
    if kind == "rolling_zscore":
        return f"{source_col}__zscore"
    if kind == "rolling_clip":
        return f"{source_col}__rolling_clip"
    if kind == "rolling_stat":
        return f"{source_col}__{_canonical_nested_rolling_stat_mode(transform.get('mode', 'root_mean_square'))}"
    return None


_NESTED_ROLLING_STAT_MODE_ALIASES = {
    "sum": "sum_values",
    "std": "standard_deviation",
    "var": "variance",
    "rms": "root_mean_square",
    "max": "maximum",
    "abs_max": "absolute_maximum",
    "min": "minimum",
}


def _canonical_nested_rolling_stat_mode(mode: object) -> str:
    normalized = str(mode).strip()
    return _NESTED_ROLLING_STAT_MODE_ALIASES.get(normalized, normalized)


def _bulk_transform_for_source(
    transform: dict[str, object],
    *,
    source_col: str,
    owner: str,
) -> dict[str, object]:
    kind = str(transform.get("kind", ""))
    if kind == "ratio":
        raise ValueError(f"{owner} cannot be applied to all parent feature outputs; ratio requires explicit sources.")
    if kind not in {"rolling_stat", "rolling_zscore", "rolling_clip", "tsfresh_rolling"}:
        raise ValueError(f"Unsupported nested feature transform kind: {kind!r}.")

    expanded = dict(transform)
    for key in (
        "source_col",
        "source_selector",
        "numerator_col",
        "numerator_selector",
        "denominator_col",
        "denominator_selector",
        "output_col",
        "output_prefix",
        "eps",
    ):
        expanded.pop(key, None)
    expanded["source_col"] = source_col
    output_col = _bulk_transform_output_col(kind, source_col, expanded)
    if output_col is not None:
        expanded["output_col"] = output_col
    if kind == "tsfresh_rolling":
        expanded["output_prefix"] = source_col
    return expanded


def _require_nested_source(
    transform: dict[str, object],
    *,
    field: str,
    allowed_columns: set[str],
    owner: str,
) -> None:
    value = transform.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{owner}.{field} must select one output column emitted by the parent feature step.")
    if value not in allowed_columns:
        raise ValueError(
            f"{owner}.{field}='{value}' is not an output column emitted by the parent feature step. "
            f"Allowed columns: {sorted(allowed_columns)}."
        )


def _expand_post_feature_transforms(
    transforms: list[dict[str, object]],
    *,
    feature_step: str,
    allowed_columns: list[str],
) -> list[dict[str, object]]:
    allowed = set(allowed_columns)
    if not allowed:
        raise ValueError(f"{feature_step}.params.transforms requires the parent feature step to emit selectable columns.")

    expanded: list[dict[str, object]] = []
    for idx, transform in enumerate(transforms):
        kind = str(transform.get("kind", ""))
        owner = f"{feature_step}.params.transforms[{idx}]"
        if kind == "ratio":
            _require_nested_source(transform, field="numerator_col", allowed_columns=allowed, owner=owner)
            _require_nested_source(transform, field="denominator_col", allowed_columns=allowed, owner=owner)
            expanded.append(transform)
        else:
            expanded.extend(
                _bulk_transform_for_source(transform, source_col=source_col, owner=owner)
                for source_col in allowed_columns
            )
    return expanded


def _tsfresh_calculators(value: object) -> list[str]:
    if value is None:
        return [str(calculator) for calculator in TSFRESH_ROLLING_CALCULATORS]
    if isinstance(value, (str, bytes)):
        return [str(value)]
    if isinstance(value, Iterable):
        return [str(calculator) for calculator in value]
    return [str(value)]


def _expected_transform_output_columns(transforms: Iterable[dict[str, object]]) -> list[str]:
    columns: list[str] = []
    for transform in transforms:
        kind = str(transform.get("kind", ""))
        if kind in {"ratio", "rolling_clip", "rolling_stat", "rolling_zscore"}:
            output_col = transform.get("output_col")
            if isinstance(output_col, str) and output_col:
                columns.append(output_col)
        elif kind == "tsfresh_rolling":
            source_col = transform.get("source_col")
            output_prefix = transform.get("output_prefix", source_col)
            if isinstance(output_prefix, str) and output_prefix:
                columns.extend(f"{output_prefix}__{calculator}" for calculator in _tsfresh_calculators(transform.get("calculators")))
    return columns


def _apply_feature_step(
    frame: pd.DataFrame,
    step: TransformStepConfig,
    *,
    asset: str | None,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    post_transforms = _post_feature_transforms(step)
    before = list(frame.columns)
    out, prerequisites = call_with_materialized_dependencies(
        frame,
        lambda materialized: apply_feature_steps(materialized, [_step_dict(step)], asset=asset),
    )
    feature_columns = _configured_output_columns(
        before=before,
        after=out.columns,
        outputs=step.outputs,
        exclude=prerequisites,
    )
    columns = list(feature_columns)
    if post_transforms:
        expanded_transforms = _expand_post_feature_transforms(
            post_transforms,
            feature_step=step.step,
            allowed_columns=feature_columns,
        )
        expected_transform_columns = _expected_transform_output_columns(expanded_transforms)
        before_transforms = list(out.columns)
        out = add_feature_transforms(out, transforms=expanded_transforms)
        columns.extend(
            _configured_output_columns(
                before=before_transforms,
                after=out.columns,
                outputs=None,
                preferred=expected_transform_columns,
            )
        )
    return out, _numeric_columns(out, columns), prerequisites


def _apply_signal(frame: pd.DataFrame, step: TransformStepConfig) -> tuple[pd.DataFrame, list[str], list[str]]:
    before = list(frame.columns)
    out, prerequisites = call_with_materialized_dependencies(
        frame,
        lambda materialized: apply_signal_step(materialized, _signal_step_dict(step)),
    )
    columns = _configured_output_columns(
        before=before,
        after=out.columns,
        outputs=step.outputs,
        exclude=prerequisites,
    )
    return out, _numeric_columns(out, columns), prerequisites


def _apply_target(
    frame: pd.DataFrame,
    step: TransformStepConfig,
) -> tuple[pd.DataFrame, list[str], dict[str, Any], list[str]]:
    if step.step not in TARGET_REGISTRY:
        raise KeyError(f"Unknown target builder: {step.step}")
    before = list(frame.columns)
    result, prerequisites = call_with_materialized_dependencies(
        frame,
        lambda materialized: TARGET_REGISTRY[step.step](materialized, dict(step.params)),
    )
    out, label_col, fwd_col, meta = result
    columns = _configured_output_columns(
        before=before,
        after=out.columns,
        outputs=step.outputs,
        meta=meta,
        preferred=[label_col, fwd_col],
        exclude=prerequisites,
    )
    return out, _numeric_columns(out, columns), meta, prerequisites


def run_transform_series(payload: TransformSeriesRequest) -> TransformSeriesResponse:
    frame, dataset = DataLoader().load_frame(
        asset=payload.asset,
        timeframe=payload.timeframe,
        source=payload.source,
        dataset_id=payload.dataset_id,
        start=payload.start,
        end=payload.end,
        require_ohlcv=True,
    )

    working = frame
    effective_asset = payload.asset or (dataset.assets[0] if len(dataset.assets) == 1 else None)
    step_results: list[TransformStepResult] = []
    selected: list[tuple[str, list[str]]] = []

    for step in payload.features:
        if not step.enabled:
            continue
        working, columns, prerequisites = _apply_feature_step(working, step, asset=effective_asset)
        selected.append(("feature", columns))
        step_results.append(
            TransformStepResult(
                source_type="feature",
                step=step.step,
                output_columns=columns,
                metadata={"materialized_prerequisites": prerequisites},
            )
        )

    for step in payload.signals:
        if not step.enabled:
            continue
        working, columns, prerequisites = _apply_signal(working, step)
        selected.append(("signal", columns))
        step_results.append(
            TransformStepResult(
                source_type="signal",
                step=step.step,
                output_columns=columns,
                metadata={"materialized_prerequisites": prerequisites},
            )
        )

    for step in payload.targets:
        if not step.enabled:
            continue
        working, columns, meta, prerequisites = _apply_target(working, step)
        selected.append(("target", columns))
        step_results.append(
            TransformStepResult(
                source_type="target",
                step=step.step,
                output_columns=columns,
                metadata={**meta, "materialized_prerequisites": prerequisites},
            )
        )

    response_frame = working.tail(payload.limit) if payload.limit else working
    series: list[NamedSeries] = []
    for source_type, columns in selected:
        series.extend(_series_response_items(response_frame, source_type, columns))

    return TransformSeriesResponse(
        series=series,
        steps=step_results,
        metadata={
            "dataset_id": dataset.id,
            "rows_loaded": int(len(frame)),
            "rows_returned": int(len(response_frame)),
        },
    )
