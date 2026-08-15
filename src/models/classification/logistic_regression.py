from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.linear_model import LogisticRegression

from src.models.classification.base import train_forward_classifier


def create_logistic_regression_estimator(
    model_params: dict[str, Any] | None = None,
) -> LogisticRegression:
    """Build the framework-approved logistic estimator without fitting it.

    Research adapters may reuse this factory inside their own framework-owned
    folds.  Keeping construction here avoids a second model registry and keeps
    the canonical classifier and optional adapters on identical defaults.
    """

    params = dict(model_params or {})
    params.setdefault("max_iter", 1000)
    params.setdefault("solver", "lbfgs")
    return LogisticRegression(**params)


def train_logistic_regression_classifier(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Apply the registered ``logistic_regression_clf`` model transformation.
    
    This model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        model:
          kind: logistic_regression_clf
          params:
            returns_col: null
            params: <configured>
            preprocessing: <configured>
    
    Required input columns
    ----------------------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    
    Parameters
    ----------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    params:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    preprocessing:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    """
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
        estimator_factory=create_logistic_regression_estimator,
        returns_col=returns_col,
    )
    return out, model, meta


__all__ = [
    "create_logistic_regression_estimator",
    "train_logistic_regression_classifier",
]
