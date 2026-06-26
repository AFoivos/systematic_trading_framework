from __future__ import annotations

from numbers import Integral
from typing import Sequence

import pandas as pd


def add_roc_features(
    df: pd.DataFrame,
    price_col: str = "close",
    windows: Sequence[int] = (10, 20),
    window: int | None = None,
    output_col: str | None = None,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``roc`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: roc
            params:
              price_col: close
              windows: [10, 20]
              window: null
              output_col: null
              inplace: false
          output_cols:
            - configured by output_col
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    windows:
        Trailing lookback or forecast horizon controlling this feature. Default: ``[10, 20]``.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``null``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    """
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")
    out = df if inplace else df.copy()
    close = out[price_col].astype(float)
    resolved_windows = _resolve_windows(window=window, windows=windows)
    if output_col is not None:
        if len(resolved_windows) != 1:
            raise ValueError("output_col requires exactly one ROC window.")
        if not isinstance(output_col, str) or not output_col.strip():
            raise ValueError("output_col must be a non-empty string.")
    for resolved_window in resolved_windows:
        series = compute_roc(close, window=resolved_window)
        out[output_col or f"roc_{resolved_window}"] = series
    return out


def compute_roc(close: pd.Series, window: int = 10) -> pd.Series:
    """
    Compute the ``compute_roc`` feature value.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: compute_roc
            params:
              close: <required>
              window: 10
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    close:
        Configuration parameter accepted by this feature.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``10``.
    """
    _validate_window(window)
    roc = close / close.shift(window) - 1.0
    roc.name = f"roc_{window}"
    return roc


def _resolve_windows(*, window: int | None, windows: Sequence[int]) -> list[int]:
    raw_windows = [window] if window is not None else list(windows)
    resolved: list[int] = []
    for raw_window in raw_windows:
        _validate_window(raw_window)
        value = int(raw_window)
        if value not in resolved:
            resolved.append(value)
    if not resolved:
        raise ValueError("ROC windows must not be empty.")
    return resolved


def _validate_window(window: int | None) -> None:
    if isinstance(window, bool) or not isinstance(window, Integral) or int(window) <= 0:
        raise ValueError("ROC window must be a positive integer.")


__all__ = ["compute_roc", "add_roc_features"]
