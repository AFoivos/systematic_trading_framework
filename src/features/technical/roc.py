from __future__ import annotations

from typing import Sequence

import pandas as pd


def add_roc_features(
    df: pd.DataFrame,
    price_col: str = "close",
    windows: Sequence[int] = (10, 20),
    inplace: bool = False,
) -> pd.DataFrame:
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")
    out = df if inplace else df.copy()
    close = out[price_col].astype(float)
    for window in windows:
        out[f"roc_{window}"] = compute_roc(close, window=window)
    return out


def compute_roc(close: pd.Series, window: int = 10) -> pd.Series:
    roc = close / close.shift(window) - 1.0
    roc.name = f"roc_{window}"
    return roc

__all__ = ["compute_roc", "add_roc_features"]
