from __future__ import annotations

from typing import Sequence

import pandas as pd

from .true_range import compute_true_range
from .wilder import wilder_smooth


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
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: atr
            params:
              high_col: high
              low_col: low
              close_col: close
              window: 14
              windows: null
              method: wilder
              add_over_price: false
              atr_col: null
              over_price_col: null
              inplace: false
            output_cols:
              - configured by atr_col
              - configured by over_price_col
    
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
    method:
        Configuration parameter accepted by this feature. Default: ``wilder``.
    add_over_price:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    atr_col:
        Output dataframe column configured by ``atr_col``. Default: ``null``.
    over_price_col:
        Output dataframe column configured by ``over_price_col``. Default: ``null``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
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
    """
    Compute the ``compute_atr`` feature value.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: compute_atr
            params:
              high: <required>
              low: <required>
              close: <required>
              window: 14
              method: wilder
    
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
    method:
        Configuration parameter accepted by this feature. Default: ``wilder``.
    """
    tr = compute_true_range(high, low, close)
    if method == "wilder":
        atr = wilder_smooth(tr, window=window)
    elif method == "simple":
        atr = tr.rolling(window=window, min_periods=window).mean()
    else:
        raise ValueError("method must be 'wilder' or 'simple'")
    atr.name = f"atr_{window}"
    return atr

__all__ = ["compute_atr", "add_atr_features"]
