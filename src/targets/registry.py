from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import pandas as pd

from src.utils.registry import build_registry, get_registered_component, registry_names

from .candidate_expected_r import build_candidate_expected_r_target
from .directional_triple_barrier import build_directional_triple_barrier_target
from .forward_return import build_forward_return_target
from .future_return_regression import build_future_return_regression_target
from .path_dependent_r import build_path_dependent_r_target
from .r_multiple import build_r_multiple_target
from .regression import (
    build_downside_adjusted_future_return_target,
    build_excess_return_regression_target,
    build_future_drawdown_regression_target,
    build_future_path_efficiency_target,
    build_future_range_regression_target,
    build_future_realized_volatility_target,
    build_future_trend_slope_target,
    build_mae_regression_target,
    build_mfe_mae_ratio_regression_target,
    build_mfe_regression_target,
    build_r_multiple_regression_target,
    build_residual_return_regression_target,
    build_risk_adjusted_future_return_target,
    build_volatility_normalized_future_return_target,
)
from .triple_barrier import build_triple_barrier_target

TargetBuilder = Callable[[pd.DataFrame, dict[str, Any] | None], tuple[pd.DataFrame, str, str, dict[str, Any]]]


_TARGET_COMPONENTS: tuple[tuple[str, TargetBuilder], ...] = (
    ("forward_return", build_forward_return_target),
    ("future_return_regression", build_future_return_regression_target),
    ("volatility_normalized_future_return", build_volatility_normalized_future_return_target),
    ("risk_adjusted_future_return", build_risk_adjusted_future_return_target),
    ("r_multiple_regression", build_r_multiple_regression_target),
    ("mfe_regression", build_mfe_regression_target),
    ("mae_regression", build_mae_regression_target),
    ("mfe_mae_ratio_regression", build_mfe_mae_ratio_regression_target),
    ("downside_adjusted_future_return", build_downside_adjusted_future_return_target),
    ("future_trend_slope", build_future_trend_slope_target),
    ("future_path_efficiency", build_future_path_efficiency_target),
    ("excess_return_regression", build_excess_return_regression_target),
    ("residual_return_regression", build_residual_return_regression_target),
    ("future_range_regression", build_future_range_regression_target),
    ("future_realized_volatility", build_future_realized_volatility_target),
    ("future_drawdown_regression", build_future_drawdown_regression_target),
    ("triple_barrier", build_triple_barrier_target),
    ("directional_triple_barrier", build_directional_triple_barrier_target),
    ("r_multiple", build_r_multiple_target),
    ("path_dependent_r", build_path_dependent_r_target),
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
