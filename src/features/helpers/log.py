from __future__ import annotations

from numbers import Real

import numpy as np
import pandas as pd

from .common import output_column, resolve_configured_column


def _finite(value: float, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not np.isfinite(float(value)):
        raise ValueError(f"{field} must be a finite number.")
    return float(value)


def compute_log(series: pd.Series, *, offset: float = 0.0, eps: float = 1e-12) -> pd.Series:
    """Compute ``log(series + offset)`` with invalid-domain values mapped to NaN."""
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    resolved_offset = _finite(offset, field="offset")
    resolved_eps = _finite(eps, field="eps")
    if resolved_eps < 0.0:
        raise ValueError("eps must be >= 0.")
    values = pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
    shifted = values + resolved_offset
    result = np.log(shifted.where(shifted > resolved_eps))
    result.name = series.name
    return result.astype("float32")


def add_log_transform(
    df: pd.DataFrame, *, source_col: str | None = None,
    source_selector: dict[str, object] | None = None, output_col: str | None = None,
    offset: float = 0.0, eps: float = 1e-12, inplace: bool = False,
) -> pd.DataFrame:
    """Apply a causal logarithm transform.

    YAML declaration::

        transforms:
          log:
            items:
              - source_col: spread
                output_col: log_spread

    Required input columns
    ----------------------
    source_col:
        Explicit column, or one column selected by ``source_selector``.

    Parameters
    ----------
    offset, eps:
        Domain adjustment and lower valid-domain boundary. Values at or below
        ``eps`` after offset become NaN. The calculation uses only the row at t.
    """
    out = df if inplace else df.copy()
    source = resolve_configured_column(out, {"source_col": source_col, "source_selector": source_selector},
                                       col_key="source_col", selector_key="source_selector", field_prefix="log")
    col = output_column(output_col, default=f"log_{source}")
    out[col] = compute_log(out[source], offset=offset, eps=eps)
    return out


__all__ = ["add_log_transform", "compute_log"]
