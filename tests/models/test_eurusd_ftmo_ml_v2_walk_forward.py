from __future__ import annotations

import numpy as np
import pandas as pd
import joblib

from src.evaluation.eurusd_ftmo_ml_v2_walk_forward import annual_walk_forward
from src.models.classification.eurusd_ftmo_meta_ensemble import forward_inference
from src.utils.eurusd_ftmo_ml_v2_contract import COMMON_MODEL_PARAMS, FEATURE_COLUMNS, MODEL_NUM_LEAVES


class _DummyEnsemble:
    @classmethod
    def fit(cls, features: pd.DataFrame, target: pd.Series) -> "_DummyEnsemble":
        assert list(features.columns) == list(FEATURE_COLUMNS)
        return cls()

    def predict(self, features: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "pred_model_3": 0.61,
                "pred_model_7": 0.62,
                "pred_model_15": 0.63,
                "pred_score": 0.62,
            },
            index=features.index,
        )


class _DummyModel:
    def __init__(self, probability: float) -> None:
        self.probability = probability

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        positive = np.full(len(features), self.probability)
        return np.column_stack([1.0 - positive, positive])


def test_exact_model_parameters_are_frozen() -> None:
    assert MODEL_NUM_LEAVES == (3, 7, 15)
    assert COMMON_MODEL_PARAMS["n_estimators"] == 250
    assert COMMON_MODEL_PARAMS["random_state"] == 42
    assert COMMON_MODEL_PARAMS["class_weight"] is None


def test_walk_forward_refits_annually_then_freezes_holdout(monkeypatch) -> None:
    monkeypatch.setattr("src.evaluation.eurusd_ftmo_ml_v2_walk_forward.MetaEnsemble", _DummyEnsemble)
    dates = pd.to_datetime(
        ["2021-01-01", "2021-06-01", "2022-06-01", "2023-06-01", "2024-06-01", "2025-06-01", "2026-02-01"]
    )
    frame = pd.DataFrame(np.zeros((len(dates), len(FEATURE_COLUMNS))), columns=FEATURE_COLUMNS)
    frame.insert(0, "target_positive_net", [0, 1, 0, 1, 0, 1, 0])
    frame.insert(0, "signal_timestamp", dates)
    frame.insert(0, "candidate_id", [f"c{i}" for i in range(len(dates))])
    result = annual_walk_forward(frame)
    scored = result.predictions[result.predictions["signal_timestamp"] >= "2022-01-01"]
    assert scored["pred_is_oos"].all()
    manifests = {row["fold"]: row for row in result.fold_manifest}
    assert manifests["2022"]["train_cutoff_exclusive"].startswith("2022-01-01")
    assert manifests["2025_holdout"]["score_rows"] == 2
    holdout = scored[scored["signal_timestamp"] >= "2025-01-01"]
    assert holdout["model_train_end"].nunique() == 1


def test_forward_inference_validates_and_averages_versioned_bundle(tmp_path) -> None:
    bundle = tmp_path / "bundle.joblib"
    joblib.dump(
        {
            "feature_columns": list(FEATURE_COLUMNS),
            "models": {"model_3": _DummyModel(0.6), "model_7": _DummyModel(0.7), "model_15": _DummyModel(0.8)},
            "manifest": {"purpose": "paper_forward"},
        },
        bundle,
    )
    features = pd.DataFrame(np.zeros((2, len(FEATURE_COLUMNS))), columns=FEATURE_COLUMNS)
    scored = forward_inference(features, bundle)
    assert np.allclose(scored["pred_score"], 0.7)
