from __future__ import annotations

import numpy as np
import pandas as pd


def compute_stoch_k(close: pd.Series, high: pd.Series, low: pd.Series, window: int = 14) -> pd.Series:
    if not (isinstance(close, pd.Series) and isinstance(high, pd.Series) and isinstance(low, pd.Series)):
        raise TypeError("close, high, low must be pandas Series")

    lowest_low = low.rolling(window=window, min_periods=window).min()
    highest_high = high.rolling(window=window, min_periods=window).max()
    range_ = (highest_high - lowest_low).replace(0.0, np.nan)
    k = 100.0 * (close - lowest_low) / range_
    k = k.clip(lower=0.0, upper=100.0)
    k.name = f"{close.name}_stoch_k_{window}"
    return k


def compute_stoch_d(k: pd.Series, smooth: int = 3) -> pd.Series:
    if not isinstance(k, pd.Series):
        raise TypeError("k must be a pandas Series")
    d = k.rolling(window=smooth, min_periods=smooth).mean()
    d.name = f"{k.name}_d{smooth}"
    return d


__all__ = ["compute_stoch_k", "compute_stoch_d"]
