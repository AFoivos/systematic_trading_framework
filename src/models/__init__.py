from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "GarchState": ("src.models.garch", "GarchState"),
    "fit_garch11_state": ("src.models.garch", "fit_garch11_state"),
    "make_garch_fold_predictor": ("src.models.garch", "make_garch_fold_predictor"),
    "LGBMBaselineConfig": ("src.models.lightgbm_baseline", "LGBMBaselineConfig"),
    "default_feature_columns": ("src.models.lightgbm_baseline", "default_feature_columns"),
    "predict_returns": ("src.models.lightgbm_baseline", "predict_returns"),
    "prediction_to_signal": ("src.models.lightgbm_baseline", "prediction_to_signal"),
    "train_regressor": ("src.models.lightgbm_baseline", "train_regressor"),
    "train_test_split_time": ("src.models.lightgbm_baseline", "train_test_split_time"),
    "train_sarimax_fold": ("src.models.sarimax", "train_sarimax_fold"),
    "make_tft_fold_predictor": ("src.models.tft", "make_tft_fold_predictor"),
}


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


__all__ = list(_EXPORTS)
