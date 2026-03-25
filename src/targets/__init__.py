from __future__ import annotations

"""Canonical target builders and label helpers."""

from .classifier import assign_quantile_labels, build_classifier_target
from .forward_return import build_forward_return_target
from .triple_barrier import build_triple_barrier_target

__all__ = [
    "assign_quantile_labels",
    "build_classifier_target",
    "build_forward_return_target",
    "build_triple_barrier_target",
]
