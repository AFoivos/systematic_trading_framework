from __future__ import annotations

FEATURE_KINDS = frozenset(
    {
        "adx",
        "autocorrelation_periodogram",
        "atr",
        "bollinger",
        "center_of_gravity",
        "cyber_cycle",
        "decycler",
        "decycler_oscillator",
        "dominant_cycle_period",
        "dominant_cycle_phase",
        "ema_stoch_rsi_pullback",
        "even_better_sinewave",
        "fama",
        "feature_transforms",
        "fisher_transform",
        "fractal_dimension",
        "frama",
        "garman_klass_volatility",
        "hilbert_transform",
        "homodyne_discriminator",
        "hmm_regime",
        "hurst_exponent",
        "instantaneous_trendline",
        "indicator_model_adaptive_pullback",
        "indicator_pullback",
        "inverse_fisher_transform",
        "lags",
        "laguerre_rsi",
        "macd",
        "macro_context",
        "mama",
        "mfi",
        "multi_timeframe",
        "opening_range_breakout",
        "order_flow_imbalance",
        "parkinson_volatility",
        "permutation_entropy",
        "ppo",
        "price_momentum",
        "rate_of_change",
        "regime_context",
        "return_momentum",
        "roofing_filter",
        "rolling_r2_trend_quality",
        "returns",
        "schaff_trend_cycle",
        "roc",
        "roc_long_only_conditions",
        "rsi",
        "session_context",
        "shannon_entropy",
        "shock_context",
        "sinewave_indicator",
        "stochastic",
        "stochastic_rsi",
        "supersmoother",
        "support_resistance",
        "support_resistance_v2",
        "swing_extrema_context",
        "trend",
        "trend_regime",
        "trend_slope_volatility",
        "vol_normalized_momentum",
        "volatility",
        "volatility_of_volatility",
        "volatility_regime",
        "volume_features",
        "vpin",
        "vwap_rms_ema_cross_long",
        "vwap",
        "yang_zhang_volatility",
        "zscore_momentum",
    }
)

SIGNAL_KINDS = frozenset(
    {
        "c1_trend_pullback_vwap",
        "c2_regime_aware_momentum",
        "ema_rms_ppo_vwap",
        "ema_stoch_rsi_pullback",
        "dense_return_forecast",
        "forecast_threshold",
        "forecast_vol_adjusted",
        "indicator_model_adaptive_pullback",
        "manual_long_model_filter",
        "meta_probability_side",
        "momentum",
        "orb_candidate_side",
        "ppo_adx_stochrsi_trend",
        "probability_conviction",
        "probability_threshold",
        "probability_vol_adjusted",
        "regime_filtered",
        "roc_long_only_conditions",
        "rsi",
        "stochastic",
        "stc_roofing_hilbert",
        "trend_state",
        "volatility_regime",
        "vwap_rms_ema_cross_long_fractal_filter",
        "vwap_rms_ema_cross_long_hmm_gate",
        "vwap_rms_ema_cross_long",
    }
)

SINGLE_ASSET_MODEL_KINDS = frozenset(
    {
        "dqn_agent",
        "event_transformer_encoder",
        "garch_forecaster",
        "elastic_net_clf",
        "lightgbm_clf",
        "lightgbm_regressor",
        "logistic_regression_clf",
        "lstm_forecaster",
        "patchtst_forecaster",
        "ppo_agent",
        "sarimax_forecaster",
        "tsfresh_extrema_feature_discovery",
        "tft_forecaster",
        "xgboost_clf",
    }
)

PORTFOLIO_MODEL_KINDS = frozenset(
    {
        "dqn_portfolio_agent",
        "ppo_portfolio_agent",
    }
)

MODEL_KINDS = frozenset({*SINGLE_ASSET_MODEL_KINDS, *PORTFOLIO_MODEL_KINDS})

RL_MODEL_KINDS = frozenset(
    {
        "dqn_agent",
        "dqn_portfolio_agent",
        "ppo_agent",
        "ppo_portfolio_agent",
    }
)

__all__ = [
    "FEATURE_KINDS",
    "MODEL_KINDS",
    "PORTFOLIO_MODEL_KINDS",
    "RL_MODEL_KINDS",
    "SIGNAL_KINDS",
    "SINGLE_ASSET_MODEL_KINDS",
]
