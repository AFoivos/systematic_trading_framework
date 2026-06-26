from __future__ import annotations

import numpy as np
import pandas as pd

from .common import non_negative_int, output_column, positive_int, resolve_configured_column


def compute_rolling_zscore(
    series: pd.Series,
    *,
    window: int = 2520,
    shift: int = 1,
    ddof: int = 0,
) -> pd.Series:
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    resolved_window = positive_int(window, field="window")
    if resolved_window <= 1:
        raise ValueError("window must be > 1.")
    resolved_shift = non_negative_int(shift, field="shift")
    resolved_ddof = non_negative_int(ddof, field="ddof")

    base = series.astype(float)
    roll_mean = base.rolling(resolved_window, min_periods=resolved_window).mean().shift(resolved_shift)
    roll_std = base.rolling(resolved_window, min_periods=resolved_window).std(ddof=resolved_ddof).shift(resolved_shift)
    out = (base - roll_mean) / roll_std.replace(0.0, np.nan)
    out.name = series.name
    return out.astype("float32")


def add_rolling_zscore_transform(
    df: pd.DataFrame,
    *,
    source_col: str | None = None,
    source_selector: dict[str, object] | None = None,
    output_col: str | None = None,
    window: int = 2520,
    shift: int = 1,
    ddof: int = 0,
    inplace: bool = False,
) -> pd.DataFrame:
    out = df if inplace else df.copy()
    cfg = {"source_col": source_col, "source_selector": source_selector}
    source = resolve_configured_column(
        out,
        cfg,
        col_key="source_col",
        selector_key="source_selector",
        field_prefix="rolling_zscore",
    )
    resolved_window = int(window)
    col = output_column(output_col, default=f"{source}_zscore_{resolved_window}")
    out[col] = compute_rolling_zscore(out[source], window=resolved_window, shift=int(shift), ddof=int(ddof))
    return out


__all__ = ["add_rolling_zscore_transform", "compute_rolling_zscore"]
