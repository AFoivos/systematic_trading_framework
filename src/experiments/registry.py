from __future__ import annotations

from importlib import import_module
from typing import Any, Callable, Mapping, Optional, Union

import pandas as pd

from src.features import (
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
    add_rate_of_change,
    add_regime_context_features,
    add_return_momentum_features,
    add_roofing_filter,
    add_rolling_r2_trend_quality,
    add_schaff_trend_cycle_features,
    swing_extrema_context,
    add_shannon_entropy,
    add_shock_context_features,
    add_sinewave_indicator,
    add_supersmoother,
    add_support_resistance_features,
    add_support_resistance_v2_features,
    add_roc_features,
    add_rsi_features,
    add_session_context_features,
    add_trend_regime,
    add_trend_slope_volatility,
    add_stochastic_features,
    add_stochastic_rsi_features,
    add_vol_normalized_momentum_features,
    add_volatility_of_volatility,
    add_volatility_regime,
    add_volatility_features,
    add_volume_features,
    add_vwap_features,
    add_vpin,
    add_yang_zhang_volatility,
    add_zscore_momentum,
)
from src.features.technical.trend import add_trend_features
from src.signals import (
    c1_trend_pullback_vwap_signal,
    c2_regime_aware_momentum_signal,
    conviction_sizing_signal,
    dense_return_forecast_signal,
    ehlers_continuation_long_signal,
    ehlers_continuation_short_signal,
    ema_rms_ppo_vwap_signal,
    ema_stoch_rsi_pullback_signal,
    indicator_model_adaptive_pullback_signal,
    forecast_threshold_signal,
    forecast_vol_adjusted_signal,
    manual_long_model_filter_signal,
    meta_probability_side_signal,
    momentum_strategy,
    orb_candidate_side_signal,
    probability_vol_adjusted_signal,
    probabilistic_signal,
    ppo_adx_stochrsi_trend_signal,
    rsi_strategy,
    roc_long_only_conditions_signal,
    stc_roofing_hilbert_signal,
    stochastic_strategy,
    trend_state_signal,
    volatility_regime_strategy,
    vwap_rms_ema_cross_long_fractal_filter_signal,
    vwap_rms_ema_cross_long_hmm_gate_signal,
    vwap_rms_ema_cross_long_signal,
)
from src.utils.config_kinds import PORTFOLIO_MODEL_KINDS as CONFIG_PORTFOLIO_MODEL_KINDS
from src.utils.config_kinds import RL_MODEL_KINDS as CONFIG_RL_MODEL_KINDS

FeatureFn = Callable[..., pd.DataFrame]
SignalFn = Callable[..., Union[pd.DataFrame, pd.Series]]
SingleAssetModelFn = Callable[..., tuple[pd.DataFrame, Optional[object], dict]]
PortfolioModelFn = Callable[..., tuple[dict[str, pd.DataFrame], Optional[object], dict]]
ModelFn = Union[SingleAssetModelFn, PortfolioModelFn]


def _lazy_single_asset_model(attr_name: str) -> SingleAssetModelFn:
    def _call(*args: Any, **kwargs: Any) -> tuple[pd.DataFrame, Optional[object], dict]:
        module = import_module("src.experiments.models")
        return getattr(module, attr_name)(*args, **kwargs)

    _call.__name__ = attr_name
    return _call


def _lazy_portfolio_model(attr_name: str) -> PortfolioModelFn:
    def _call(*args: Any, **kwargs: Any) -> tuple[dict[str, pd.DataFrame], Optional[object], dict]:
        module = import_module("src.experiments.models")
        return getattr(module, attr_name)(*args, **kwargs)

    _call.__name__ = attr_name
    return _call


FEATURE_REGISTRY: Mapping[str, FeatureFn] = {
    "returns": add_close_returns,
    "volatility": add_volatility_features,
    "trend": add_trend_features,
    "trend_regime": add_trend_regime,
    "lags": add_lagged_features,
    "bollinger": add_bollinger_features,
    "macd": add_macd_features,
    "ppo": add_ppo_features,
    "roc": add_roc_features,
    "atr": add_atr_features,
    "adx": add_adx_features,
    "volume_features": add_volume_features,
    "vwap": add_vwap_features,
    "vwap_rms_ema_cross_long": vwap_rms_ema_cross_long_signal,
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
    "rate_of_change": add_rate_of_change,
    "zscore_momentum": add_zscore_momentum,
    "rolling_r2_trend_quality": add_rolling_r2_trend_quality,
    "trend_slope_volatility": add_trend_slope_volatility,
    "volatility_of_volatility": add_volatility_of_volatility,
    "volatility_regime": add_volatility_regime,
    "hmm_regime": add_hmm_regime,
    "hilbert_transform": add_hilbert_transform,
    "roofing_filter": add_roofing_filter,
    "schaff_trend_cycle": add_schaff_trend_cycle_features,
    "supersmoother": add_supersmoother,
    "shannon_entropy": add_shannon_entropy,
    "permutation_entropy": add_permutation_entropy,
    "vpin": add_vpin,
    "order_flow_imbalance": add_order_flow_imbalance,
}

