from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

from .common import output_column, resolve_configured_column


Comparison = Literal["gt", "ge", "lt", "le", "eq", "ne"]
Direction = Literal["up", "down"]


def compute_threshold_flag(
    series: pd.Series,
    *,
    threshold: float = 0.0,
    op: Comparison = "gt",
    use_abs: bool = False,
) -> pd.Series:
    """
    Compute the ``threshold_flag`` feature helper value.

    YAML declaration::

        transforms:
          threshold_flag:
            params:
              threshold: 0.0
              op: gt
              use_abs: false

    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on the supplied Series directly.

    Parameters
    ----------
    threshold:
        Numeric threshold used by the comparison.
    op:
        Comparison operator: ``gt``, ``ge``, ``lt``, ``le``, ``eq``, or ``ne``.
    use_abs:
        If true, compare the absolute value of the source series.
    """
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    source = pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
    comparable = source.abs() if use_abs else source
    resolved_threshold = float(threshold)
    if op == "gt":
        mask = comparable > resolved_threshold
    elif op == "ge":
        mask = comparable >= resolved_threshold
    elif op == "lt":
        mask = comparable < resolved_threshold
    elif op == "le":
        mask = comparable <= resolved_threshold
    elif op == "eq":
        mask = comparable == resolved_threshold
    elif op == "ne":
        mask = comparable != resolved_threshold
    else:
        raise ValueError("op must be one of: gt, ge, lt, le, eq, ne.")
    return (source.notna() & mask).astype("int8")


def compute_rising_flag(series: pd.Series, *, periods: int = 1) -> pd.Series:
    """
    Compute the ``rising_flag`` feature helper value.

    YAML declaration::

        transforms:
          rising_flag:
            params:
              periods: 1

    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on the supplied Series directly.

    Parameters
    ----------
    periods:
        Number of bars used for the lagged comparison.
    """
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    if isinstance(periods, bool) or not isinstance(periods, int) or periods <= 0:
        raise ValueError("periods must be a positive integer.")
    source = pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
    lagged = source.shift(int(periods))
    return (source.notna() & lagged.notna() & (source > lagged)).astype("int8")


def compute_between_flag(
    series: pd.Series,
    *,
    lower: float,
    upper: float,
    inclusive: Literal["both", "neither", "left", "right"] = "both",
) -> pd.Series:
    """
    Compute the ``between_flag`` feature helper value.

    YAML declaration::

        transforms:
          between_flag:
            params:
              lower: 10.0
              upper: 48.0
              inclusive: both

    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on the supplied Series directly.

    Parameters
    ----------
    lower:
        Lower bound for the range check.
    upper:
        Upper bound for the range check.
    inclusive:
        Boundary inclusion mode passed to pandas ``between``.
    """
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    low = float(lower)
    high = float(upper)
    if low > high:
        raise ValueError("lower must be <= upper.")
    source = pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
    return (source.notna() & source.between(low, high, inclusive=inclusive)).astype("int8")


def compute_crossing_flag(
    series: pd.Series,
    *,
    threshold: float = 0.0,
    direction: Direction = "up",
) -> pd.Series:
    """
    Compute the ``crossing_flag`` feature helper value.

    YAML declaration::

        transforms:
          crossing_flag:
            params:
              threshold: 0.0
              direction: up

    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on the supplied Series directly.

    Parameters
    ----------
    threshold:
        Numeric level used for the crossing event.
    direction:
        ``up`` for previous value <= threshold and current value > threshold;
        ``down`` for previous value >= threshold and current value < threshold.
    """
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    source = pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
    previous = source.shift(1)
    resolved_threshold = float(threshold)
    if direction == "up":
        mask = previous.le(resolved_threshold) & source.gt(resolved_threshold)
    elif direction == "down":
        mask = previous.ge(resolved_threshold) & source.lt(resolved_threshold)
    else:
        raise ValueError("direction must be 'up' or 'down'.")
    return (source.notna() & previous.notna() & mask).astype("int8")


