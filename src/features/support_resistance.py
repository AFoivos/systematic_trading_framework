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
    Apply the registered ``support_resistance`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: support_resistance
            params:
              price_col: close
              high_col: high
              low_col: low
              windows: [24, 72, 168]
              atr_col: null
              atr_window: 24
              include_pct_distance: true
              include_atr_distance: true
              inplace: false
          output_cols:
            - configured by atr_col
    
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
    windows:
        Trailing lookback or forecast horizon controlling this feature. Default: ``[24, 72, 168]``.
    atr_col:
        Output dataframe column configured by ``atr_col``. Default: ``null``.
    atr_window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``24``.
    include_pct_distance:
        Configuration parameter accepted by this feature. Default: ``true``.
    include_atr_distance:
        Configuration parameter accepted by this feature. Default: ``true``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
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
