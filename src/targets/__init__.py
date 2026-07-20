from __future__ import annotations

"""Canonical target builders and label helpers."""

from .candidate_expected_r import CANDIDATE_EXPECTED_R_OUTPUT_COLS, build_candidate_expected_r_target
from .directional_triple_barrier import build_directional_triple_barrier_target
from .forward_return import build_forward_return_target
from .future_return_regression import build_future_return_regression_target
from .output_aliases import TARGET_OUTPUT_KEYS, apply_target_output_aliases
from .path_dependent_r import PATH_DEPENDENT_R_OUTPUT_COLS, build_path_dependent_r_target
from .r_multiple import R_MULTIPLE_TARGET_OUTPUT_COLS, build_r_multiple_target
from .strategy_path_r import STRATEGY_PATH_R_OUTPUT_COLS, build_strategy_path_r_target
from .regression import (
    REGRESSION_TARGET_KINDS,
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
from .registry import TARGET_KINDS, TARGET_REGISTRY, build_target, get_target_builder
from .triple_barrier import build_triple_barrier_target
from .trade_evaluation import (
    TRADE_EVALUATION_REGRESSION_TARGET_KINDS,
    TRADE_EVALUATION_TARGET_KINDS,
    build_expected_realized_r_target,
    build_target_before_stop_probability_target,
    build_trade_mfe_mae_regression_target,
)
from .classifier import assign_quantile_labels, build_classifier_target

__all__ = [
    "R_MULTIPLE_TARGET_OUTPUT_COLS",
    "CANDIDATE_EXPECTED_R_OUTPUT_COLS",
    "PATH_DEPENDENT_R_OUTPUT_COLS",
    "REGRESSION_TARGET_KINDS",
    "STRATEGY_PATH_R_OUTPUT_COLS",
    "TARGET_KINDS",
    "TARGET_OUTPUT_KEYS",
    "TARGET_REGISTRY",
    "TRADE_EVALUATION_REGRESSION_TARGET_KINDS",
    "TRADE_EVALUATION_TARGET_KINDS",
    "apply_target_output_aliases",
    "assign_quantile_labels",
    "build_candidate_expected_r_target",
    "build_classifier_target",
    "build_directional_triple_barrier_target",
    "build_downside_adjusted_future_return_target",
    "build_excess_return_regression_target",
    "build_expected_realized_r_target",
    "build_forward_return_target",
    "build_future_drawdown_regression_target",
    "build_future_path_efficiency_target",
    "build_future_range_regression_target",
    "build_future_realized_volatility_target",
    "build_future_return_regression_target",
    "build_future_trend_slope_target",
    "build_path_dependent_r_target",
    "build_mae_regression_target",
    "build_mfe_mae_ratio_regression_target",
    "build_mfe_regression_target",
    "build_r_multiple_regression_target",
    "build_residual_return_regression_target",
    "build_risk_adjusted_future_return_target",
    "build_r_multiple_target",
    "build_strategy_path_r_target",
    "build_target",
    "build_triple_barrier_target",
    "build_target_before_stop_probability_target",
    "build_trade_mfe_mae_regression_target",
    "build_volatility_normalized_future_return_target",
    "get_target_builder",
]
