from __future__ import annotations

"""Canonical target builders and label helpers."""

from .candidate_expected_r import CANDIDATE_EXPECTED_R_OUTPUT_COLS, build_candidate_expected_r_target
from .directional_triple_barrier import build_directional_triple_barrier_target
from .forward_return import build_forward_return_target
from .future_return_regression import build_future_return_regression_target
from .output_aliases import TARGET_OUTPUT_KEYS, apply_target_output_aliases
from .r_multiple import R_MULTIPLE_TARGET_OUTPUT_COLS, build_r_multiple_target
from .registry import TARGET_KINDS, TARGET_REGISTRY, build_target, get_target_builder
from .triple_barrier import build_triple_barrier_target
from .classifier import assign_quantile_labels, build_classifier_target

__all__ = [
    "R_MULTIPLE_TARGET_OUTPUT_COLS",
    "CANDIDATE_EXPECTED_R_OUTPUT_COLS",
    "TARGET_KINDS",
    "TARGET_OUTPUT_KEYS",
    "TARGET_REGISTRY",
    "apply_target_output_aliases",
    "assign_quantile_labels",
    "build_candidate_expected_r_target",
    "build_classifier_target",
    "build_directional_triple_barrier_target",
    "build_forward_return_target",
    "build_future_return_regression_target",
    "build_r_multiple_target",
    "build_target",
    "build_triple_barrier_target",
    "get_target_builder",
]
