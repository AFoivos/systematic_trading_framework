from __future__ import annotations

import pandas as pd

from .common import non_negative_int, output_column, resolve_configured_column


def compute_lag(series: pd.Series, *, lag: int = 1) -> pd.Series:
    """
    Compute the ``lag`` feature helper value.

    YAML declaration::

        transforms:
          lag:
            params:
              lag: 1

    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on the supplied Series directly.

    Parameters
    ----------
    lag:
        Number of bars to shift the source series backward in time.
    """
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    resolved_lag = non_negative_int(lag, field="lag")
    out = series.shift(resolved_lag)
    out.name = f"{series.name}_lag_{resolved_lag}"
    return out


def add_lag_transform(
    df: pd.DataFrame,
    *,
    source_col: str | None = None,
    source_selector: dict[str, object] | None = None,
    output_col: str | None = None,
    lag: int = 1,
    prefix: str = "lag",
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``lag`` feature helper transformation.

    YAML declaration::

        transforms:
          lag:
            params:
              source_col: close
              lag: 1
              output_col: lag_close_1

    Required input columns
    ----------------------
    source_col:
        Input dataframe column configured by ``source_col``.

    Parameters
    ----------
    source_col:
        Input dataframe column to lag.
    source_selector:
        Column selector used when ``source_col`` is not provided.
    output_col:
        Output column for the lagged series.
    lag:
        Number of bars to shift the source series backward in time.
    prefix:
        Prefix used for the default output column name.
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
        field_prefix="lag",
    )
    resolved_lag = non_negative_int(lag, field="lag")
    col = output_column(output_col, default=f"{prefix}_{source}_{resolved_lag}")
    out[col] = compute_lag(out[source], lag=resolved_lag)
    return out


__all__ = ["add_lag_transform", "compute_lag"]
