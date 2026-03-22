from __future__ import annotations

from importlib import import_module

"""Legacy compatibility package.

The actual experiment-side helpers now live under ``src.experiments.support`` and
model-side training logic lives under ``src.models``.
"""

from src.experiments.support.targets import (
    assign_quantile_labels,
    build_classifier_target,
    build_forward_return_target,
    build_triple_barrier_target,
)

_EXPORTS = {
    "infer_feature_columns": ("src.models.runtime", "infer_feature_columns"),
    "prepare_forecaster_inputs": ("src.models.forecasting", "prepare_forecaster_inputs"),
    "resolve_runtime_for_model": ("src.models.runtime", "resolve_runtime_for_model"),
    "train_forward_classifier": ("src.models.classification", "train_forward_classifier"),
    "train_forward_forecaster": ("src.models.forecasting", "train_forward_forecaster"),
    "train_garch_forecaster": ("src.models.forecasting", "train_garch_forecaster"),
    "train_lightgbm_classifier": ("src.models.classification", "train_lightgbm_classifier"),
    "train_lstm_forecaster": ("src.models.forecasting", "train_lstm_forecaster"),
    "train_logistic_regression_classifier": ("src.models.classification", "train_logistic_regression_classifier"),
    "train_patchtst_forecaster": ("src.models.forecasting", "train_patchtst_forecaster"),
    "train_sarimax_forecaster": ("src.models.forecasting", "train_sarimax_forecaster"),
    "train_tft_forecaster": ("src.models.forecasting", "train_tft_forecaster"),
    "train_xgboost_classifier": ("src.models.classification", "train_xgboost_classifier"),
}


def __getattr__(name: str):
    if name in _EXPORTS:
        module_name, attr_name = _EXPORTS[name]
        value = getattr(import_module(module_name), attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "assign_quantile_labels",
    "build_classifier_target",
    "build_forward_return_target",
    "build_triple_barrier_target",
    *list(_EXPORTS),
]
