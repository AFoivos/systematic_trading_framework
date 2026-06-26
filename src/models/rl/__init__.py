from __future__ import annotations

from typing import Any

from .envs import PortfolioTradingEnv, RLRewardConfig, SingleAssetTradingEnv
from .portfolio import train_dqn_portfolio_agent, train_ppo_portfolio_agent
from .single_asset import train_dqn_agent, train_ppo_agent


def build_policy_kwargs(*args: Any, **kwargs: Any):
    """
    Apply the registered ``build_policy_kwargs`` RL model transformation.
    
    This RL model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        model:
          kind: build_policy_kwargs
          params:
            # no configurable parameters
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    None:
        This callable has no public configuration parameters.
    """
    from .sb3 import build_policy_kwargs as _build_policy_kwargs

    return _build_policy_kwargs(*args, **kwargs)


def make_vec_env(*args: Any, **kwargs: Any):
    """
    Apply the registered ``make_vec_env`` RL model transformation.
    
    This RL model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        model:
          kind: make_vec_env
          params:
            # no configurable parameters
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    None:
        This callable has no public configuration parameters.
    """
    from .sb3 import make_vec_env as _make_vec_env

    return _make_vec_env(*args, **kwargs)


def train_sb3_model(*args: Any, **kwargs: Any):
    """
    Apply the registered ``sb3_model`` RL model transformation.
    
    This RL model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        model:
          kind: sb3_model
          params:
            # no configurable parameters
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    None:
        This callable has no public configuration parameters.
    """
    from .sb3 import train_sb3_model as _train_sb3_model

    return _train_sb3_model(*args, **kwargs)


def __getattr__(name: str):
    if name == "SequenceFeatureExtractor":
        from .extractors import SequenceFeatureExtractor

        return SequenceFeatureExtractor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "PortfolioTradingEnv",
    "RLRewardConfig",
    "SequenceFeatureExtractor",
    "SingleAssetTradingEnv",
    "build_policy_kwargs",
    "make_vec_env",
    "train_dqn_agent",
    "train_dqn_portfolio_agent",
    "train_ppo_agent",
    "train_ppo_portfolio_agent",
    "train_sb3_model",
]
