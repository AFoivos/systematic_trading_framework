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
