from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.models.common.runtime import ensure_xgboost_runtime_available
from src.models.types import ForecasterFoldPredictor


_INTERNAL_PARAM_KEYS = {
    "minimum_expected_features",
    "_diagnostics",
}
_LIGHTGBM_ONLY_PARAM_KEYS = {
    "num_leaves",
    "min_child_samples",
}


def _clean_xgboost_regressor_params(params: dict[str, Any]) -> dict[str, Any]:
    out = dict(params or {})
    for key in _INTERNAL_PARAM_KEYS | _LIGHTGBM_ONLY_PARAM_KEYS:
        out.pop(key, None)
    out = {key: value for key, value in out.items() if value is not None}
    out.setdefault("objective", "reg:squarederror")
    out.setdefault("eval_metric", "rmse")
    out.setdefault("tree_method", "hist")
    out.setdefault("random_state", 7)
    out.setdefault("n_jobs", 1)
    return out


def make_xgboost_regressor_fold_predictor() -> ForecasterFoldPredictor:
    """
    Return an XGBRegressor fold predictor compatible with train_forward_forecaster.
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
        ensure_xgboost_runtime_available()
        from xgboost import XGBRegressor

        if not feature_cols:
            raise ValueError("xgboost_regressor requires at least one feature column.")

        params = _clean_xgboost_regressor_params(model_params)
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
                "xgboost_regressor has no complete training rows after feature/target NaN filtering."
            )

        model = XGBRegressor(**params)
        model.fit(
            x_train_all.loc[train_complete, feature_cols],
            y_train_all.loc[train_complete],
        )

        predictions = pd.Series(np.nan, index=test_index, dtype=float)
        if bool(test_complete.any()):
            pred_values = model.predict(x_test_all.loc[test_complete, feature_cols])
            predictions.loc[test_complete[test_complete].index] = np.asarray(pred_values, dtype=float)

        selected_feature_count = int(len(feature_cols))
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
        }
        return predictions.dropna(), {}, model, meta

    return _predict_fold


__all__ = ["make_xgboost_regressor_fold_predictor"]
