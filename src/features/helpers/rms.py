from __future__ import annotations

import numpy as np
import pandas as pd

from .common import non_negative_int, output_column, positive_int, resolve_configured_column


def compute_rms(series: pd.Series, *, window: int = 48, shift: int = 0) -> pd.Series:
    """
    Compute the ``rms`` feature helper value.
    
    This feature helper uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        transforms:
          rms:
            params:
              window: 48
              shift: 0
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    window:
        Trailing lookback or forecast horizon controlling this feature helper. Default: ``48``.
    shift:
        Configuration parameter accepted by this feature helper. Default: ``0``.
    """
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    resolved_window = positive_int(window, field="window")
    resolved_shift = non_negative_int(shift, field="shift")
    source = pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
    out = source.pow(2).rolling(resolved_window, min_periods=resolved_window).mean().pow(0.5)
    if resolved_shift:
        out = out.shift(resolved_shift)
    out.name = f"{series.name}__root_mean_square"
    return out.astype("float32")


def add_rms_transform(
    df: pd.DataFrame,
    *,
    source_col: str | None = None,
    source_selector: dict[str, object] | None = None,
    output_col: str | None = None,
    output_prefix: str | None = None,
    window: int = 48,
    shift: int = 0,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``rms`` feature helper transformation.
    
    This feature helper uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        transforms:
          rms:
            params:
              source_col: null
              source_selector: null
              output_col: null
              output_prefix: null
              window: 48
              shift: 0
              inplace: false
          outputs:
            - configured by output_col
            - configured by output_prefix
    
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
    output_prefix:
        Configuration parameter accepted by this feature helper. Default: ``null``.
    window:
        Trailing lookback or forecast horizon controlling this feature helper. Default: ``48``.
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
        field_prefix="rms",
    )
    transformed = compute_rms(out[source], window=int(window), shift=int(shift))
    prefix = output_prefix if output_prefix is not None else source
    col = output_column(output_col, default=f"{prefix}__root_mean_square")
    out[col] = transformed
    return out


__all__ = ["add_rms_transform", "compute_rms"]
