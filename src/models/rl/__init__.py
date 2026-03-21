from __future__ import annotations

from typing import Any

from .envs import PortfolioTradingEnv, RLRewardConfig, SingleAssetTradingEnv


def build_policy_kwargs(*args: Any, **kwargs: Any):
    from .sb3 import build_policy_kwargs as _build_policy_kwargs

    return _build_policy_kwargs(*args, **kwargs)


def make_vec_env(*args: Any, **kwargs: Any):
    from .sb3 import make_vec_env as _make_vec_env

    return _make_vec_env(*args, **kwargs)


def train_sb3_model(*args: Any, **kwargs: Any):
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
    "train_sb3_model",
]
