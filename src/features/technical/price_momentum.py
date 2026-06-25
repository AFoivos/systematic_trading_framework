from __future__ import annotations

from typing import Sequence

import pandas as pd


def add_price_momentum_features(
    df: pd.DataFrame,
    price_col: str = "close",
    windows: Sequence[int] = (5, 20, 60),
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``price_momentum`` feature transformation.
    
    YAML declaration::
    
        features:
          - step: price_momentum
            params: {}
    
    Required input columns
    ----------------------
    price_col:
        Input column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column name consumed by the component. Default: ``close``.
    windows:
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``(5, 20, 60)``.
    inplace:
        Configuration value used by the registered component. Default: ``False``.
    """
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")
    out = df if inplace else df.copy()
    prices = out[price_col].astype(float)
    for window in windows:
        out[f"{price_col}_mom_{window}"] = compute_price_momentum(prices, window)
    return out


def compute_price_momentum(prices: pd.Series, window: int) -> pd.Series:
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series")
    mom = prices / prices.shift(window) - 1.0
    mom.name = f"{prices.name}_mom_{window}"
    return mom

__all__ = ["compute_price_momentum", "add_price_momentum_features"]
