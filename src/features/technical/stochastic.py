from __future__ import annotations

import numpy as np
import pandas as pd


def add_stochastic_features(
    df: pd.DataFrame,
    price_col: str = "close",
    high_col: str = "high",
    low_col: str = "low",
    window: int = 14,
    smooth: int = 3,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``stochastic`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: stochastic
            params:
              price_col: close
              high_col: high
              low_col: low
              window: 14
              smooth: 3
              inplace: false
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``14``.
    smooth:
        Configuration parameter accepted by this feature. Default: ``3``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    """
    missing = [c for c in (price_col, high_col, low_col) if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for stochastic features: {missing}")
    out = df if inplace else df.copy()
    close = out[price_col].astype(float)
    high = out[high_col].astype(float)
    low = out[low_col].astype(float)
    k = compute_stoch_k(close, high, low, window=window)
    d = compute_stoch_d(k, smooth=smooth)
    out[f"{price_col}_stoch_k_{window}"] = k
    out[f"{price_col}_stoch_d_{window}"] = d
    return out


def compute_stoch_k(close: pd.Series, high: pd.Series, low: pd.Series, window: int = 14) -> pd.Series:
    """
    Compute the ``compute_stoch_k`` feature value.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: compute_stoch_k
            params:
              close: <required>
              high: <required>
              low: <required>
              window: 14
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    close:
        Configuration parameter accepted by this feature.
    high:
        Configuration parameter accepted by this feature.
    low:
        Configuration parameter accepted by this feature.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``14``.
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


def compute_stoch_d(k: pd.Series, smooth: int = 3) -> pd.Series:
    """
    Compute the ``compute_stoch_d`` feature value.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: compute_stoch_d
            params:
              k: <required>
              smooth: 3
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    k:
        Configuration parameter accepted by this feature.
    smooth:
        Configuration parameter accepted by this feature. Default: ``3``.
    """
    if not isinstance(k, pd.Series):
        raise TypeError("k must be a pandas Series")
    d = k.rolling(window=smooth, min_periods=smooth).mean()
    d.name = f"{k.name}_d{smooth}"
    return d

__all__ = ["compute_stoch_k", "compute_stoch_d", "add_stochastic_features"]
