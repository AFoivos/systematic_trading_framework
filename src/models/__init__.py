from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "ensure_lightgbm_runtime_available": ("src.models.common.runtime", "ensure_lightgbm_runtime_available"),
    "ensure_xgboost_runtime_available": ("src.models.common.runtime", "ensure_xgboost_runtime_available"),
    "GarchState": ("src.models.forecasting.garch", "GarchState"),
    "fit_garch11_state": ("src.models.forecasting.garch", "fit_garch11_state"),
    "infer_feature_columns": ("src.models.common.runtime", "infer_feature_columns"),
    "make_garch_fold_predictor": ("src.models.forecasting.garch", "make_garch_fold_predictor"),
    "LGBMBaselineConfig": ("src.models.forecasting.lightgbm_baseline", "LGBMBaselineConfig"),
    "default_feature_columns": ("src.models.forecasting.lightgbm_baseline", "default_feature_columns"),
    "predict_returns": ("src.models.forecasting.lightgbm_baseline", "predict_returns"),
    "prediction_to_signal": ("src.models.forecasting.lightgbm_baseline", "prediction_to_signal"),
    "prepare_forecaster_inputs": ("src.models.forecasting", "prepare_forecaster_inputs"),
    "probe_lightgbm_runtime": ("src.models.common.runtime", "probe_lightgbm_runtime"),
    "probe_xgboost_runtime": ("src.models.common.runtime", "probe_xgboost_runtime"),
    "resolve_feature_selectors": ("src.models.common.runtime", "resolve_feature_selectors"),
    "resolve_garch_overlay": ("src.models.common.overlay", "resolve_garch_overlay"),
    "resolve_runtime_for_model": ("src.models.common.runtime", "resolve_runtime_for_model"),
    "train_forward_classifier": ("src.models.classification", "train_forward_classifier"),
    "train_event_transformer_encoder": (
        "src.models.classification.event_transformer",
        "train_event_transformer_encoder",
    ),
    "train_elastic_net_classifier": (
        "src.models.classification.elastic_net",
        "train_elastic_net_classifier",
    ),
    "train_forward_forecaster": ("src.models.forecasting", "train_forward_forecaster"),
    "train_garch_forecaster": ("src.models.forecasting", "train_garch_forecaster"),
    "train_lightgbm_classifier": ("src.models.classification.lightgbm", "train_lightgbm_classifier"),
    "train_logistic_regression_classifier": (
        "src.models.classification.logistic_regression",
        "train_logistic_regression_classifier",
    ),
    "train_lstm_forecaster": ("src.models.forecasting", "train_lstm_forecaster"),
    "train_patchtst_forecaster": ("src.models.forecasting", "train_patchtst_forecaster"),
    "train_sarimax_forecaster": ("src.models.forecasting", "train_sarimax_forecaster"),
    "train_tft_forecaster": ("src.models.forecasting", "train_tft_forecaster"),
    "train_regressor": ("src.models.forecasting.lightgbm_baseline", "train_regressor"),
    "train_test_split_time": ("src.models.forecasting.lightgbm_baseline", "train_test_split_time"),
    "train_xgboost_classifier": ("src.models.classification.xgboost", "train_xgboost_classifier"),
    "train_sarimax_fold": ("src.models.forecasting.sarimax", "train_sarimax_fold"),
    "make_lstm_fold_predictor": ("src.models.forecasting.lstm", "make_lstm_fold_predictor"),
    "make_patchtst_fold_predictor": ("src.models.forecasting.patchtst", "make_patchtst_fold_predictor"),
    "SequenceScaler": ("src.models.forecasting.sequence", "SequenceScaler"),
    "SequenceSamples": ("src.models.forecasting.sequence", "SequenceSamples"),
    "build_sequence_samples": ("src.models.forecasting.sequence", "build_sequence_samples"),
    "fit_sequence_scaler": ("src.models.forecasting.sequence", "fit_sequence_scaler"),
    "resolve_event_embedding_columns": (
        "src.models.classification.event_transformer",
        "resolve_event_embedding_columns",
    ),
    "make_tft_fold_predictor": ("src.models.forecasting.tft", "make_tft_fold_predictor"),
}


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


__all__ = list(_EXPORTS)
