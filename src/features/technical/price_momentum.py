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
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: price_momentum
            params:
              price_col: close
              windows: [5, 20, 60]
              inplace: false
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    windows:
        Trailing lookback or forecast horizon controlling this feature. Default: ``[5, 20, 60]``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    """
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")
    out = df if inplace else df.copy()
    prices = out[price_col].astype(float)
    for window in windows:
        out[f"{price_col}_mom_{window}"] = compute_price_momentum(prices, window)
    return out


def compute_price_momentum(prices: pd.Series, window: int) -> pd.Series:
    """
    Compute the ``compute_price_momentum`` feature value.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: compute_price_momentum
            params:
              window: <required>
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    window:
        Trailing lookback or forecast horizon controlling this feature.
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series")
    mom = prices / prices.shift(window) - 1.0
    mom.name = f"{prices.name}_mom_{window}"
    return mom

__all__ = ["compute_price_momentum", "add_price_momentum_features"]
