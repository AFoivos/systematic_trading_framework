from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def build_forward_return_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Build the canonical forward-return target and optional binary label columns.
    """
    cfg = dict(target_cfg or {})
    price_col = cfg.get("price_col", "close")
    horizon = int(cfg.get("horizon", 1))
    if horizon <= 0:
        raise ValueError("target.horizon must be a positive integer.")
    fwd_col = cfg.get("fwd_col", f"target_fwd_{horizon}")
    label_col = cfg.get("label_col", "label")
    threshold = float(cfg.get("threshold", 0.0))
    quantiles = cfg.get("quantiles")

    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")

    out = df.copy()
    out[fwd_col] = out[price_col].pct_change(periods=horizon).shift(-horizon)

    valid_mask = out[fwd_col].notna()
    out[label_col] = np.nan
    if quantiles:
        if not isinstance(quantiles, (list, tuple)) or len(quantiles) != 2:
            raise ValueError("target.quantiles must be a [low, high] pair")
        q_low, q_high = float(quantiles[0]), float(quantiles[1])
        if not (0.0 <= q_low < q_high <= 1.0):
            raise ValueError("target.quantiles must satisfy 0 <= low < high <= 1")
    else:
        out.loc[valid_mask, label_col] = (out.loc[valid_mask, fwd_col] > threshold).astype("float32")

    meta = {
        "kind": "forward_return",
        "price_col": price_col,
        "horizon": horizon,
        "fwd_col": fwd_col,
        "label_col": label_col,
        "threshold": threshold,
        "quantiles": quantiles,
    }
    return out, label_col, fwd_col, meta


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


__all__ = ["assign_quantile_labels", "build_forward_return_target"]
