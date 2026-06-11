from __future__ import annotations

from src.models.classification import (
    train_elastic_net_classifier,
    train_event_transformer_encoder,
    train_lightgbm_classifier,
    train_logistic_regression_classifier,
    train_xgboost_classifier,
)
from src.models.common.runtime import infer_feature_columns, resolve_feature_selectors
from src.models.forecasting import (
    train_garch_forecaster,
    train_lightgbm_regressor,
    train_lstm_forecaster,
    train_patchtst_forecaster,
    train_sarimax_forecaster,
    train_tft_forecaster,
)
from src.models.rl import (
    train_dqn_agent,
    train_dqn_portfolio_agent,
    train_ppo_agent,
    train_ppo_portfolio_agent,
)
from src.experiments.support.tsfresh_extrema_feature_discovery import (
    train_tsfresh_extrema_feature_discovery,
)

__all__ = [
    "train_dqn_agent",
    "train_dqn_portfolio_agent",
    "infer_feature_columns",
    "resolve_feature_selectors",
    "train_elastic_net_classifier",
    "train_event_transformer_encoder",
    "train_garch_forecaster",
    "train_lightgbm_classifier",
    "train_lightgbm_regressor",
    "train_lstm_forecaster",
    "train_logistic_regression_classifier",
    "train_patchtst_forecaster",
    "train_ppo_agent",
    "train_ppo_portfolio_agent",
    "train_sarimax_forecaster",
    "train_tsfresh_extrema_feature_discovery",
    "train_tft_forecaster",
    "train_xgboost_classifier",
]
