from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from src.features.technical.atr import compute_atr


def add_support_resistance_features(
    df: pd.DataFrame,
    *,
    price_col: str = "close",
    high_col: str = "high",
    low_col: str = "low",
    windows: Sequence[int] = (24, 72, 168),
    atr_col: str | None = None,
    atr_window: int = 24,
    include_pct_distance: bool = True,
    include_atr_distance: bool = True,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Add point-in-time safe rolling support and resistance levels.

    Support is defined as the rolling minimum of `low_col` over each window.
    Resistance is defined as the rolling maximum of `high_col` over each window.
    Distances are computed relative to the current `price_col` and optionally normalized by ATR.
    """
    missing = [col for col in (price_col, high_col, low_col) if col not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for support_resistance: {missing}")
    if not isinstance(windows, Sequence) or isinstance(windows, (str, bytes)) or len(windows) == 0:
        raise ValueError("windows must be a non-empty sequence of positive integers.")

    normalized_windows: list[int] = []
    for raw_window in windows:
        if isinstance(raw_window, bool) or not isinstance(raw_window, int) or raw_window <= 0:
            raise ValueError("support_resistance windows must be positive integers.")
        normalized_windows.append(int(raw_window))

    out = df if inplace else df.copy()
    price = out[price_col].astype(float)
    high = out[high_col].astype(float)
    low = out[low_col].astype(float)

    atr_series: pd.Series | None = None
    if include_atr_distance:
        if atr_col is not None:
            if atr_col not in out.columns:
                raise KeyError(
                    f"support_resistance atr_col '{atr_col}' not found in DataFrame. "
                    "Provide an existing ATR column or omit atr_col to use atr_window fallback."
                )
            atr_series = out[atr_col].astype(float)
        else:
            atr_series = compute_atr(high, low, price, window=int(atr_window), method="wilder").astype(float)
        atr_series = atr_series.where(atr_series > 0.0, other=np.nan)

    for window in normalized_windows:
        support_col = f"support_{window}"
        resistance_col = f"resistance_{window}"
        support = low.rolling(window=window, min_periods=window).min().astype(float)
        resistance = high.rolling(window=window, min_periods=window).max().astype(float)
        out[support_col] = support
        out[resistance_col] = resistance

        if include_pct_distance:
            out[f"support_distance_pct_{window}"] = ((price / support) - 1.0).astype("float32")
            out[f"resistance_distance_pct_{window}"] = ((resistance / price) - 1.0).astype("float32")

        if include_atr_distance and atr_series is not None:
            out[f"support_distance_atr_{window}"] = ((price - support) / atr_series).astype("float32")
            out[f"resistance_distance_atr_{window}"] = ((resistance - price) / atr_series).astype("float32")

    return out


__all__ = ["add_support_resistance_features"]
