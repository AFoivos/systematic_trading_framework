from __future__ import annotations

import pandas as pd
import numpy as np

from src.features.helpers.common import output_column, positive_int, require_columns

from ._common import clean_numeric


def add_range_position_features(
    df: pd.DataFrame,
    *,
    value_col: str = "close",
    high_col: str = "high",
    low_col: str = "low",
    window: int = 20,
    output_col: str | None = None,
    clip: bool = True,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``range_position`` normalization helper transformation.

    Computes where ``value_col`` sits inside the trailing high-low range.
    """
    require_columns(df, [value_col, high_col, low_col], owner="range-position normalization")
    resolved_window = positive_int(window, field="window")
    if resolved_window <= 1:
        raise ValueError("window must be > 1.")
    out = df if inplace else df.copy()
    value = clean_numeric(out[value_col])
    high = clean_numeric(out[high_col]).rolling(resolved_window, min_periods=resolved_window).max()
    low = clean_numeric(out[low_col]).rolling(resolved_window, min_periods=resolved_window).min()
    position = (value - low) / (high - low).replace(0.0, np.nan)
    if clip:
        position = position.clip(lower=0.0, upper=1.0)
    col = output_column(output_col, default=f"{value_col}_range_position_{resolved_window}")
    out[col] = position.astype("float32")
    return out


__all__ = ["add_range_position_features"]
