from __future__ import annotations

import numpy as np
import pandas as pd


def add_mfi_features(
    df: pd.DataFrame,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    volume_col: str = "volume",
    window: int = 14,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``mfi`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: mfi
            params:
              high_col: high
              low_col: low
              close_col: close
              volume_col: volume
              window: 14
              inplace: false
    
    Required input columns
    ----------------------
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    volume_col:
        Input dataframe column configured by ``volume_col``. Default: ``volume``.
    
    Parameters
    ----------
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    volume_col:
        Input dataframe column configured by ``volume_col``. Default: ``volume``.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``14``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    """
    missing = [c for c in (high_col, low_col, close_col, volume_col) if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for MFI features: {missing}")
    out = df if inplace else df.copy()
    out[f"mfi_{window}"] = compute_mfi(
        out[high_col].astype(float),
        out[low_col].astype(float),
        out[close_col].astype(float),
        out[volume_col].astype(float),
        window=window,
    )
    return out


def compute_mfi(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    window: int = 14,
) -> pd.Series:
    """
    Compute the ``compute_mfi`` feature value.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: compute_mfi
            params:
              high: <required>
              low: <required>
              close: <required>
              volume: <required>
              window: 14
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    high:
        Configuration parameter accepted by this feature.
    low:
        Configuration parameter accepted by this feature.
    close:
        Configuration parameter accepted by this feature.
    volume:
        Configuration parameter accepted by this feature.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``14``.
    """
    typical_price = (high + low + close) / 3.0
    raw_flow = typical_price * volume
    pos_flow = raw_flow.where(typical_price.diff() > 0, 0.0)
    neg_flow = raw_flow.where(typical_price.diff() < 0, 0.0)

    pos_sum = pos_flow.rolling(window=window, min_periods=window).sum()
    neg_sum = neg_flow.rolling(window=window, min_periods=window).sum()
    mfr = pos_sum / neg_sum.replace(0, np.nan)
    mfi = 100 - (100 / (1 + mfr))
    mfi = mfi.where(~((neg_sum == 0.0) & (pos_sum > 0.0)), other=100.0)
    mfi = mfi.where(~((pos_sum == 0.0) & (neg_sum > 0.0)), other=0.0)
    mfi.name = f"mfi_{window}"
    return mfi

__all__ = ["compute_mfi", "add_mfi_features"]
