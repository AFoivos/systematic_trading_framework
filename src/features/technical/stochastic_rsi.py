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
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: stochastic_rsi
            params:
              price_col: close
              rsi_period: 14
              stoch_period: 14
              k_period: 3
              d_period: 3
              oversold: 0.2
              overbought: 0.8
              prefix: stoch_rsi
              method: wilder
              inplace: false
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    rsi_period:
        Configuration parameter accepted by this feature. Default: ``14``.
    stoch_period:
        Configuration parameter accepted by this feature. Default: ``14``.
    k_period:
        Configuration parameter accepted by this feature. Default: ``3``.
    d_period:
        Configuration parameter accepted by this feature. Default: ``3``.
    oversold:
        Configuration parameter accepted by this feature. Default: ``0.2``.
    overbought:
        Configuration parameter accepted by this feature. Default: ``0.8``.
    prefix:
        Configuration parameter accepted by this feature. Default: ``stoch_rsi``.
    method:
        Configuration parameter accepted by this feature. Default: ``wilder``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
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
    """
    Compute the ``compute_stochastic_rsi`` feature value.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: compute_stochastic_rsi
            params:
              rsi_period: 14
              stoch_period: 14
              k_period: 3
              d_period: 3
              oversold: 0.2
              overbought: 0.8
              prefix: stoch_rsi
              method: wilder
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    rsi_period:
        Configuration parameter accepted by this feature. Default: ``14``.
    stoch_period:
        Configuration parameter accepted by this feature. Default: ``14``.
    k_period:
        Configuration parameter accepted by this feature. Default: ``3``.
    d_period:
        Configuration parameter accepted by this feature. Default: ``3``.
    oversold:
        Configuration parameter accepted by this feature. Default: ``0.2``.
    overbought:
        Configuration parameter accepted by this feature. Default: ``0.8``.
    prefix:
        Configuration parameter accepted by this feature. Default: ``stoch_rsi``.
    method:
        Configuration parameter accepted by this feature. Default: ``wilder``.
    """
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
    return pd.DataFrame(
        {
            f"{prefix}_k": k,
            f"{prefix}_d": d,
        },
        index=prices.index,
    )


__all__ = ["compute_stochastic_rsi", "add_stochastic_rsi_features"]
