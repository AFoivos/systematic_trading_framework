from __future__ import annotations

"""Experiment-support utilities for targets, diagnostics, and evaluation metrics."""

from .diagnostics import (
    aggregate_feature_importance,
    aggregate_label_distributions,
    extract_feature_importance,
    summarize_feature_availability,
    summarize_label_distribution,
    summarize_numeric_distribution,
    summarize_prediction_alignment,
)
from .metrics import (
    binary_classification_metrics,
    empty_classification_metrics,
    empty_regression_metrics,
    empty_volatility_metrics,
    forecast_to_probability,
    regression_metrics,
    volatility_metrics,
)
from .targets import (
    assign_quantile_labels,
    build_classifier_target,
    build_forward_return_target,
    build_triple_barrier_target,
)

__all__ = [
    "aggregate_feature_importance",
    "aggregate_label_distributions",
    "assign_quantile_labels",
    "binary_classification_metrics",
    "build_classifier_target",
    "build_forward_return_target",
    "build_triple_barrier_target",
    "empty_classification_metrics",
    "empty_regression_metrics",
    "empty_volatility_metrics",
    "extract_feature_importance",
    "forecast_to_probability",
    "regression_metrics",
    "summarize_feature_availability",
    "summarize_label_distribution",
    "summarize_numeric_distribution",
    "summarize_prediction_alignment",
    "volatility_metrics",
]
