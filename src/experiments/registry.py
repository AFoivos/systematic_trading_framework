from __future__ import annotations

from typing import Callable, Mapping, Optional, Union

import pandas as pd

from src.features import (
    add_adx_features,
    add_atr_features,
    add_bollinger_features,
    add_close_returns,
    add_feature_transforms,
    add_lagged_features,
    add_macd_features,
    add_macro_context_features,
    add_mfi_features,
    add_ppo_features,
    add_price_momentum_features,
    add_regime_context_features,
    add_return_momentum_features,
    add_roc_features,
    add_rsi_features,
    add_session_context_features,
    add_stochastic_features,
    add_vol_normalized_momentum_features,
    add_volatility_features,
    add_volume_features,
)
from src.features.technical.trend import add_trend_features, add_trend_regime_features
from src.signals import (
    conviction_sizing_signal,
    forecast_threshold_signal,
    forecast_vol_adjusted_signal,
    momentum_strategy,
    probability_vol_adjusted_signal,
    probabilistic_signal,
    rsi_strategy,
    stochastic_strategy,
    trend_state_signal,
    volatility_regime_strategy,
)
from src.experiments.models import (
    train_dqn_agent,
    train_dqn_portfolio_agent,
    train_garch_forecaster,
    train_lightgbm_classifier,
    train_logistic_regression_classifier,
    train_ppo_agent,
    train_ppo_portfolio_agent,
    train_sarimax_forecaster,
    train_lstm_forecaster,
    train_patchtst_forecaster,
    train_tft_forecaster,
    train_xgboost_classifier,
)

FeatureFn = Callable[..., pd.DataFrame]
SignalFn = Callable[..., Union[pd.DataFrame, pd.Series]]
SingleAssetModelFn = Callable[..., tuple[pd.DataFrame, Optional[object], dict]]
PortfolioModelFn = Callable[..., tuple[dict[str, pd.DataFrame], Optional[object], dict]]
ModelFn = Union[SingleAssetModelFn, PortfolioModelFn]


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
    "mfi": add_mfi_features,
    "rsi": add_rsi_features,
    "stochastic": add_stochastic_features,
    "price_momentum": add_price_momentum_features,
    "return_momentum": add_return_momentum_features,
    "vol_normalized_momentum": add_vol_normalized_momentum_features,
    "session_context": add_session_context_features,
    "regime_context": add_regime_context_features,
    "macro_context": add_macro_context_features,
    "feature_transforms": add_feature_transforms,
}

SIGNAL_REGISTRY: Mapping[str, SignalFn] = {
    "trend_state": trend_state_signal,
    "probability_threshold": probabilistic_signal,
    "probability_conviction": conviction_sizing_signal,
    "probability_vol_adjusted": probability_vol_adjusted_signal,
    "forecast_threshold": forecast_threshold_signal,
    "forecast_vol_adjusted": forecast_vol_adjusted_signal,
    "rsi": rsi_strategy,
    "momentum": momentum_strategy,
    "stochastic": stochastic_strategy,
    "volatility_regime": volatility_regime_strategy,
}

SINGLE_ASSET_MODEL_REGISTRY: Mapping[str, SingleAssetModelFn] = {
    "lightgbm_clf": train_lightgbm_classifier,
    "logistic_regression_clf": train_logistic_regression_classifier,
    "xgboost_clf": train_xgboost_classifier,
    "sarimax_forecaster": train_sarimax_forecaster,
    "garch_forecaster": train_garch_forecaster,
    "lstm_forecaster": train_lstm_forecaster,
    "patchtst_forecaster": train_patchtst_forecaster,
    "tft_forecaster": train_tft_forecaster,
    "ppo_agent": train_ppo_agent,
    "dqn_agent": train_dqn_agent,
}

PORTFOLIO_MODEL_REGISTRY: Mapping[str, PortfolioModelFn] = {
    "ppo_portfolio_agent": train_ppo_portfolio_agent,
    "dqn_portfolio_agent": train_dqn_portfolio_agent,
}

MODEL_REGISTRY: Mapping[str, ModelFn] = {
    **SINGLE_ASSET_MODEL_REGISTRY,
    **PORTFOLIO_MODEL_REGISTRY,
}

RL_MODEL_KINDS = frozenset(
    {
        "ppo_agent",
        "dqn_agent",
        "ppo_portfolio_agent",
        "dqn_portfolio_agent",
    }
)
PORTFOLIO_MODEL_KINDS = frozenset(PORTFOLIO_MODEL_REGISTRY)


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
