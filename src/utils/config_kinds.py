from __future__ import annotations

FEATURE_KINDS = frozenset(
    {
        "adx",
        "atr",
        "bollinger",
        "ema_stoch_rsi_pullback",
        "feature_transforms",
        "indicator_model_adaptive_pullback",
        "indicator_pullback",
        "lags",
        "macd",
        "macro_context",
        "mfi",
        "multi_timeframe",
        "opening_range_breakout",
        "ppo",
        "price_momentum",
        "regime_context",
        "return_momentum",
        "returns",
        "roc",
        "roc_long_only_conditions",
        "rsi",
        "session_context",
        "shock_context",
        "stochastic",
        "stochastic_rsi",
        "support_resistance",
        "support_resistance_v2",
        "swing_extrema_context",
        "trend",
        "trend_regime",
        "vol_normalized_momentum",
        "volatility",
        "volume_features",
        "vwap",
    }
)

SIGNAL_KINDS = frozenset(
    {
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
        "trend_state",
        "volatility_regime",
        "vwap_rms_ema_cross_long",
    }
)

SINGLE_ASSET_MODEL_KINDS = frozenset(
    {
        "dqn_agent",
        "event_transformer_encoder",
        "garch_forecaster",
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
