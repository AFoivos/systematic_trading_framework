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
    add_distance: bool = True,
    inplace: bool = False,
) -> pd.DataFrame:
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

    for resolved_window in _resolve_windows(window=window, windows=windows):
        vwap = compute_vwap(typical_price, volume, window=resolved_window)
        out[f"vwap_{resolved_window}"] = vwap
        if add_distance:
            out[f"{close_col}_over_vwap_{resolved_window}"] = close / vwap - 1.0
    return out


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
