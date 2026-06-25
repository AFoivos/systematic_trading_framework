from __future__ import annotations

"""
Backward-compatible facade for component registries.

Canonical registry ownership now lives in:
- src.features.registry
- src.signals.registry
- src.targets.registry
- src.models.registry
- src.pipelines.registry
"""

from src.features.registry import (
    FEATURE_COMPATIBILITY_REGISTRY,
    FEATURE_KINDS,
    FEATURE_REGISTRY,
    FeatureFn,
    get_feature_fn,
)
from src.models.registry import (
    MODEL_KINDS,
    MODEL_REGISTRY,
    PORTFOLIO_MODEL_KINDS,
    PORTFOLIO_MODEL_REGISTRY,
    RL_MODEL_KINDS,
    SINGLE_ASSET_MODEL_KINDS,
    SINGLE_ASSET_MODEL_REGISTRY,
    ModelFn,
    PortfolioModelFn,
    SingleAssetModelFn,
    get_model_fn,
    is_portfolio_model_kind,
    is_rl_model_kind,
)
from src.pipelines.registry import PIPELINE_KINDS, PIPELINE_REGISTRY, PipelineFn, get_pipeline_fn
from src.signals.registry import (
    DEPRECATED_SIGNAL_ALIASES,
    SIGNAL_KINDS,
    SIGNAL_REGISTRY,
    SignalFn,
    get_signal_fn,
)
from src.targets.registry import TARGET_KINDS, TARGET_REGISTRY, TargetBuilder, build_target, get_target_builder

__all__ = [
    "DEPRECATED_SIGNAL_ALIASES",
    "FEATURE_COMPATIBILITY_REGISTRY",
    "FEATURE_KINDS",
    "FEATURE_REGISTRY",
    "MODEL_KINDS",
    "MODEL_REGISTRY",
    "PIPELINE_KINDS",
    "PIPELINE_REGISTRY",
    "PORTFOLIO_MODEL_KINDS",
    "PORTFOLIO_MODEL_REGISTRY",
    "RL_MODEL_KINDS",
    "SIGNAL_KINDS",
    "SIGNAL_REGISTRY",
    "SINGLE_ASSET_MODEL_KINDS",
    "SINGLE_ASSET_MODEL_REGISTRY",
    "TARGET_KINDS",
    "TARGET_REGISTRY",
    "FeatureFn",
    "ModelFn",
    "PipelineFn",
    "PortfolioModelFn",
    "SignalFn",
    "SingleAssetModelFn",
    "TargetBuilder",
    "build_target",
    "get_feature_fn",
    "get_model_fn",
    "get_pipeline_fn",
    "get_signal_fn",
    "get_target_builder",
    "is_portfolio_model_kind",
    "is_rl_model_kind",
]