SIGNAL_REGISTRY: Mapping[str, SignalFn] = {
    "c1_trend_pullback_vwap": c1_trend_pullback_vwap_signal,
    "c2_regime_aware_momentum": c2_regime_aware_momentum_signal,
    "ehlers_continuation_long": ehlers_continuation_long_signal,
    "ehlers_continuation_long_signal": ehlers_continuation_long_signal,
    "ehlers_continuation_short": ehlers_continuation_short_signal,
    "ehlers_continuation_short_signal": ehlers_continuation_short_signal,
    "trend_state": trend_state_signal,
    "ema_rms_ppo_vwap": ema_rms_ppo_vwap_signal,
    "probability_threshold": probabilistic_signal,
    "probability_conviction": conviction_sizing_signal,
    "probability_vol_adjusted": probability_vol_adjusted_signal,
    "meta_probability_side": meta_probability_side_signal,
    "orb_candidate_side": orb_candidate_side_signal,
    "ppo_adx_stochrsi_trend": ppo_adx_stochrsi_trend_signal,
    "roc_long_only_conditions": roc_long_only_conditions_signal,
    "ema_stoch_rsi_pullback": ema_stoch_rsi_pullback_signal,
    "indicator_model_adaptive_pullback": indicator_model_adaptive_pullback_signal,
    "manual_long_model_filter": manual_long_model_filter_signal,
    "dense_return_forecast": dense_return_forecast_signal,
    "forecast_threshold": forecast_threshold_signal,
    "forecast_vol_adjusted": forecast_vol_adjusted_signal,
    "rsi": rsi_strategy,
    "momentum": momentum_strategy,
    "stochastic": stochastic_strategy,
    "stc_roofing_hilbert": stc_roofing_hilbert_signal,
    "volatility_regime": volatility_regime_strategy,
    "vwap_rms_ema_cross_long_fractal_filter": vwap_rms_ema_cross_long_fractal_filter_signal,
    "vwap_rms_ema_cross_long_hmm_gate": vwap_rms_ema_cross_long_hmm_gate_signal,
    "vwap_rms_ema_cross_long": vwap_rms_ema_cross_long_signal,
}

SINGLE_ASSET_MODEL_REGISTRY: Mapping[str, SingleAssetModelFn] = {
    "elastic_net_clf": _lazy_single_asset_model("train_elastic_net_classifier"),
    "lightgbm_clf": _lazy_single_asset_model("train_lightgbm_classifier"),
    "lightgbm_regressor": _lazy_single_asset_model("train_lightgbm_regressor"),
    "logistic_regression_clf": _lazy_single_asset_model("train_logistic_regression_classifier"),
    "xgboost_clf": _lazy_single_asset_model("train_xgboost_classifier"),
    "event_transformer_encoder": _lazy_single_asset_model("train_event_transformer_encoder"),
    "sarimax_forecaster": _lazy_single_asset_model("train_sarimax_forecaster"),
    "garch_forecaster": _lazy_single_asset_model("train_garch_forecaster"),
    "lstm_forecaster": _lazy_single_asset_model("train_lstm_forecaster"),
    "patchtst_forecaster": _lazy_single_asset_model("train_patchtst_forecaster"),
    "tft_forecaster": _lazy_single_asset_model("train_tft_forecaster"),
    "tsfresh_extrema_feature_discovery": _lazy_single_asset_model("train_tsfresh_extrema_feature_discovery"),
    "ppo_agent": _lazy_single_asset_model("train_ppo_agent"),
    "dqn_agent": _lazy_single_asset_model("train_dqn_agent"),
}

PORTFOLIO_MODEL_REGISTRY: Mapping[str, PortfolioModelFn] = {
    "ppo_portfolio_agent": _lazy_portfolio_model("train_ppo_portfolio_agent"),
    "dqn_portfolio_agent": _lazy_portfolio_model("train_dqn_portfolio_agent"),
}

MODEL_REGISTRY: Mapping[str, ModelFn] = {
    **SINGLE_ASSET_MODEL_REGISTRY,
    **PORTFOLIO_MODEL_REGISTRY,
}

RL_MODEL_KINDS = CONFIG_RL_MODEL_KINDS
PORTFOLIO_MODEL_KINDS = CONFIG_PORTFOLIO_MODEL_KINDS


def get_feature_fn(name: str) -> FeatureFn:
    """
    Handle get feature fn inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    if name not in FEATURE_REGISTRY:
        raise KeyError(f"Unknown feature step: {name}")
    return FEATURE_REGISTRY[name]


def get_signal_fn(name: str) -> SignalFn:
    """
    Handle get signal fn inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    if name not in SIGNAL_REGISTRY:
        raise KeyError(f"Unknown signal kind: {name}")
    return SIGNAL_REGISTRY[name]


def get_model_fn(name: str) -> ModelFn:
    """
    Handle get model fn inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    if name not in MODEL_REGISTRY:
        raise KeyError(f"Unknown model kind: {name}")
    return MODEL_REGISTRY[name]


def is_portfolio_model_kind(name: str) -> bool:
    return name in PORTFOLIO_MODEL_KINDS


def is_rl_model_kind(name: str) -> bool:
    return name in RL_MODEL_KINDS