def add_threshold_flag_transform(
    df: pd.DataFrame,
    *,
    source_col: str | None = None,
    source_selector: dict[str, object] | None = None,
    output_col: str | None = None,
    threshold: float = 0.0,
    op: Comparison = "gt",
    use_abs: bool = False,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``threshold_flag`` feature helper transformation.

    YAML declaration::

        transforms:
          threshold_flag:
            params:
              source_col: trend_slope_vol_ratio_96
              threshold: 1.0
              op: ge
              use_abs: true
              output_col: trend_slope_vol_ratio_96_strong

    Required input columns
    ----------------------
    source_col:
        Input dataframe column configured by ``source_col``.

    Parameters
    ----------
    source_col:
        Input dataframe column to compare.
    source_selector:
        Column selector used when ``source_col`` is not provided.
    output_col:
        Output binary flag column.
    threshold:
        Numeric threshold used by the comparison.
    op:
        Comparison operator: ``gt``, ``ge``, ``lt``, ``le``, ``eq``, or ``ne``.
    use_abs:
        If true, compare the absolute value of the source column.
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
        field_prefix="threshold_flag",
    )
    col = output_column(output_col, default=f"{source}_{op}_{float(threshold):g}")
    out[col] = compute_threshold_flag(out[source], threshold=float(threshold), op=op, use_abs=bool(use_abs))
    return out


def add_rising_flag_transform(
    df: pd.DataFrame,
    *,
    source_col: str | None = None,
    source_selector: dict[str, object] | None = None,
    output_col: str | None = None,
    periods: int = 1,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``rising_flag`` feature helper transformation.

    YAML declaration::

        transforms:
          rising_flag:
            params:
              source_col: rolling_r2_96
              output_col: rolling_r2_96_rising

    Required input columns
    ----------------------
    source_col:
        Input dataframe column configured by ``source_col``.

    Parameters
    ----------
    source_col:
        Input dataframe column to compare with its lagged value.
    source_selector:
        Column selector used when ``source_col`` is not provided.
    output_col:
        Output binary flag column.
    periods:
        Number of bars used for the lagged comparison.
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
        field_prefix="rising_flag",
    )
    col = output_column(output_col, default=f"{source}_rising")
    out[col] = compute_rising_flag(out[source], periods=periods)
    return out


def add_between_flag_transform(
    df: pd.DataFrame,
    *,
    source_col: str | None = None,
    source_selector: dict[str, object] | None = None,
    output_col: str | None = None,
    lower: float,
    upper: float,
    inclusive: Literal["both", "neither", "left", "right"] = "both",
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``between_flag`` feature helper transformation.

    YAML declaration::

        transforms:
          between_flag:
            params:
              source_col: hilbert_dominant_cycle_64
              lower: 10.0
              upper: 48.0
              output_col: hilbert_cycle_ok_64

    Required input columns
    ----------------------
    source_col:
        Input dataframe column configured by ``source_col``.

    Parameters
    ----------
    source_col:
        Input dataframe column to evaluate.
    source_selector:
        Column selector used when ``source_col`` is not provided.
    output_col:
        Output binary flag column.
    lower:
        Lower bound for the range check.
    upper:
        Upper bound for the range check.
    inclusive:
        Boundary inclusion mode passed to pandas ``between``.
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
        field_prefix="between_flag",
    )
    col = output_column(output_col, default=f"{source}_between_{float(lower):g}_{float(upper):g}")
    out[col] = compute_between_flag(out[source], lower=float(lower), upper=float(upper), inclusive=inclusive)
    return out


def add_crossing_flag_transform(
    df: pd.DataFrame,
    *,
    source_col: str | None = None,
    source_selector: dict[str, object] | None = None,
    output_col: str | None = None,
    threshold: float = 0.0,
    direction: Direction = "up",
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``crossing_flag`` feature helper transformation.

    YAML declaration::

        transforms:
          crossing_flag:
            params:
              source_col: roofing_filter_48_10
              threshold: 0.0
              direction: up
              output_col: roofing_filter_48_10_cross_up_zero

    Required input columns
    ----------------------
    source_col:
        Input dataframe column configured by ``source_col``.

    Parameters
    ----------
    source_col:
        Input dataframe column to evaluate for crossing events.
    source_selector:
        Column selector used when ``source_col`` is not provided.
    output_col:
        Output binary flag column.
    threshold:
        Numeric level used for the crossing event.
    direction:
        ``up`` or ``down`` crossing direction.
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
        field_prefix="crossing_flag",
    )
    col = output_column(output_col, default=f"{source}_cross_{direction}_{float(threshold):g}")
    out[col] = compute_crossing_flag(out[source], threshold=float(threshold), direction=direction)
    return out


__all__ = [
    "add_between_flag_transform",
    "add_crossing_flag_transform",
    "add_rising_flag_transform",
    "add_threshold_flag_transform",
    "compute_between_flag",
    "compute_crossing_flag",
    "compute_rising_flag",
    "compute_threshold_flag",
]
