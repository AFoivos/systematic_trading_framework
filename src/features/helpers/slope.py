from __future__ import annotations

import numpy as np
import pandas as pd

from .common import non_negative_int, output_column, positive_int, resolve_configured_column


def _linear_slope(values: np.ndarray) -> float:
    finite_mask = np.isfinite(values)
    if not bool(finite_mask.all()):
        return float("nan")
    x = np.arange(values.size, dtype=float)
    x = x - float(x.mean())
    y = values.astype(float) - float(values.mean())
    denom = float(np.dot(x, x))
    if denom == 0.0:
        return float("nan")
    return float(np.dot(x, y) / denom)


def compute_slope(series: pd.Series, *, window: int = 2, shift: int = 0) -> pd.Series:
    """
    Compute the ``slope`` feature helper value.
    
    This feature helper uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        transforms:
          slope:
            params:
              window: 2
              shift: 0
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    window:
        Trailing lookback or forecast horizon controlling this feature helper. Default: ``2``.
    shift:
        Configuration parameter accepted by this feature helper. Default: ``0``.
    """
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    resolved_window = positive_int(window, field="window")
    resolved_shift = non_negative_int(shift, field="shift")
    source = pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
    out = source.rolling(resolved_window, min_periods=resolved_window).apply(_linear_slope, raw=True)
    if resolved_shift:
        out = out.shift(resolved_shift)
    out.name = f"{series.name}__slope"
    return out.astype("float32")


def add_slope_transform(
    df: pd.DataFrame,
    *,
    source_col: str | None = None,
    source_selector: dict[str, object] | None = None,
    output_col: str | None = None,
    window: int = 2,
    shift: int = 0,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``slope`` feature helper transformation.
    
    This feature helper uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        transforms:
          slope:
            params:
              source_col: null
              source_selector: null
              output_col: null
              window: 2
              shift: 0
              inplace: false
          outputs:
            - configured by output_col
    
    Required input columns
    ----------------------
    source_col:
        Input dataframe column configured by ``source_col``. Default: ``null``.
    source_selector:
        Column selector used when the matching explicit column is not provided. Default: ``null``.
    
    Parameters
    ----------
    source_col:
        Input dataframe column configured by ``source_col``. Default: ``null``.
    source_selector:
        Column selector used when the matching explicit column is not provided. Default: ``null``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    window:
        Trailing lookback or forecast horizon controlling this feature helper. Default: ``2``.
    shift:
        Configuration parameter accepted by this feature helper. Default: ``0``.
    inplace:
        Boolean switch controlling optional feature helper behavior. Default: ``false``.
    """
    out = df if inplace else df.copy()
    cfg = {"source_col": source_col, "source_selector": source_selector}
    source = resolve_configured_column(
        out,
        cfg,
        col_key="source_col",
        selector_key="source_selector",
        field_prefix="slope",
    )
    transformed = compute_slope(out[source], window=int(window), shift=int(shift))
    col = output_column(output_col, default=f"{source}_slope_{int(window)}")
    out[col] = transformed
    return out


__all__ = ["add_slope_transform", "compute_slope"]
