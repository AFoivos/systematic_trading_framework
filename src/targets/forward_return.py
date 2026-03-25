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
    returns_col = cfg.get("returns_col")
    returns_type = str(cfg.get("returns_type", "simple"))
    horizon = int(cfg.get("horizon", 1))
    if horizon <= 0:
        raise ValueError("target.horizon must be a positive integer.")
    if returns_type not in {"simple", "log"}:
        raise ValueError("target.returns_type must be 'simple' or 'log'.")
    if returns_col is None and returns_type != "simple":
        raise ValueError("target.returns_type='log' requires target.returns_col.")
    fwd_col = cfg.get("fwd_col", f"target_fwd_{horizon}")
    label_col = cfg.get("label_col", "label")
    threshold = float(cfg.get("threshold", 0.0))
    quantiles = cfg.get("quantiles")

    out = df.copy()
    if returns_col is not None:
        returns_col = str(returns_col)
        if returns_col not in out.columns:
            raise KeyError(f"returns_col '{returns_col}' not found in DataFrame")
        future_returns = pd.concat(
            [
                out[returns_col].astype(float).shift(-step).rename(f"step_{step}")
                for step in range(1, horizon + 1)
            ],
            axis=1,
        )
        valid_mask = future_returns.notna().all(axis=1)
        out[fwd_col] = np.nan
        if bool(valid_mask.any()):
            if returns_type == "log":
                target_values = future_returns.loc[valid_mask].sum(axis=1)
            else:
                target_values = (1.0 + future_returns.loc[valid_mask]).prod(axis=1) - 1.0
            out.loc[valid_mask, fwd_col] = target_values.to_numpy(dtype=float)
    else:
        if price_col not in df.columns:
            raise KeyError(f"price_col '{price_col}' not found in DataFrame")
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
        "returns_col": returns_col,
        "returns_type": returns_type,
        "horizon": horizon,
        "fwd_col": fwd_col,
        "label_col": label_col,
        "threshold": threshold,
        "quantiles": quantiles,
        "labeled_rows": int(valid_mask.sum()),
        "positive_rate": float((out.loc[valid_mask, label_col] == 1.0).mean()) if not quantiles and bool(valid_mask.any()) else None,
    }
    return out, label_col, fwd_col, meta


__all__ = ["build_forward_return_target"]
