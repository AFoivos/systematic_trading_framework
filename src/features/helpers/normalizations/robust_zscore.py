from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.helpers.common import output_column, positive_int, require_columns

from ._common import clean_numeric, optional_min_periods, positive_float


def _median_abs_deviation(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    if values.size == 0:
        return float("nan")
    median = float(np.median(values))
    return float(np.median(np.abs(values - median)))


def add_robust_zscore_features(
    df: pd.DataFrame,
    *,
    source_col: str,
    window: int = 252,
    min_periods: int | None = None,
    output_col: str | None = None,
    shift_stats: bool = True,
    mad_scale: float = 1.4826,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``robust_zscore`` normalization helper transformation.

    Uses rolling median and rolling median absolute deviation. Stats are shifted
    by default so the current value is normalized against prior history.
    """
    require_columns(df, [source_col], owner="robust z-score normalization")
    resolved_window = positive_int(window, field="window")
    if resolved_window <= 1:
        raise ValueError("window must be > 1.")
    resolved_min_periods = optional_min_periods(min_periods, window=resolved_window)
    scale = positive_float(mad_scale, field="mad_scale")

    out = df if inplace else df.copy()
    source = clean_numeric(out[source_col])
    median = source.rolling(resolved_window, min_periods=resolved_min_periods).median()
    mad = source.rolling(resolved_window, min_periods=resolved_min_periods).apply(
        _median_abs_deviation,
        raw=True,
    )
    if shift_stats:
        median = median.shift(1)
        mad = mad.shift(1)
    col = output_column(output_col, default=f"{source_col}_robust_zscore_{resolved_window}")
    out[col] = ((source - median) / (mad * scale).replace(0.0, np.nan)).astype("float32")
    return out


__all__ = ["add_robust_zscore_features"]
