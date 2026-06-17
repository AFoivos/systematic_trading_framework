from __future__ import annotations

"""Experiment-support utilities for targets, diagnostics, and evaluation metrics."""

from importlib import import_module
from typing import Any


_LAZY_ATTRS = {
    "aggregate_feature_importance": "src.experiments.support.diagnostics",
    "aggregate_label_distributions": "src.experiments.support.diagnostics",
    "extract_feature_importance": "src.experiments.support.diagnostics",
    "summarize_feature_availability": "src.experiments.support.diagnostics",
    "summarize_label_distribution": "src.experiments.support.diagnostics",
    "summarize_numeric_distribution": "src.experiments.support.diagnostics",
    "summarize_prediction_alignment": "src.experiments.support.diagnostics",
    "binary_classification_metrics": "src.experiments.support.metrics",
    "empty_classification_metrics": "src.experiments.support.metrics",
    "empty_regression_metrics": "src.experiments.support.metrics",
    "empty_volatility_metrics": "src.experiments.support.metrics",
    "forecast_to_probability": "src.experiments.support.metrics",
    "regression_metrics": "src.experiments.support.metrics",
    "volatility_metrics": "src.experiments.support.metrics",
    "R_MULTIPLE_TARGET_OUTPUT_COLS": "src.targets",
    "assign_quantile_labels": "src.targets",
    "build_classifier_target": "src.targets",
    "build_forward_return_target": "src.targets",
    "build_r_multiple_target": "src.targets",
    "build_triple_barrier_target": "src.targets",
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_ATTRS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_LAZY_ATTRS[name])
    value = getattr(module, name)
    globals()[name] = value
    return value


__all__ = [
    "R_MULTIPLE_TARGET_OUTPUT_COLS",
    "aggregate_feature_importance",
    "aggregate_label_distributions",
    "assign_quantile_labels",
    "binary_classification_metrics",
    "build_classifier_target",
    "build_forward_return_target",
    "build_r_multiple_target",
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
