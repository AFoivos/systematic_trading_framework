from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.evaluation.model_metrics import (
    binary_classification_metrics,
    forecast_to_probability,
)
from src.models.artifacts import predict_with_model_bundle
from src.models.classification import train_logistic_regression_classifier
from src.models.classification.base import FittedClassifierPipeline
from src.models.forecasting.base import train_forward_forecaster


class _BinaryClassifier:
    classes_ = np.array([0, 1])

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        return (features.iloc[:, 0].to_numpy(dtype=float) >= 0.0).astype(int)

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        positive = np.where(features.iloc[:, 0].to_numpy(dtype=float) >= 0.0, 0.8, 0.2)
        return np.column_stack([1.0 - positive, positive])


class _Regressor:
    def predict(self, features: pd.DataFrame) -> np.ndarray:
        return features.iloc[:, 0].to_numpy(dtype=float)


class _RecordedForecaster:
    def __init__(self, train_positions: np.ndarray):
        self.train_positions = tuple(int(value) for value in train_positions)

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        return np.zeros(len(features), dtype=float)


def _recording_fold_predictor(
    full_df: pd.DataFrame,
    train_idx: np.ndarray,
    test_idx: np.ndarray,
    feature_cols: list[str],
    target_col: str,
    model_params: dict[str, object],
    runtime_meta: dict[str, object],
) -> tuple[pd.Series, dict[str, pd.Series], object, dict[str, object]]:
    del feature_cols, model_params, runtime_meta
    train_target = full_df.iloc[train_idx][target_col].dropna().astype(float)
    prediction = pd.Series(
        float(train_target.mean()),
        index=full_df.index[test_idx],
        dtype=float,
    )
    return (
        prediction,
        {},
        _RecordedForecaster(train_idx),
        {"model_train_rows": int(len(train_target))},
    )


def test_binary_metrics_align_series_by_index() -> None:
    index = pd.Index(["a", "b"])
    y_true = pd.Series([0, 1], index=index)
    pred_prob = pd.Series([0.9, 0.1], index=index[::-1])

    metrics = binary_classification_metrics(y_true, pred_prob)

    assert metrics["evaluation_rows"] == 2
    assert metrics["accuracy"] == pytest.approx(1.0)


def test_binary_metrics_reject_duplicate_indexes() -> None:
    y_true = pd.Series([0, 1], index=["a", "a"])
    pred_prob = pd.Series([0.1, 0.9], index=["a", "b"])

    with pytest.raises(ValueError, match="unique indexes"):
        binary_classification_metrics(y_true, pred_prob)


def test_forecast_probability_is_prefix_invariant_with_train_fitted_scale() -> None:
    prefix = pd.Series([1.0, 2.0], index=[0, 1])
    extended = pd.Series([1.0, 2.0, 100.0], index=[0, 1, 2])

    prefix_probability = forecast_to_probability(prefix, scale=2.5)
    extended_probability = forecast_to_probability(extended, scale=2.5)

    pd.testing.assert_series_equal(
        prefix_probability,
        extended_probability.iloc[:2],
        check_names=False,
    )
    with pytest.raises(ValueError, match="train-fitted scale"):
        forecast_to_probability(prefix, scale=None)


def test_classifier_artifact_never_writes_labels_as_predicted_returns() -> None:
    bundle = {
        "model": _BinaryClassifier(),
        "model_meta": {
            "model_kind": "binary_classifier",
            "task_type": "classification",
            "feature_cols": ["feature"],
            "pred_prob_col": "pred_prob",
            "pred_label_col": "pred_label",
        },
        "model_config": {},
    }

    out = predict_with_model_bundle(
        pd.DataFrame({"feature": [-1.0, 1.0]}),
        bundle,
    )

    assert "pred_ret" not in out.columns
    assert out["pred_label"].tolist() == [0, 1]
    assert out["pred_prob"].tolist() == pytest.approx([0.2, 0.8])


def test_regression_artifact_requires_persisted_probability_scale() -> None:
    bundle = {
        "model": _Regressor(),
        "model_meta": {
            "model_kind": "regressor",
            "task_type": "regression",
            "feature_cols": ["feature"],
        },
        "model_config": {},
    }

    with pytest.raises(ValueError, match="train-fitted scale"):
        predict_with_model_bundle(pd.DataFrame({"feature": [1.0, 2.0]}), bundle)


def test_forecaster_returns_final_refit_model_not_last_cv_fold() -> None:
    index = pd.date_range("2024-01-01", periods=40, freq="D")
    frame = pd.DataFrame(
        {
            "close": 100.0 + np.arange(40, dtype=float),
            "feature": np.linspace(-1.0, 1.0, 40),
        },
        index=index,
    )

    _, model, meta = train_forward_forecaster(
        frame,
        {
            "feature_cols": ["feature"],
            "target": {
                "kind": "future_return_regression",
                "price_col": "close",
                "horizon_bars": 2,
            },
            "split": {
                "method": "walk_forward",
                "train_size": 20,
                "test_size": 5,
                "step_size": 5,
                "expanding": True,
                "max_folds": 2,
            },
        },
        model_kind="recording_regressor",
        fold_predictor=_recording_fold_predictor,
        required_features=True,
        runtime_estimator_family="sklearn",
    )

    assert isinstance(model, _RecordedForecaster)
    assert model.train_positions[-1] == meta["final_refit"]["train_end_position"]
    assert model.train_positions[-1] > meta["folds"][-1]["effective_train_end"]
    assert meta["final_refit"]["enabled"]


def test_classifier_returns_serializable_final_refit_pipeline() -> None:
    index = pd.date_range("2024-01-01", periods=80, freq="h")
    frame = pd.DataFrame(
        {
            "close": 100.0 + np.sin(np.arange(80, dtype=float)) * 2.0,
            "feature": np.cos(np.arange(80, dtype=float)),
        },
        index=index,
    )

    _, model, meta = train_logistic_regression_classifier(
        frame,
        {
            "feature_cols": ["feature"],
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
            "split": {
                "method": "walk_forward",
                "train_size": 40,
                "test_size": 10,
                "step_size": 10,
                "max_folds": 2,
            },
            "preprocessing": {"scaler": "standard"},
        },
    )

    assert isinstance(model, FittedClassifierPipeline)
    assert meta["final_refit"]["enabled"]
    assert meta["final_refit"]["train_end_position"] > meta["folds"][-1]["effective_train_end"]
    probability = model.predict_proba(frame[["feature"]].iloc[-2:])
    assert probability.shape == (2, 2)
