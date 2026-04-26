from __future__ import annotations

from typing import Sequence

import pandas as pd

from .true_range import compute_true_range


def add_atr_features(
    df: pd.DataFrame,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    window: int = 14,
    windows: Sequence[int] | None = None,
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
    for resolved_window in _resolve_windows(window=window, windows=windows):
        atr = compute_atr(high, low, close, window=resolved_window, method=method)
        out[f"atr_{resolved_window}"] = atr
        if add_over_price:
            out[f"atr_over_price_{resolved_window}"] = atr / close
    return out


def _resolve_windows(*, window: int, windows: Sequence[int] | None) -> list[int]:
    raw_windows = list(windows) if windows is not None else [window]
    resolved: list[int] = []
    for raw_window in raw_windows:
        if isinstance(raw_window, bool) or int(raw_window) <= 0:
            raise ValueError("ATR windows must be positive integers.")
        value = int(raw_window)
        if value not in resolved:
            resolved.append(value)
    if not resolved:
        raise ValueError("ATR windows must not be empty.")
    return resolved


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
