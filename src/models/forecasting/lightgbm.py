from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.evaluation.model_diagnostics import (
    compute_lightgbm_importance,
    compute_lightgbm_shap_diagnostics,
)
from src.models.common.runtime import ensure_lightgbm_runtime_available
from src.models.types import ForecasterFoldPredictor


_INTERNAL_PARAM_KEYS = {
    "minimum_expected_features",
    "_diagnostics",
}


def _clean_lgbm_regressor_params(params: dict[str, Any]) -> dict[str, Any]:
    out = dict(params or {})
    for key in _INTERNAL_PARAM_KEYS:
        out.pop(key, None)
    out.setdefault("n_estimators", 300)
    out.setdefault("learning_rate", 0.03)
    out.setdefault("max_depth", -1)
    out.setdefault("num_leaves", 31)
    out.setdefault("subsample", 1.0)
    out.setdefault("colsample_bytree", 1.0)
    out.setdefault("random_state", 7)
    out.setdefault("n_jobs", 1)
    out.setdefault("verbosity", -1)
    return out


def make_lightgbm_regressor_fold_predictor() -> ForecasterFoldPredictor:
    """
    Return a fold predictor compatible with train_forward_forecaster.

    The fold predictor trains only on rows with complete current-bar feature values and a known
    future-return target. Test predictions are emitted only where the current feature row is
    complete, preserving the OOS alignment contract used by the rest of the framework.
    """

    def _predict_fold(
        df: pd.DataFrame,
        train_idx: np.ndarray,
        test_idx: np.ndarray,
        feature_cols: list[str],
        target_col: str,
        model_params: dict[str, Any],
        runtime_meta: dict[str, Any],
    ) -> tuple[pd.Series, dict[str, pd.Series], object, dict[str, Any]]:
        ensure_lightgbm_runtime_available()
        from lightgbm import LGBMRegressor

        if not feature_cols:
            raise ValueError("lightgbm_regressor requires at least one feature column.")

        params = _clean_lgbm_regressor_params(model_params)
        train_index = df.index[np.asarray(train_idx, dtype=int)]
        test_index = df.index[np.asarray(test_idx, dtype=int)]

        x_train_all = df.loc[train_index, feature_cols].astype(float)
        y_train_all = df.loc[train_index, target_col].astype(float)
        x_test_all = df.loc[test_index, feature_cols].astype(float)

        train_complete = x_train_all.notna().all(axis=1) & y_train_all.notna()
        test_complete = x_test_all.notna().all(axis=1)
        train_rows = int(train_complete.sum())
        if train_rows <= 0:
            raise ValueError(
                "lightgbm_regressor has no complete training rows after feature/target NaN filtering."
            )

        model = LGBMRegressor(**params)
        model.fit(
            x_train_all.loc[train_complete, feature_cols],
            y_train_all.loc[train_complete],
        )
        if hasattr(model, "feature_name_"):
            feature_names = list(getattr(model, "feature_name_") or [])
            if len(feature_names) != len(feature_cols):
                raise AssertionError(
                    "LightGBM feature_name_ length must match actual_model_feature_count."
                )

        predictions = pd.Series(np.nan, index=test_index, dtype=float)
        if bool(test_complete.any()):
            pred_values = model.predict(x_test_all.loc[test_complete, feature_cols])
            predictions.loc[test_complete[test_complete].index] = np.asarray(pred_values, dtype=float)

        selected_feature_count = int(len(feature_cols))
        diagnostics_cfg = dict(model_params.get("_diagnostics", {}) or {})
        model_diag_cfg = dict(diagnostics_cfg.get("model", diagnostics_cfg) or {})
        shap_cfg = dict(model_diag_cfg.get("shap", diagnostics_cfg.get("shap", {})) or {})
        shap_payload = {}
        if bool(model_diag_cfg.get("enabled", diagnostics_cfg.get("enabled", False))) or bool(shap_cfg.get("enabled", False)):
            shap_payload = compute_lightgbm_shap_diagnostics(
                model=model,
                features=x_test_all.loc[test_complete, feature_cols],
                predictions=predictions.loc[test_complete],
                realized=df.loc[test_index, target_col].astype(float),
                feature_cols=feature_cols,
                cfg=shap_cfg,
            )
        lightgbm_importance = compute_lightgbm_importance(model, feature_cols)
        meta = {
            "runtime": dict(runtime_meta or {}),
            "train_rows_raw": int(len(train_idx)),
            "model_train_rows": train_rows,
            "test_rows_raw": int(len(test_idx)),
            "test_pred_rows": int(predictions.notna().sum()),
            "selected_feature_count": selected_feature_count,
            "model_feature_count": selected_feature_count,
            "reported_feature_count": selected_feature_count,
            "final_feature_names": list(feature_cols),
            "dropped_missing_count": int(len(train_idx) - train_rows),
            "dropped_constant_count": 0,
            "dropped_selector_count": 0,
            "lightgbm_importance": lightgbm_importance,
        }
        if shap_payload:
            meta["shap"] = shap_payload
        return predictions.dropna(), {}, model, meta

    return _predict_fold


__all__ = ["make_lightgbm_regressor_fold_predictor"]
