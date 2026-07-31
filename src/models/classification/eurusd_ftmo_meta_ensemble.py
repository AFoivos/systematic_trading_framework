from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from src.features.eurusd_ftmo_ml_v2_contract import feature_schema_hash, validate_model_matrix
from src.utils.eurusd_ftmo_ml_v2_contract import (
    COMMON_MODEL_PARAMS,
    FEATURE_COLUMNS,
    MODEL_NUM_LEAVES,
    STRATEGY_NAME,
    STRATEGY_VERSION,
)


def _lightgbm_classifier() -> type[Any]:
    try:
        from lightgbm import LGBMClassifier
    except ImportError as exc:  # pragma: no cover - depends on optional runtime
        raise ImportError("lightgbm is required for EURUSD FTMO ML v2 training.") from exc
    return LGBMClassifier


@dataclass
class MetaEnsemble:
    models: dict[int, Any]

    @classmethod
    def fit(cls, features: pd.DataFrame, target: pd.Series) -> "MetaEnsemble":
        validate_model_matrix(features)
        labels = pd.to_numeric(target, errors="coerce")
        valid = labels.notna()
        x = features.loc[valid, list(FEATURE_COLUMNS)]
        y = labels.loc[valid].astype(int)
        if x.empty:
            raise ValueError("Cannot fit the ensemble without labeled candidates.")
        if sorted(y.unique().tolist()) != [0, 1]:
            raise ValueError("Each training fold must contain both binary target classes.")
        classifier = _lightgbm_classifier()
        models: dict[int, Any] = {}
        for leaves in MODEL_NUM_LEAVES:
            params = {**COMMON_MODEL_PARAMS, "num_leaves": leaves}
            model = classifier(**params)
            model.fit(x, y)
            models[leaves] = model
        return cls(models=models)

    def predict(self, features: pd.DataFrame) -> pd.DataFrame:
        validate_model_matrix(features)
        predictions: dict[str, np.ndarray] = {}
        for leaves in MODEL_NUM_LEAVES:
            if leaves not in self.models:
                raise ValueError(f"Ensemble is missing the num_leaves={leaves} model.")
            predictions[f"pred_model_{leaves}"] = self.models[leaves].predict_proba(features)[:, 1]
        out = pd.DataFrame(predictions, index=features.index)
        out["pred_score"] = out.mean(axis=1)
        return out

    def feature_importance(self) -> pd.DataFrame:
        frame = pd.DataFrame({"feature": FEATURE_COLUMNS})
        for leaves, model in sorted(self.models.items()):
            frame[f"model_{leaves}_split_importance"] = np.asarray(model.feature_importances_, dtype=float)
        importance_columns = [column for column in frame if column.endswith("_split_importance")]
        frame["mean_split_importance"] = frame[importance_columns].mean(axis=1)
        return frame.sort_values("mean_split_importance", ascending=False, kind="stable").reset_index(drop=True)

    def bundle(self, *, manifest: dict[str, Any]) -> dict[str, Any]:
        return {
            "strategy_name": STRATEGY_NAME,
            "strategy_version": STRATEGY_VERSION,
            "feature_columns": list(FEATURE_COLUMNS),
            "feature_schema_hash": feature_schema_hash(),
            "model_parameters": {
                f"model_{leaves}": {**COMMON_MODEL_PARAMS, "num_leaves": leaves}
                for leaves in MODEL_NUM_LEAVES
            },
            "models": {f"model_{leaves}": self.models[leaves] for leaves in MODEL_NUM_LEAVES},
            "manifest": dict(manifest),
        }

    def save(self, path: str | Path, *, manifest: dict[str, Any]) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.bundle(manifest=manifest), destination)
        return destination


def load_final_ensemble(path: str | Path) -> tuple[MetaEnsemble, dict[str, Any]]:
    """Load a versioned final bundle for paper/forward inference, fail closed."""
    payload = joblib.load(Path(path))
    if not isinstance(payload, dict):
        raise ValueError("Model bundle must be a mapping.")
    if list(payload.get("feature_columns", ())) != list(FEATURE_COLUMNS):
        raise ValueError("Model bundle feature order does not match the fixed 151-column contract.")
    raw_models = dict(payload.get("models", {}) or {})
    models: dict[int, Any] = {}
    for leaves in MODEL_NUM_LEAVES:
        key = f"model_{leaves}"
        if key not in raw_models:
            raise ValueError(f"Model bundle is missing {key}.")
        models[leaves] = raw_models[key]
    return MetaEnsemble(models=models), dict(payload.get("manifest", {}) or {})


def forward_inference(features: pd.DataFrame, bundle_path: str | Path) -> pd.DataFrame:
    """Score already-built candidate features without fitting or historical reuse."""
    validate_model_matrix(features)
    ensemble, _ = load_final_ensemble(bundle_path)
    return ensemble.predict(features)


__all__ = ["MetaEnsemble", "forward_inference", "load_final_ensemble"]
