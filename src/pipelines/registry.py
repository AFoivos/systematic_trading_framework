from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from src.utils.registry import build_registry, get_registered_component, registry_names

from .canonical_pipeline import run_canonical_pipeline
from src.experiments.support.btcusd_dual_trend_ftmo import run_pipeline as run_btcusd_dual_trend_ftmo_v1_pipeline
from src.experiments.support.eurusd_ftmo_ml_v2 import run_reconstruction as run_eurusd_ftmo_ml_v2_pipeline

PipelineFn = Callable[[str | Path], Any]
PipelineConfigValidator = Callable[[dict[str, Any]], None]


_PIPELINE_COMPONENTS: tuple[tuple[str, PipelineFn], ...] = (
    ("canonical_experiment", run_canonical_pipeline),
    ("btcusd_dual_trend_ftmo_v1", run_btcusd_dual_trend_ftmo_v1_pipeline),
    ("eurusd_ftmo_ml_v2", run_eurusd_ftmo_ml_v2_pipeline),
)


def _validate_btcusd_dual_trend_ftmo_v1_config(cfg: dict[str, Any]) -> None:
    from src.experiments.support.btcusd_dual_trend_ftmo import _validate_locked_config

    _validate_locked_config(cfg)


def _validate_eurusd_ftmo_ml_v2_config(cfg: dict[str, Any]) -> None:
    from src.experiments.support.eurusd_ftmo_ml_v2 import _validate_locked_config

    _validate_locked_config(cfg)


_PIPELINE_CONFIG_VALIDATOR_COMPONENTS: tuple[tuple[str, PipelineConfigValidator], ...] = (
    ("btcusd_dual_trend_ftmo_v1", _validate_btcusd_dual_trend_ftmo_v1_config),
    ("eurusd_ftmo_ml_v2", _validate_eurusd_ftmo_ml_v2_config),
)


PIPELINE_REGISTRY: Mapping[str, PipelineFn] = build_registry("pipeline", _PIPELINE_COMPONENTS)
PIPELINE_CONFIG_VALIDATOR_REGISTRY: Mapping[str, PipelineConfigValidator] = build_registry(
    "custom pipeline config validator",
    _PIPELINE_CONFIG_VALIDATOR_COMPONENTS,
)
PIPELINE_KINDS = registry_names(PIPELINE_REGISTRY)


def get_pipeline_fn(name: str) -> PipelineFn:
    return get_registered_component(PIPELINE_REGISTRY, name, category="pipeline")


def validate_custom_pipeline_config(name: str, cfg: dict[str, Any]) -> None:
    validator = get_registered_component(
        PIPELINE_CONFIG_VALIDATOR_REGISTRY,
        name,
        category="custom pipeline config validator",
    )
    validator(cfg)


__all__ = [
    "PIPELINE_KINDS",
    "PIPELINE_CONFIG_VALIDATOR_REGISTRY",
    "PIPELINE_REGISTRY",
    "PipelineConfigValidator",
    "PipelineFn",
    "get_pipeline_fn",
    "validate_custom_pipeline_config",
]
