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
    Apply the registered ``elastic_net_clf`` model transformation.
    
    This model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        model:
          kind: elastic_net_clf
          params:
            returns_col: null
            params: <configured>
            penalty: <configured>
            preprocessing: <configured>
            solver: <configured>
    
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
    penalty:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    preprocessing:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    solver:
        Configuration parameter accepted by this model. Default: ``<configured>``.
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
