from __future__ import annotations

from typing import Callable, Mapping, Optional, Union

import pandas as pd

from src.features import add_close_returns, add_lagged_features, add_volatility_features
from src.features.technical.indicators import add_indicator_features
from src.features.technical.momentum import add_momentum_features
from src.features.technical.oscillators import add_oscillator_features
from src.features.technical.trend import add_trend_features, add_trend_regime_features
from src.backtesting.strategies import probabilistic_signal, trend_state_signal
from src.experiments.models import train_lightgbm_classifier

FeatureFn = Callable[..., pd.DataFrame]
SignalFn = Callable[..., Union[pd.DataFrame, pd.Series]]
ModelFn = Callable[..., tuple[pd.DataFrame, Optional[object], dict]]


FEATURE_REGISTRY: Mapping[str, FeatureFn] = {
    "returns": add_close_returns,
    "volatility": add_volatility_features,
    "trend": add_trend_features,
    "trend_regime": add_trend_regime_features,
    "oscillators": add_oscillator_features,
    "lags": add_lagged_features,
    "momentum": add_momentum_features,
    "indicators": add_indicator_features,
}

SIGNAL_REGISTRY: Mapping[str, SignalFn] = {
    "trend_state": trend_state_signal,
    "probability_threshold": probabilistic_signal,
}

MODEL_REGISTRY: Mapping[str, ModelFn] = {
    "lightgbm_clf": train_lightgbm_classifier,
}


def get_feature_fn(name: str) -> FeatureFn:
    if name not in FEATURE_REGISTRY:
        raise KeyError(f"Unknown feature step: {name}")
    return FEATURE_REGISTRY[name]


def get_signal_fn(name: str) -> SignalFn:
    if name not in SIGNAL_REGISTRY:
        raise KeyError(f"Unknown signal kind: {name}")
    return SIGNAL_REGISTRY[name]


def get_model_fn(name: str) -> ModelFn:
    if name not in MODEL_REGISTRY:
        raise KeyError(f"Unknown model kind: {name}")
    return MODEL_REGISTRY[name]
