from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


def add_vwap_features(
    df: pd.DataFrame,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    volume_col: str = "volume",
    window: int = 20,
    windows: Sequence[int] | None = None,
    add_distance: bool = False,
    vwap_col: str | None = None,
    distance_col: str | None = None,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``vwap`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: vwap
            params:
              high_col: high
              low_col: low
              close_col: close
              volume_col: volume
              window: 20
              windows: null
              add_distance: false
              vwap_col: null
              distance_col: null
              inplace: false
          output_cols:
            - configured by vwap_col
            - configured by distance_col
    
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
        Trailing lookback or forecast horizon controlling this feature. Default: ``20``.
    windows:
        Trailing lookback or forecast horizon controlling this feature. Default: ``null``.
    add_distance:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    vwap_col:
        Output dataframe column configured by ``vwap_col``. Default: ``null``.
    distance_col:
        Output dataframe column configured by ``distance_col``. Default: ``null``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    """
    missing = [c for c in (high_col, low_col, close_col, volume_col) if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for VWAP features: {missing}")

    out = df if inplace else df.copy()
    high = out[high_col].astype(float)
    low = out[low_col].astype(float)
    close = out[close_col].astype(float)
    volume = out[volume_col].astype(float)
    typical_price = (high + low + close) / 3.0
    typical_price.name = "typical_price"

    resolved_windows = _resolve_windows(window=window, windows=windows)
    _validate_stable_output_cols(
        resolved_windows=resolved_windows,
        add_distance=add_distance,
        vwap_col=vwap_col,
        distance_col=distance_col,
    )
    for resolved_window in resolved_windows:
        vwap = compute_vwap(typical_price, volume, window=resolved_window)
        out[vwap_col or f"vwap_{resolved_window}"] = vwap
    return out


def _validate_stable_output_cols(
    *,
    resolved_windows: Sequence[int],
    add_distance: bool,
    vwap_col: str | None,
    distance_col: str | None,
) -> None:
    for field_name, value in (("vwap_col", vwap_col), ("distance_col", distance_col)):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"{field_name} must be a non-empty string when provided.")
    if vwap_col is not None and vwap_col == distance_col:
        raise ValueError("VWAP output columns must be unique.")
    if len(resolved_windows) != 1 and vwap_col is not None:
        raise ValueError("Stable VWAP output columns require exactly one resolved window.")
    if add_distance or distance_col is not None:
        raise ValueError("VWAP distance outputs are no longer supported; use transforms.ratio helpers.")


def _resolve_windows(*, window: int, windows: Sequence[int] | None) -> list[int]:
    raw_windows = list(windows) if windows is not None else [window]
    resolved: list[int] = []
    for raw_window in raw_windows:
        if isinstance(raw_window, bool) or int(raw_window) <= 0:
            raise ValueError("VWAP windows must be positive integers.")
        value = int(raw_window)
        if value not in resolved:
            resolved.append(value)
    if not resolved:
        raise ValueError("VWAP windows must not be empty.")
    return resolved


def compute_vwap(price: pd.Series, volume: pd.Series, window: int = 20) -> pd.Series:
    """
    Compute the ``compute_vwap`` feature value.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: compute_vwap
            params:
              price: <required>
              volume: <required>
              window: 20
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    price:
        Configuration parameter accepted by this feature.
    volume:
        Configuration parameter accepted by this feature.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``20``.
    """
    if not isinstance(price, pd.Series) or not isinstance(volume, pd.Series):
        raise TypeError("price and volume must be pandas Series")
    if isinstance(window, bool) or int(window) <= 0:
        raise ValueError("VWAP window must be a positive integer.")

    resolved_window = int(window)
    price_float = price.astype(float)
    volume_float = volume.astype(float)
    dollar_volume = price_float * volume_float
    numerator = dollar_volume.rolling(window=resolved_window, min_periods=resolved_window).sum()
    denominator = volume_float.rolling(window=resolved_window, min_periods=resolved_window).sum()
    vwap = numerator / denominator.replace(0.0, np.nan)
    vwap.name = f"vwap_{resolved_window}"
    return vwap


__all__ = ["compute_vwap", "add_vwap_features"]
