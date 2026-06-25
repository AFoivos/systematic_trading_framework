from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import pandas as pd

from src.utils.registry import build_registry, get_registered_component, registry_names

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
)


TARGET_REGISTRY: Mapping[str, TargetBuilder] = build_registry("target", _TARGET_COMPONENTS)
TARGET_KINDS = registry_names(TARGET_REGISTRY)


def get_target_builder(name: str) -> TargetBuilder:
    return get_registered_component(TARGET_REGISTRY, name, category="target")


def build_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
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
