from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from .wilder import wilder_smooth


def add_rsi_features(
    df: pd.DataFrame,
    price_col: str = "close",
    windows: Sequence[int] = (14,),
    method: str = "wilder",
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``rsi`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: rsi
            params:
              price_col: close
              windows: [14]
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
    windows:
        Trailing lookback or forecast horizon controlling this feature. Default: ``[14]``.
    method:
        Configuration parameter accepted by this feature. Default: ``wilder``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    """
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")
    out = df if inplace else df.copy()
    prices = out[price_col].astype(float)
    for window in windows:
        out[f"{price_col}_rsi_{window}"] = compute_rsi(prices, window=window, method=method)
    return out


def compute_rsi(prices: pd.Series, window: int = 14, method: str = "wilder") -> pd.Series:
    """
    Compute the ``compute_rsi`` feature value.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: compute_rsi
            params:
              window: 14
              method: wilder
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``14``.
    method:
        Configuration parameter accepted by this feature. Default: ``wilder``.
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series")

    delta = prices.diff()
    gains = delta.clip(lower=0.0)
    losses = -delta.clip(upper=0.0)

    if method == "wilder":
        avg_gain = wilder_smooth(gains, window=window)
        avg_loss = wilder_smooth(losses, window=window)
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
