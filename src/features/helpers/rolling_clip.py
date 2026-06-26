from __future__ import annotations

import numpy as np
import pandas as pd

from .common import non_negative_int, output_column, positive_int, probability, resolve_configured_column


def compute_rolling_clip(
    series: pd.Series,
    *,
    window: int = 2520,
    lower_q: float = 0.01,
    upper_q: float = 0.99,
    shift: int = 1,
) -> pd.Series:
    """
    Compute the ``rolling_clip`` feature helper value.
    
    This feature helper uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        transforms:
          rolling_clip:
            params:
              window: 2520
              lower_q: 0.01
              upper_q: 0.99
              shift: 1
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    window:
        Trailing lookback or forecast horizon controlling this feature helper. Default: ``2520``.
    lower_q:
        Numeric threshold used by this feature helper. Default: ``0.01``.
    upper_q:
        Numeric threshold used by this feature helper. Default: ``0.99``.
    shift:
        Configuration parameter accepted by this feature helper. Default: ``1``.
    """
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    resolved_window = positive_int(window, field="window")
    if resolved_window <= 1:
        raise ValueError("window must be > 1.")
    resolved_shift = non_negative_int(shift, field="shift")
    q_low = probability(lower_q, field="lower_q")
    q_high = probability(upper_q, field="upper_q")
    if not q_low < q_high:
        raise ValueError("lower_q must be < upper_q.")

    lower = series.rolling(resolved_window, min_periods=resolved_window).quantile(q_low).shift(resolved_shift)
    upper = series.rolling(resolved_window, min_periods=resolved_window).quantile(q_high).shift(resolved_shift)
    valid_bounds = lower.notna() & upper.notna()
    out = pd.Series(np.nan, index=series.index, dtype="float32")
    if bool(valid_bounds.any()):
        out.loc[valid_bounds] = np.minimum(
            np.maximum(series.loc[valid_bounds].astype(float), lower.loc[valid_bounds].astype(float)),
            upper.loc[valid_bounds].astype(float),
        ).astype("float32")
    return out


def add_rolling_clip_transform(
    df: pd.DataFrame,
    *,
    source_col: str | None = None,
    source_selector: dict[str, object] | None = None,
    output_col: str | None = None,
    window: int = 2520,
    lower_q: float = 0.01,
    upper_q: float = 0.99,
    shift: int = 1,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``rolling_clip`` feature helper transformation.
    
    This feature helper uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        transforms:
          rolling_clip:
            params:
              source_col: null
              source_selector: null
              output_col: null
              window: 2520
              lower_q: 0.01
              upper_q: 0.99
              shift: 1
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
        Trailing lookback or forecast horizon controlling this feature helper. Default: ``2520``.
    lower_q:
        Numeric threshold used by this feature helper. Default: ``0.01``.
    upper_q:
        Numeric threshold used by this feature helper. Default: ``0.99``.
    shift:
        Configuration parameter accepted by this feature helper. Default: ``1``.
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
        field_prefix="rolling_clip",
    )
    col = output_column(output_col, default=f"{source}_rollclip_{int(window)}")
    out[col] = compute_rolling_clip(
        out[source].astype(float),
        window=int(window),
        lower_q=float(lower_q),
        upper_q=float(upper_q),
        shift=int(shift),
    )
    return out


__all__ = ["add_rolling_clip_transform", "compute_rolling_clip"]
