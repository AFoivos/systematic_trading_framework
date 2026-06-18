from __future__ import annotations

import numpy as np
import pandas as pd

from .rsi import compute_rsi


def add_stochastic_rsi_features(
    df: pd.DataFrame,
    price_col: str = "close",
    rsi_period: int = 14,
    stoch_period: int = 14,
    k_period: int = 3,
    d_period: int = 3,
    oversold: float = 0.20,
    overbought: float = 0.80,
    prefix: str = "stoch_rsi",
    method: str = "wilder",
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``stochastic_rsi`` feature transformation.

    YAML declaration::

        features:
          - step: stochastic_rsi
            params: {}
    """
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")

    out = df if inplace else df.copy()
    prices = out[price_col].astype(float)
    stoch_rsi = compute_stochastic_rsi(
        prices,
        rsi_period=rsi_period,
        stoch_period=stoch_period,
        k_period=k_period,
        d_period=d_period,
        oversold=oversold,
        overbought=overbought,
        prefix=prefix,
        method=method,
    )
    return out.join(stoch_rsi)


def compute_stochastic_rsi(
    prices: pd.Series,
    rsi_period: int = 14,
    stoch_period: int = 14,
    k_period: int = 3,
    d_period: int = 3,
    oversold: float = 0.20,
    overbought: float = 0.80,
    prefix: str = "stoch_rsi",
    method: str = "wilder",
) -> pd.DataFrame:
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series")
    for name, value in {
        "rsi_period": rsi_period,
        "stoch_period": stoch_period,
        "k_period": k_period,
        "d_period": d_period,
    }.items():
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if not isinstance(prefix, str) or not prefix.strip():
        raise ValueError("prefix must be a non-empty string")
    if not (0.0 <= float(oversold) <= 1.0):
        raise ValueError("oversold must be in [0, 1]")
    if not (0.0 <= float(overbought) <= 1.0):
        raise ValueError("overbought must be in [0, 1]")
    if float(oversold) >= float(overbought):
        raise ValueError("oversold must be less than overbought")

    rsi = compute_rsi(prices.astype(float), window=rsi_period, method=method)
    lowest_rsi = rsi.rolling(window=stoch_period, min_periods=stoch_period).min()
    highest_rsi = rsi.rolling(window=stoch_period, min_periods=stoch_period).max()
    rsi_range = (highest_rsi - lowest_rsi).replace(0.0, np.nan)

    raw = ((rsi - lowest_rsi) / rsi_range).clip(lower=0.0, upper=1.0)
    k = raw.rolling(window=k_period, min_periods=k_period).mean().clip(lower=0.0, upper=1.0)
    d = k.rolling(window=d_period, min_periods=d_period).mean().clip(lower=0.0, upper=1.0)
    k_minus_d = k - d
    slope = k - k.shift(1)
    cross_up = ((k.shift(1) <= d.shift(1)) & (k > d)).astype(int)
    cross_down = ((k.shift(1) >= d.shift(1)) & (k < d)).astype(int)
    oversold_flag = (k <= float(oversold)).astype(int)
    overbought_flag = (k >= float(overbought)).astype(int)
    recover_from_oversold = ((k.shift(1) <= float(oversold)) & (k > float(oversold))).astype(int)
    fall_from_overbought = ((k.shift(1) >= float(overbought)) & (k < float(overbought))).astype(int)

    return pd.DataFrame(
        {
            f"{prefix}_k": k,
            f"{prefix}_d": d,
            f"{prefix}_k_minus_d": k_minus_d,
            f"{prefix}_cross_up": cross_up,
            f"{prefix}_cross_down": cross_down,
            f"{prefix}_oversold": oversold_flag,
            f"{prefix}_overbought": overbought_flag,
            f"{prefix}_slope": slope,
            f"{prefix}_recover_from_oversold": recover_from_oversold,
            f"{prefix}_fall_from_overbought": fall_from_overbought,
        },
        index=prices.index,
    )


__all__ = ["compute_stochastic_rsi", "add_stochastic_rsi_features"]
