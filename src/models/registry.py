from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Optional, Union

import pandas as pd

from src.utils.registry import build_registry, get_registered_component, lazy_callable, registry_names

SingleAssetModelFn = Callable[..., tuple[pd.DataFrame, Optional[object], dict]]
PortfolioModelFn = Callable[..., tuple[dict[str, pd.DataFrame], Optional[object], dict]]
ModelFn = Union[SingleAssetModelFn, PortfolioModelFn]


_SINGLE_ASSET_MODEL_COMPONENTS: tuple[tuple[str, SingleAssetModelFn], ...] = (
    ("elastic_net_clf", lazy_callable("src.models.classification.elastic_net", "train_elastic_net_classifier")),
    ("lightgbm_clf", lazy_callable("src.models.classification.lightgbm", "train_lightgbm_classifier")),
    ("lightgbm_regressor", lazy_callable("src.models.forecasting.base", "train_lightgbm_regressor")),
    ("logistic_regression_clf", lazy_callable("src.models.classification.logistic_regression", "train_logistic_regression_classifier")),
    ("xgboost_clf", lazy_callable("src.models.classification.xgboost", "train_xgboost_classifier")),
    ("event_transformer_encoder", lazy_callable("src.models.classification.event_transformer", "train_event_transformer_encoder")),
    ("sarimax_forecaster", lazy_callable("src.models.forecasting.base", "train_sarimax_forecaster")),
    ("garch_forecaster", lazy_callable("src.models.forecasting.base", "train_garch_forecaster")),
    ("lstm_forecaster", lazy_callable("src.models.forecasting.base", "train_lstm_forecaster")),
    ("patchtst_forecaster", lazy_callable("src.models.forecasting.base", "train_patchtst_forecaster")),
    ("tft_forecaster", lazy_callable("src.models.forecasting.base", "train_tft_forecaster")),
    ("tsfresh_extrema_feature_discovery", lazy_callable("src.experiments.support.tsfresh_extrema_feature_discovery", "train_tsfresh_extrema_feature_discovery")),
    ("ppo_agent", lazy_callable("src.models.rl.single_asset", "train_ppo_agent")),
    ("dqn_agent", lazy_callable("src.models.rl.single_asset", "train_dqn_agent")),
)

_PORTFOLIO_MODEL_COMPONENTS: tuple[tuple[str, PortfolioModelFn], ...] = (
    ("ppo_portfolio_agent", lazy_callable("src.models.rl.portfolio", "train_ppo_portfolio_agent")),
    ("dqn_portfolio_agent", lazy_callable("src.models.rl.portfolio", "train_dqn_portfolio_agent")),
)


SINGLE_ASSET_MODEL_REGISTRY: Mapping[str, SingleAssetModelFn] = build_registry(
    "single-asset model",
    _SINGLE_ASSET_MODEL_COMPONENTS,
)
PORTFOLIO_MODEL_REGISTRY: Mapping[str, PortfolioModelFn] = build_registry(
    "portfolio model",
    _PORTFOLIO_MODEL_COMPONENTS,
)
MODEL_REGISTRY: Mapping[str, ModelFn] = build_registry(
    "model",
    (
        *SINGLE_ASSET_MODEL_REGISTRY.items(),
        *PORTFOLIO_MODEL_REGISTRY.items(),
    ),
)

SINGLE_ASSET_MODEL_KINDS = registry_names(SINGLE_ASSET_MODEL_REGISTRY)
PORTFOLIO_MODEL_KINDS = registry_names(PORTFOLIO_MODEL_REGISTRY)
MODEL_KINDS = registry_names(MODEL_REGISTRY)
RL_MODEL_KINDS = frozenset({"dqn_agent", "dqn_portfolio_agent", "ppo_agent", "ppo_portfolio_agent"})


def get_model_fn(name: str) -> ModelFn:
    return get_registered_component(MODEL_REGISTRY, name, category="model")


def is_portfolio_model_kind(name: str) -> bool:
    return str(name) in PORTFOLIO_MODEL_REGISTRY


def is_rl_model_kind(name: str) -> bool:
    return str(name) in RL_MODEL_KINDS


__all__ = [
    "MODEL_KINDS",
    "MODEL_REGISTRY",
    "ModelFn",
    "PORTFOLIO_MODEL_KINDS",
    "PORTFOLIO_MODEL_REGISTRY",
    "PortfolioModelFn",
    "RL_MODEL_KINDS",
    "SINGLE_ASSET_MODEL_KINDS",
    "SINGLE_ASSET_MODEL_REGISTRY",
    "SingleAssetModelFn",
    "get_model_fn",
    "is_portfolio_model_kind",
    "is_rl_model_kind",
]
