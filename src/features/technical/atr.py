from __future__ import annotations

import pandas as pd

from .true_range import compute_true_range


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 14,
    method: str = "wilder",
) -> pd.Series:
    tr = compute_true_range(high, low, close)
    if method == "wilder":
        atr = tr.ewm(alpha=1 / window, adjust=False).mean()
    elif method == "simple":
        atr = tr.rolling(window=window, min_periods=window).mean()
    else:
        raise ValueError("method must be 'wilder' or 'simple'")
    atr.name = f"atr_{window}"
    return atr


__all__ = ["compute_atr"]
