from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .forward_return import build_forward_return_target
from .triple_barrier import build_triple_barrier_target


def build_classifier_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    cfg = dict(target_cfg or {})
    kind = str(cfg.get("kind", "forward_return"))
    if kind == "forward_return":
        return build_forward_return_target(df=df, target_cfg=cfg)
    if kind == "triple_barrier":
        return build_triple_barrier_target(df=df, target_cfg=cfg)
    raise ValueError(f"Unsupported target.kind: {kind}")


def assign_quantile_labels(
    forward_returns: pd.Series,
    *,
    low_value: float,
    high_value: float,
) -> pd.Series:
    """
    Convert a forward-return series into a binary quantile label series.
    """
    labels = pd.Series(np.nan, index=forward_returns.index, dtype="float32")
    labels.loc[forward_returns <= float(low_value)] = 0.0
    labels.loc[forward_returns >= float(high_value)] = 1.0
    return labels


__all__ = ["assign_quantile_labels", "build_classifier_target"]
