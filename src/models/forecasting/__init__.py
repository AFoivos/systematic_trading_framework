from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "GarchState": ("src.models.forecasting.garch", "GarchState"),
    "LGBMBaselineConfig": ("src.models.forecasting.lightgbm_baseline", "LGBMBaselineConfig"),
    "SequenceSamples": ("src.models.forecasting.sequence", "SequenceSamples"),
    "SequenceScaler": ("src.models.forecasting.sequence", "SequenceScaler"),
    "build_sequence_samples": ("src.models.forecasting.sequence", "build_sequence_samples"),
    "default_feature_columns": ("src.models.forecasting.lightgbm_baseline", "default_feature_columns"),
    "fit_garch11_state": ("src.models.forecasting.garch", "fit_garch11_state"),
    "fit_sequence_scaler": ("src.models.forecasting.sequence", "fit_sequence_scaler"),
    "make_garch_fold_predictor": ("src.models.forecasting.garch", "make_garch_fold_predictor"),
    "make_lstm_fold_predictor": ("src.models.forecasting.lstm", "make_lstm_fold_predictor"),
    "make_patchtst_fold_predictor": ("src.models.forecasting.patchtst", "make_patchtst_fold_predictor"),
    "make_tft_fold_predictor": ("src.models.forecasting.tft", "make_tft_fold_predictor"),
    "prepare_forecaster_inputs": ("src.models.forecasting.base", "prepare_forecaster_inputs"),
    "predict_returns": ("src.models.forecasting.lightgbm_baseline", "predict_returns"),
    "prediction_to_signal": ("src.models.forecasting.lightgbm_baseline", "prediction_to_signal"),
    "train_forward_forecaster": ("src.models.forecasting.base", "train_forward_forecaster"),
    "train_garch_forecaster": ("src.models.forecasting.base", "train_garch_forecaster"),
    "train_lstm_forecaster": ("src.models.forecasting.base", "train_lstm_forecaster"),
    "train_patchtst_forecaster": ("src.models.forecasting.base", "train_patchtst_forecaster"),
    "train_regressor": ("src.models.forecasting.lightgbm_baseline", "train_regressor"),
    "train_sarimax_fold": ("src.models.forecasting.sarimax", "train_sarimax_fold"),
    "train_sarimax_forecaster": ("src.models.forecasting.base", "train_sarimax_forecaster"),
    "train_test_split_time": ("src.models.forecasting.lightgbm_baseline", "train_test_split_time"),
    "train_tft_forecaster": ("src.models.forecasting.base", "train_tft_forecaster"),
}


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


__all__ = list(_EXPORTS)
