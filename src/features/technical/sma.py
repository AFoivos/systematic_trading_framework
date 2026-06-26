from __future__ import annotations

from typing import Optional

import pandas as pd


def compute_sma(prices: pd.Series, window: int, min_periods: Optional[int] = None) -> pd.Series:
    """
    Compute the ``compute_sma`` feature value.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: compute_sma
            params:
              window: <required>
              min_periods: null
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    window:
        Trailing lookback or forecast horizon controlling this feature.
    min_periods:
        Configuration parameter accepted by this feature. Default: ``null``.
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series")
    if min_periods is None:
        min_periods = window
    sma = prices.rolling(window=window, min_periods=min_periods).mean()
    sma.name = f"{prices.name}_sma_{window}"
    return sma


__all__ = ["compute_sma"]
