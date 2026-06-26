from __future__ import annotations

import numpy as np
import pandas as pd

from .common import non_negative_int, output_column, positive_int, resolve_configured_column
from .rolling_sum import _resolve_min_periods


def compute_rolling_mean(
    series: pd.Series,
    *,
    window: int,
    min_periods: int | None = None,
    shift: int = 0,
) -> pd.Series:
    """
    Compute the ``rolling_mean`` feature helper value.

    YAML declaration::

        transforms:
          rolling_mean:
            params:
              window: 96

    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on the supplied Series directly.

    Parameters
    ----------
    window:
        Trailing rolling window length.
    min_periods:
        Minimum observations required inside the trailing window.
    shift:
        Optional shift applied after the rolling statistic is computed.
    """
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    resolved_window = positive_int(window, field="window")
    resolved_min_periods = _resolve_min_periods(min_periods, window=resolved_window)
    resolved_shift = non_negative_int(shift, field="shift")
    source = pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
    out = source.rolling(resolved_window, min_periods=resolved_min_periods).mean()
    if resolved_shift:
        out = out.shift(resolved_shift)
    out.name = f"{series.name}_rolling_mean_{resolved_window}"
    return out.astype("float32")


def add_rolling_mean_transform(
    df: pd.DataFrame,
    *,
    source_col: str | None = None,
    source_selector: dict[str, object] | None = None,
    output_col: str | None = None,
    window: int = 20,
    min_periods: int | None = None,
    shift: int = 0,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``rolling_mean`` feature helper transformation.

    YAML declaration::

        transforms:
          rolling_mean:
            params:
              source_col: vol
              window: 96
              output_col: vol_mean_96

    Required input columns
    ----------------------
    source_col:
        Input dataframe column configured by ``source_col``.

    Parameters
    ----------
    source_col:
        Input dataframe column to aggregate.
    source_selector:
        Column selector used when ``source_col`` is not provided.
    output_col:
        Output column for the rolling mean.
    window:
        Trailing rolling window length.
    min_periods:
        Minimum observations required inside the trailing window.
    shift:
        Optional shift applied after the rolling mean is computed.
    inplace:
        If true, mutate the supplied dataframe; otherwise copy it first.
    """
    out = df if inplace else df.copy()
    cfg = {"source_col": source_col, "source_selector": source_selector}
    source = resolve_configured_column(
        out,
        cfg,
        col_key="source_col",
        selector_key="source_selector",
        field_prefix="rolling_mean",
    )
    resolved_window = positive_int(window, field="window")
    col = output_column(output_col, default=f"{source}_rolling_mean_{resolved_window}")
    out[col] = compute_rolling_mean(
        out[source],
        window=resolved_window,
        min_periods=min_periods,
        shift=shift,
    )
    return out


__all__ = ["add_rolling_mean_transform", "compute_rolling_mean"]
