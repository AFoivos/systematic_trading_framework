from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


def add_rsi_features(
    df: pd.DataFrame,
    price_col: str = "close",
    windows: Sequence[int] = (14,),
    method: str = "wilder",
    inplace: bool = False,
) -> pd.DataFrame:
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")
    out = df if inplace else df.copy()
    prices = out[price_col].astype(float)
    for window in windows:
        out[f"{price_col}_rsi_{window}"] = compute_rsi(prices, window=window, method=method)
    return out


def compute_rsi(prices: pd.Series, window: int = 14, method: str = "wilder") -> pd.Series:
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series")

    delta = prices.diff()
    gains = delta.clip(lower=0.0)
    losses = -delta.clip(upper=0.0)

    if method == "wilder":
        avg_gain = gains.ewm(alpha=1 / window, adjust=False).mean()
        avg_loss = losses.ewm(alpha=1 / window, adjust=False).mean()
    elif method == "simple":
        avg_gain = gains.rolling(window=window, min_periods=window).mean()
        avg_loss = losses.rolling(window=window, min_periods=window).mean()
    else:
        raise ValueError("method must be 'wilder' or 'simple'")

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.where(~((avg_loss == 0.0) & (avg_gain > 0.0)), other=100.0)
    rsi = rsi.where(~((avg_gain == 0.0) & (avg_loss > 0.0)), other=0.0)
    rsi = rsi.clip(lower=0.0, upper=100.0)
    rsi.name = f"{prices.name}_rsi_{window}"
    return rsi

__all__ = ["compute_rsi", "add_rsi_features"]
