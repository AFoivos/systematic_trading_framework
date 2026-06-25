from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.linear_model import LogisticRegression

from src.models.classification.base import train_forward_classifier


def train_elastic_net_classifier(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Train the registered ``elastic_net_clf`` model component.
    
    YAML declaration::
    
        model:
          kind: elastic_net_clf
          params: {}
    
    Required input columns
    ----------------------
    returns_col:
        Optional input column configured by ``returns_col``; used when a value is provided.
    
    Parameters
    ----------
    model_cfg:
        Configuration mapping, usually resolved from YAML before this
        registered component is called.
    returns_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    """
    cfg = dict(model_cfg or {})
    params = dict(cfg.get("params", {}) or {})

    penalty = str(params.get("penalty", "elasticnet"))
    if penalty != "elasticnet":
        raise ValueError("elastic_net_clf requires params.penalty='elasticnet'.")
    solver = str(params.get("solver", "saga"))
    if solver != "saga":
        raise ValueError("elastic_net_clf requires params.solver='saga'.")

    params["penalty"] = "elasticnet"
    params["solver"] = "saga"
    params.setdefault("l1_ratio", 0.5)
    params.setdefault("C", 1.0)
    params.setdefault("max_iter", 2000)
    cfg["params"] = params

    preprocessing = dict(cfg.get("preprocessing", {}) or {})
    preprocessing.setdefault("scaler", "standard")
    cfg["preprocessing"] = preprocessing

    out, model, meta = train_forward_classifier(
        df,
        cfg,
        model_kind="elastic_net_clf",
        estimator_family="sklearn",
        estimator_factory=lambda model_params: LogisticRegression(**model_params),
        returns_col=returns_col,
    )
    return out, model, meta


__all__ = ["train_elastic_net_classifier"]
