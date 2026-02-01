from __future__ import annotations

from typing import Sequence, Optional

import numpy as np
import pandas as pd


def compute_price_momentum(
    prices: pd.Series,
    window: int,
) -> pd.Series:
    """
    Price momentum: P_t / P_{t-window} - 1
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series")

    mom = prices / prices.shift(window) - 1.0
    mom.name = f"{prices.name}_mom_{window}"
    return mom


def compute_return_momentum(
    returns: pd.Series,
    window: int,
) -> pd.Series:
    """
    Return-based momentum: sum of returns over window.
    (For log-returns: additive)
    """
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas Series")

    mom = returns.rolling(window=window).sum()
    mom.name = f"{returns.name}_mom_{window}"
    return mom


def compute_vol_normalized_momentum(
    returns: pd.Series,
    volatility: pd.Series,
    window: int,
    eps: float = 1e-8,
) -> pd.Series:
    """
    Volatility-normalized momentum:
    sum of returns / current volatility
    """
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas Series")
    if not isinstance(volatility, pd.Series):
        raise TypeError("volatility must be a pandas Series")

    raw_mom = returns.rolling(window=window).sum()
    norm_mom = raw_mom / (volatility + eps)

    norm_mom.name = f"{returns.name}_norm_mom_{window}"
    return norm_mom


def add_momentum_features(
    df: pd.DataFrame,
    price_col: str = "close",
    returns_col: str = "close_logret",
    vol_col: Optional[str] = "vol_rolling_20",
    windows: Sequence[int] = (5, 20, 60),
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Προσθέτει momentum features:

    - price momentum
    - return momentum
    - volatility-normalized momentum (αν υπάρχει vol_col)
    """
    out = df if inplace else df.copy()

    prices = out[price_col].astype(float)
    returns = out[returns_col].astype(float)

    for w in windows:
        out[f"{price_col}_mom_{w}"] = compute_price_momentum(prices, w)
        out[f"{returns_col}_mom_{w}"] = compute_return_momentum(returns, w)

        if vol_col is not None and vol_col in out.columns:
            out[f"{returns_col}_norm_mom_{w}"] = compute_vol_normalized_momentum(
                returns,
                out[vol_col].astype(float),
                window=w,
            )

    return out
