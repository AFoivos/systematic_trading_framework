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
    
    YAML declaration::
    
        features:
          - step: roc
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
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``(10, 20)``.
    window:
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``None``.
    output_col:
        Output column name emitted by the component. Default: ``None``.
    inplace:
        Configuration value used by the registered component. Default: ``False``.
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
