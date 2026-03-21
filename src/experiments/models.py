from __future__ import annotations

from src.experiments.modeling import (
    infer_feature_columns,
    train_garch_forecaster,
    train_lightgbm_classifier,
    train_logistic_regression_classifier,
    train_sarimax_forecaster,
    train_tft_forecaster,
)


def train_ppo_agent(*args, **kwargs):
    from src.experiments.modeling.rl import train_ppo_agent as _train_ppo_agent

    return _train_ppo_agent(*args, **kwargs)


def train_dqn_agent(*args, **kwargs):
    from src.experiments.modeling.rl import train_dqn_agent as _train_dqn_agent

    return _train_dqn_agent(*args, **kwargs)


def train_ppo_portfolio_agent(*args, **kwargs):
    from src.experiments.modeling.rl import train_ppo_portfolio_agent as _train_ppo_portfolio_agent

    return _train_ppo_portfolio_agent(*args, **kwargs)


def train_dqn_portfolio_agent(*args, **kwargs):
    from src.experiments.modeling.rl import train_dqn_portfolio_agent as _train_dqn_portfolio_agent

    return _train_dqn_portfolio_agent(*args, **kwargs)

__all__ = [
    "train_dqn_agent",
    "train_dqn_portfolio_agent",
    "infer_feature_columns",
    "train_garch_forecaster",
    "train_lightgbm_classifier",
    "train_logistic_regression_classifier",
    "train_ppo_agent",
    "train_ppo_portfolio_agent",
    "train_sarimax_forecaster",
    "train_tft_forecaster",
]
