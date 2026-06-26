from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from .true_range import compute_true_range


def add_adx_features(
    df: pd.DataFrame,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    window: int = 14,
    windows: Sequence[int] | None = None,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``adx`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: adx
            params:
              high_col: high
              low_col: low
              close_col: close
              window: 14
              windows: null
              inplace: false
    
    Required input columns
    ----------------------
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    
    Parameters
    ----------
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``14``.
    windows:
        Trailing lookback or forecast horizon controlling this feature. Default: ``null``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    """
    missing = [c for c in (high_col, low_col, close_col) if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for ADX features: {missing}")
    out = df if inplace else df.copy()
    high = out[high_col].astype(float)
    low = out[low_col].astype(float)
    close = out[close_col].astype(float)
    resolved_windows = _resolve_windows(window=window, windows=windows)
    for resolved_window in resolved_windows:
        adx = compute_adx(high, low, close, window=resolved_window)
        for column in adx.columns:
            out[column] = adx[column]
    return out


def _resolve_windows(*, window: int, windows: Sequence[int] | None) -> list[int]:
    raw_windows = list(windows) if windows is not None else [window]
    resolved: list[int] = []
    for raw_window in raw_windows:
        if isinstance(raw_window, bool) or int(raw_window) <= 0:
            raise ValueError("ADX windows must be positive integers.")
        value = int(raw_window)
        if value not in resolved:
            resolved.append(value)
    if not resolved:
        raise ValueError("ADX windows must not be empty.")
    return resolved


def compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.DataFrame:
    """
    Compute the ``compute_adx`` feature value.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: compute_adx
            params:
              high: <required>
              low: <required>
              close: <required>
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
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``14``.
    """
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    tr = compute_true_range(high, low, close)
    atr = tr.ewm(alpha=1 / window, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1 / window, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / window, adjust=False).mean() / atr)
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    adx = dx.ewm(alpha=1 / window, adjust=False).mean()

    return pd.DataFrame(
        {
            f"plus_di_{window}": plus_di,
            f"minus_di_{window}": minus_di,
            f"adx_{window}": adx,
        }
    )

__all__ = ["compute_adx", "add_adx_features"]
