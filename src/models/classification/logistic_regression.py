from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.linear_model import LogisticRegression

from src.models.classification.base import train_forward_classifier


def train_logistic_regression_classifier(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    cfg = dict(model_cfg or {})
    params = dict(cfg.get("params", {}) or {})
    params.setdefault("max_iter", 1000)
    params.setdefault("solver", "lbfgs")
    cfg["params"] = params
    preprocessing = dict(cfg.get("preprocessing", {}) or {})
    preprocessing.setdefault("scaler", "standard")
    cfg["preprocessing"] = preprocessing

    out, model, meta = train_forward_classifier(
        df,
        cfg,
        model_kind="logistic_regression_clf",
        estimator_family="sklearn",
        estimator_factory=lambda model_params: LogisticRegression(**model_params),
        returns_col=returns_col,
    )
    return out, model, meta


__all__ = ["train_logistic_regression_classifier"]
