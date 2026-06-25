from __future__ import annotations

from typing import Any

import pandas as pd

from src.models.classification.base import train_forward_classifier
from src.models.common.runtime import ensure_lightgbm_runtime_available


def train_lightgbm_classifier(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Train a LightGBM forward classifier through the shared classification
    training pipeline.
    
    This function is a thin wrapper around ``train_forward_classifier``. It
    checks that LightGBM is available, creates an ``LGBMClassifier`` from the
    estimator parameters, and delegates target creation, feature selection,
    anti-leakage time splits, training, prediction generation, and metadata
    reporting to the shared classifier pipeline.
    
    YAML declaration::
    
        models:
              - kind: lightgbm_clf
                params:
                  target:
                    horizon: 1
                    threshold: 0.0
                    label_col: label
                    fwd_col: fwd_return
    
                  feature_cols: null
                  feature_selectors: null
    
                  split:
                    method: time
                    train_size: 0.70
                    test_size: 0.30
    
                  preprocessing:
                    scaler: none
    
                  calibration:
                    method: none
                    fraction: 0.20
                    min_rows: 200
    
                  pred_prob_col: pred_prob
                  pred_raw_prob_col: null
                  pred_is_oos_col: pred_is_oos
    
                  params:
                    n_estimators: 300
                    learning_rate: 0.05
                    num_leaves: 31
                    max_depth: -1
                    subsample: 1.0
                    colsample_bytree: 1.0
                    random_state: 42
                output_cols:
                  - pred_prob
                  - pred_is_oos
    
    Required input columns
    ----------------------
    returns_col:
        Optional input column configured by ``returns_col``; used when a value is provided.
    
    Parameters
    ----------
    df:
        Input DataFrame containing the feature columns and the source columns
        required to build the classifier target.
    model_cfg:
        Model configuration mapping consumed by the shared classifier pipeline.
        It may contain target settings, feature columns or selectors, split
        settings, preprocessing settings, calibration settings, prediction
        output-column names, and LightGBM estimator parameters.
    returns_col:
        Optional returns column passed to overlays such as GARCH.
    """


    ensure_lightgbm_runtime_available()
    try:
        from lightgbm import LGBMClassifier
    except Exception as exc:
        raise ImportError(
            "LightGBM classifier requires lightgbm. Install lightgbm to use model.kind='lightgbm_clf'."
        ) from exc
    return train_forward_classifier(
        df,
        model_cfg,
        model_kind="lightgbm_clf",
        estimator_family="lightgbm",
        estimator_factory=lambda params: LGBMClassifier(**params),
        returns_col=returns_col,
    )


__all__ = ["train_lightgbm_classifier"]
