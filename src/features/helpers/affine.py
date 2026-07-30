from __future__ import annotations

from numbers import Real

import numpy as np
import pandas as pd

from .common import output_column, resolve_configured_column


def _finite(value: float, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not np.isfinite(float(value)):
        raise ValueError(f"{field} must be a finite number.")
    return float(value)


def compute_affine(series: pd.Series, *, scale: float = 1.0, offset: float = 0.0) -> pd.Series:
    """Compute the row-local affine transform ``series * scale + offset``."""
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    values = pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
    out = values * _finite(scale, field="scale") + _finite(offset, field="offset")
    out.name = series.name
    return out.astype("float32")


def add_affine_transform(
    df: pd.DataFrame, *, source_col: str | None = None,
    source_selector: dict[str, object] | None = None, output_col: str | None = None,
    scale: float = 1.0, offset: float = 0.0, inplace: bool = False,
) -> pd.DataFrame:
    """Apply a causal affine transform.

    YAML declaration::

        transforms:
          affine:
            items:
              - source_col: close_rsi_14
                output_col: rsi_14
                scale: 0.04
                offset: -2.0

    Required input columns
    ----------------------
    source_col:
        Explicit column, or one column selected by ``source_selector``.

    Parameters
    ----------
    scale, offset:
        Finite constants. Output is float32 and uses only the value at t.
    """
    out = df if inplace else df.copy()
    source = resolve_configured_column(out, {"source_col": source_col, "source_selector": source_selector},
                                       col_key="source_col", selector_key="source_selector", field_prefix="affine")
    col = output_column(output_col, default=f"{source}_affine")
    out[col] = compute_affine(out[source], scale=scale, offset=offset)
    return out


__all__ = ["add_affine_transform", "compute_affine"]
