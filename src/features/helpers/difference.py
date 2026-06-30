from __future__ import annotations

import numpy as np
import pandas as pd

from .common import non_negative_int, output_column, require_columns, resolve_configured_column


def compute_difference(series: pd.Series, *, periods: int = 1) -> pd.Series:
    """
    Compute the ``difference`` feature helper value.

    YAML declaration::

        transforms:
          difference:
            params:
              periods: 3

    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on the supplied Series directly.

    Parameters
    ----------
    periods:
        Number of bars used for the lagged subtraction.
    """
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    resolved_periods = non_negative_int(periods, field="periods")
    source = pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
    out = source - source.shift(resolved_periods)
    out.name = f"{series.name}_diff_{resolved_periods}"
    return out.astype("float32")


def add_difference_transform(
    df: pd.DataFrame,
    *,
    source_col: str | None = None,
    source_selector: dict[str, object] | None = None,
    reference_col: str | None = None,
    output_col: str | None = None,
    periods: int = 1,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``difference`` feature helper transformation.

    YAML declaration::

        transforms:
          difference:
            params:
              source_col: roofing_filter_48_10
              periods: 3
              output_col: roofing_filter_48_10_slope

    Required input columns
    ----------------------
    source_col:
        Input dataframe column configured by ``source_col``.

    Parameters
    ----------
    source_col:
        Input dataframe column to subtract from its lagged value, or from
        ``reference_col`` when configured.
    source_selector:
        Column selector used when ``source_col`` is not provided.
    reference_col:
        Optional column to subtract from ``source_col`` at the same timestamp.
        When provided, ``periods`` is ignored.
    output_col:
        Output column for the difference.
    periods:
        Number of bars used for the lagged subtraction.
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
        field_prefix="difference",
    )
    if reference_col is not None:
        require_columns(out, [source, reference_col], owner="difference")
        col = output_column(output_col, default=f"{source}_minus_{reference_col}")
        left = pd.to_numeric(out[source], errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
        right = pd.to_numeric(out[reference_col], errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
        out[col] = (left - right).astype("float32")
        return out
    resolved_periods = non_negative_int(periods, field="periods")
    col = output_column(output_col, default=f"{source}_diff_{resolved_periods}")
    out[col] = compute_difference(out[source], periods=resolved_periods)
    return out


__all__ = ["add_difference_transform", "compute_difference"]
