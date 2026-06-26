from __future__ import annotations

import numpy as np
import pandas as pd

from .common import non_negative_int, output_column, positive_int, resolve_configured_column


def compute_rms(series: pd.Series, *, window: int = 48, shift: int = 0) -> pd.Series:
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
