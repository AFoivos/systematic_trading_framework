from __future__ import annotations

import pandas as pd

from .true_range import compute_true_range


def add_atr_features(
    df: pd.DataFrame,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    window: int = 14,
    method: str = "wilder",
    add_over_price: bool = True,
    inplace: bool = False,
) -> pd.DataFrame:
    missing = [c for c in (high_col, low_col, close_col) if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for ATR features: {missing}")
    out = df if inplace else df.copy()
    high = out[high_col].astype(float)
    low = out[low_col].astype(float)
    close = out[close_col].astype(float)
    atr = compute_atr(high, low, close, window=window, method=method)
    out[f"atr_{window}"] = atr
    if add_over_price:
        out[f"atr_over_price_{window}"] = atr / close
    return out


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

__all__ = ["compute_atr", "add_atr_features"]
