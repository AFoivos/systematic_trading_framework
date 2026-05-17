from __future__ import annotations

from typing import Any

import pandas as pd

from src.models.classification.base import train_forward_classifier
from src.models.common.runtime import ensure_xgboost_runtime_available


def train_xgboost_classifier(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    ensure_xgboost_runtime_available()
    try:
        from xgboost import XGBClassifier
    except Exception as exc:
        raise ImportError(
            "XGBoost classifier requires xgboost. Install xgboost to use model.kind='xgboost_clf'."
        ) from exc
    cfg = dict(model_cfg or {})
    params = dict(cfg.get("params", {}) or {})
    for unsupported_key in ("num_leaves", "min_child_samples"):
        params.pop(unsupported_key, None)
    params = {key: value for key, value in params.items() if value is not None}
    params.setdefault("objective", "binary:logistic")
    params.setdefault("eval_metric", "logloss")
    params.setdefault("tree_method", "hist")
    cfg["params"] = params

    out, model, meta = train_forward_classifier(
        df,
        cfg,
        model_kind="xgboost_clf",
        estimator_family="xgboost",
        estimator_factory=lambda model_params: XGBClassifier(**model_params),
        returns_col=returns_col,
    )
    return out, model, meta


__all__ = ["train_xgboost_classifier"]
