from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd


def compute_rsi(
    prices: pd.Series,
    window: int = 14,
    method: str = "wilder",
) -> pd.Series:
    """
    RSI (Relative Strength Index).

    method:
    - "wilder": EWMA με alpha = 1/window (Classical RSI)
    - "simple": simple rolling mean σε gains/losses
    """
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


def compute_stoch_k(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    window: int = 14,
) -> pd.Series:
    """
    Stochastic %K:

    %K_t = 100 * (close_t - lowest_low) / (highest_high - lowest_low)
    """
    if not (isinstance(close, pd.Series) and isinstance(high, pd.Series) and isinstance(low, pd.Series)):
        raise TypeError("close, high, low must be pandas Series")

    lowest_low = low.rolling(window=window, min_periods=window).min()
    highest_high = high.rolling(window=window, min_periods=window).max()

    range_ = (highest_high - lowest_low).replace(0.0, np.nan)
    k = 100.0 * (close - lowest_low) / range_
    k = k.clip(lower=0.0, upper=100.0)
    k.name = f"{close.name}_stoch_k_{window}"
    return k


def compute_stoch_d(
    k: pd.Series,
    smooth: int = 3,
) -> pd.Series:
    """
    Stochastic %D: moving average του %K.
    """
    if not isinstance(k, pd.Series):
        raise TypeError("k must be a pandas Series")

    d = k.rolling(window=smooth, min_periods=smooth).mean()
    d.name = f"{k.name}_d{smooth}"
    return d


def add_oscillator_features(
    df: pd.DataFrame,
    price_col: str = "close",
    high_col: str = "high",
    low_col: str = "low",
    rsi_windows: Sequence[int] = (14,),
    stoch_windows: Sequence[int] = (14,),
    stoch_smooth: int = 3,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Features:
    - {price_col}_rsi_{w}
    - {price_col}_stoch_k_{w}
    - {price_col}_stoch_k_{w}_d{stoch_smooth}
    """
    missing = [c for c in (price_col, high_col, low_col) if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for oscillators: {missing}")

    out = df if inplace else df.copy()

    close = out[price_col].astype(float)
    high = out[high_col].astype(float)
    low = out[low_col].astype(float)

    for w in rsi_windows:
        rsi = compute_rsi(close, window=w, method="wilder")
        out[f"{price_col}_rsi_{w}"] = rsi

    for w in stoch_windows:
        k = compute_stoch_k(close, high, low, window=w)
        d = compute_stoch_d(k, smooth=stoch_smooth)

        out[f"{price_col}_stoch_k_{w}"] = k
        out[f"{price_col}_stoch_d_{w}"] = d

    return out
