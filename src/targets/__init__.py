from __future__ import annotations

"""Canonical target builders and label helpers."""

from .classifier import assign_quantile_labels, build_classifier_target
from .directional_triple_barrier import build_directional_triple_barrier_target
from .forward_return import build_forward_return_target
from .output_aliases import TARGET_OUTPUT_KEYS, apply_target_output_aliases
from .r_multiple import R_MULTIPLE_TARGET_OUTPUT_COLS, build_r_multiple_target
from .triple_barrier import build_triple_barrier_target

__all__ = [
    "R_MULTIPLE_TARGET_OUTPUT_COLS",
    "TARGET_OUTPUT_KEYS",
    "apply_target_output_aliases",
    "assign_quantile_labels",
    "build_classifier_target",
    "build_directional_triple_barrier_target",
    "build_forward_return_target",
    "build_r_multiple_target",
    "build_triple_barrier_target",
]
