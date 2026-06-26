from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.helpers.common import require_columns


def add_rolling_zscore_features(
    df: pd.DataFrame,
    *,
    columns: list[str],
    window: int = 96,
    min_periods: int | None = None,
    shift_stats: bool = True,
    inplace: bool = False,
) -> pd.DataFrame:
    if isinstance(window, bool) or int(window) <= 1:
        raise ValueError("window must be > 1.")
    if min_periods is not None and (isinstance(min_periods, bool) or int(min_periods) <= 0):
        raise ValueError("min_periods must be a positive integer when provided.")

    require_columns(df, list(columns), owner="rolling z-score normalization")
    out = df if inplace else df.copy()
    resolved_window = int(window)
    resolved_min_periods = int(min_periods) if min_periods is not None else resolved_window

    for col in columns:
        x = out[col].astype(float)
        rolling_mean = x.rolling(resolved_window, min_periods=resolved_min_periods).mean()
        rolling_std = x.rolling(resolved_window, min_periods=resolved_min_periods).std()

        if shift_stats:
            rolling_mean = rolling_mean.shift(1)
            rolling_std = rolling_std.shift(1)

        out[f"{col}_zscore_{resolved_window}"] = (x - rolling_mean) / rolling_std.replace(0, np.nan)

    return out


__all__ = ["add_rolling_zscore_features"]
