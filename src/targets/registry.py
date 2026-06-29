from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import pandas as pd

from src.utils.registry import build_registry, get_registered_component, registry_names

from .candidate_expected_r import build_candidate_expected_r_target
from .directional_triple_barrier import build_directional_triple_barrier_target
from .forward_return import build_forward_return_target
from .future_return_regression import build_future_return_regression_target
from .r_multiple import build_r_multiple_target
from .triple_barrier import build_triple_barrier_target

TargetBuilder = Callable[[pd.DataFrame, dict[str, Any] | None], tuple[pd.DataFrame, str, str, dict[str, Any]]]


_TARGET_COMPONENTS: tuple[tuple[str, TargetBuilder], ...] = (
    ("forward_return", build_forward_return_target),
    ("future_return_regression", build_future_return_regression_target),
    ("triple_barrier", build_triple_barrier_target),
    ("directional_triple_barrier", build_directional_triple_barrier_target),
    ("r_multiple", build_r_multiple_target),
    ("candidate_expected_r", build_candidate_expected_r_target),
)


TARGET_REGISTRY: Mapping[str, TargetBuilder] = build_registry("target", _TARGET_COMPONENTS)
TARGET_KINDS = registry_names(TARGET_REGISTRY)


def get_target_builder(name: str) -> TargetBuilder:
    """
    Apply the registered ``get_target_builder`` target transformation.
    
    This target uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        target:
          kind: get_target_builder
          params:
            name: <required>
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    name:
        Configuration parameter accepted by this target.
    """
    return get_registered_component(TARGET_REGISTRY, name, category="target")


def build_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Apply the registered ``target`` target transformation.
    
    This target uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        target:
          kind: target
          params:
            kind: <configured>
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    kind:
        Configuration parameter accepted by this target. Default: ``<configured>``.
    """
    cfg = dict(target_cfg or {})
    kind = str(cfg.get("kind", "forward_return"))
    builder = get_target_builder(kind)
    return builder(df, cfg)


__all__ = [
    "TARGET_KINDS",
    "TARGET_REGISTRY",
    "TargetBuilder",
    "build_target",
    "get_target_builder",
]
