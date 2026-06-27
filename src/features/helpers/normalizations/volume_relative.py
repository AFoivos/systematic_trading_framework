from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.helpers.common import output_column, positive_int, require_columns

from ._common import clean_numeric, finite_non_negative, optional_min_periods


def add_volume_relative_features(
    df: pd.DataFrame,
    *,
    volume_col: str = "volume",
    window: int = 96,
    min_periods: int | None = None,
    output_col: str | None = None,
    zscore_col: str | None = None,
    shift_stats: bool = True,
    eps: float = 1e-12,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``volume_relative`` normalization helper transformation.

    The default output is ``volume / rolling_mean(volume)``. A shifted z-score is
    emitted only when ``zscore_col`` is provided.
    """
    require_columns(df, [volume_col], owner="relative-volume normalization")
    resolved_window = positive_int(window, field="window")
    if resolved_window <= 1:
        raise ValueError("window must be > 1.")
    resolved_min_periods = optional_min_periods(min_periods, window=resolved_window)
    resolved_eps = finite_non_negative(eps, field="eps")

    out = df if inplace else df.copy()
    volume = clean_numeric(out[volume_col])
    mean = volume.rolling(resolved_window, min_periods=resolved_min_periods).mean()
    std = volume.rolling(resolved_window, min_periods=resolved_min_periods).std(ddof=0)
    if shift_stats:
        mean = mean.shift(1)
        std = std.shift(1)
    col = output_column(output_col, default=f"{volume_col}_relative_{resolved_window}")
    out[col] = (volume / mean.where(mean.abs() > resolved_eps, np.nan)).astype("float32")
    if zscore_col is not None:
        out[output_column(zscore_col, default=f"{volume_col}_zscore_{resolved_window}", field="zscore_col")] = (
            (volume - mean) / std.where(std.abs() > resolved_eps, np.nan)
        ).astype("float32")
    return out


__all__ = ["add_volume_relative_features"]
