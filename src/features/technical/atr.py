from __future__ import annotations

from typing import Sequence

import pandas as pd

from .true_range import compute_true_range


def add_atr_features(
    df: pd.DataFrame,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    window: int = 14,
    windows: Sequence[int] | None = None,
    method: str = "wilder",
    add_over_price: bool = False,
    atr_col: str | None = None,
    over_price_col: str | None = None,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``atr`` feature transformation.
    
    YAML declaration::
    
        features:
          - step: atr
            params: {}
    
    Required input columns
    ----------------------
    high_col:
        Input column configured by ``high_col``. Default: ``high``.
    low_col:
        Input column configured by ``low_col``. Default: ``low``.
    close_col:
        Input column configured by ``close_col``. Default: ``close``.
    
    Parameters
    ----------
    high_col:
        Input dataframe column name consumed by the component. Default: ``high``.
    low_col:
        Input dataframe column name consumed by the component. Default: ``low``.
    close_col:
        Input dataframe column name consumed by the component. Default: ``close``.
    window:
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``14``.
    windows:
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``None``.
    method:
        Mode selector that controls the registered component behavior. Default: ``wilder``.
    add_over_price:
        No longer supported. Derived price-normalized ATR output must be
        declared with a nested normalization/transform helper. Default:
        ``False``.
    atr_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    over_price_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    inplace:
        Configuration value used by the registered component. Default: ``False``.
    """
    missing = [c for c in (high_col, low_col, close_col) if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for ATR features: {missing}")
    out = df if inplace else df.copy()
    high = out[high_col].astype(float)
    low = out[low_col].astype(float)
    close = out[close_col].astype(float)
    resolved_windows = _resolve_windows(window=window, windows=windows)
    _validate_stable_output_cols(
        resolved_windows=resolved_windows,
        add_over_price=add_over_price,
        atr_col=atr_col,
        over_price_col=over_price_col,
    )
    for resolved_window in resolved_windows:
        atr = compute_atr(high, low, close, window=resolved_window, method=method)
        out[atr_col or f"atr_{resolved_window}"] = atr
    return out


def _validate_stable_output_cols(
    *,
    resolved_windows: Sequence[int],
    add_over_price: bool,
    atr_col: str | None,
    over_price_col: str | None,
) -> None:
    for field_name, value in (("atr_col", atr_col), ("over_price_col", over_price_col)):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"{field_name} must be a non-empty string when provided.")
    if atr_col is not None and atr_col == over_price_col:
        raise ValueError("ATR output columns must be unique.")
    if len(resolved_windows) != 1 and atr_col is not None:
        raise ValueError("Stable ATR output columns require exactly one resolved window.")
    if add_over_price or over_price_col is not None:
        raise ValueError("ATR over-price outputs are no longer supported; use transforms.ratio helpers.")


def _resolve_windows(*, window: int, windows: Sequence[int] | None) -> list[int]:
    raw_windows = list(windows) if windows is not None else [window]
    resolved: list[int] = []
    for raw_window in raw_windows:
        if isinstance(raw_window, bool) or int(raw_window) <= 0:
            raise ValueError("ATR windows must be positive integers.")
        value = int(raw_window)
        if value not in resolved:
            resolved.append(value)
    if not resolved:
        raise ValueError("ATR windows must not be empty.")
    return resolved


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 14,
    method: str = "wilder",
) -> pd.Series:
    tr = compute_true_range(high, low, close)
    if method == "wilder":
        atr = tr.ewm(alpha=1 / window, adjust=False).mean()
    elif method == "simple":
        atr = tr.rolling(window=window, min_periods=window).mean()
    else:
        raise ValueError("method must be 'wilder' or 'simple'")
    atr.name = f"atr_{window}"
    return atr

__all__ = ["compute_atr", "add_atr_features"]
