from __future__ import annotations

from typing import Optional

import pandas as pd


def compute_sma(prices: pd.Series, window: int, min_periods: Optional[int] = None) -> pd.Series:
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series")
    if min_periods is None:
        min_periods = window
    sma = prices.rolling(window=window, min_periods=min_periods).mean()
    sma.name = f"{prices.name}_sma_{window}"
    return sma


__all__ = ["compute_sma"]
