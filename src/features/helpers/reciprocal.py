from __future__ import annotations

import numpy as np
import pandas as pd

from .common import output_column, resolve_configured_column


def compute_reciprocal(series: pd.Series, *, eps: float = 1e-12, use_abs: bool = False) -> pd.Series:
    """
    Compute the ``reciprocal`` feature helper value.

    YAML declaration::

        transforms:
          reciprocal:
            params:
              eps: 1e-12
              use_abs: true

    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on the supplied Series directly.

    Parameters
    ----------
    eps:
        Minimum denominator magnitude required before division.
    use_abs:
        If true, compute ``1 / abs(source)``.
    """
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    source = pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
    denominator = source.abs() if use_abs else source
    out = 1.0 / denominator.where(denominator.abs() > float(eps), np.nan)
    out.name = f"{series.name}_reciprocal"
    return out.astype("float32")


def add_reciprocal_transform(
    df: pd.DataFrame,
    *,
    source_col: str | None = None,
    source_selector: dict[str, object] | None = None,
    output_col: str | None = None,
    eps: float = 1e-12,
    use_abs: bool = False,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``reciprocal`` feature helper transformation.

    YAML declaration::

        transforms:
          reciprocal:
            params:
              source_col: hilbert_instantaneous_frequency_64
              use_abs: true
              output_col: hilbert_dominant_cycle_64

    Required input columns
    ----------------------
    source_col:
        Input dataframe column configured by ``source_col``.

    Parameters
    ----------
    source_col:
        Input dataframe column to invert.
    source_selector:
        Column selector used when ``source_col`` is not provided.
    output_col:
        Output column for the reciprocal values.
    eps:
        Minimum denominator magnitude required before division.
    use_abs:
        If true, compute ``1 / abs(source)``.
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
        field_prefix="reciprocal",
    )
    col = output_column(output_col, default=f"{source}_reciprocal")
    out[col] = compute_reciprocal(out[source], eps=float(eps), use_abs=bool(use_abs))
    return out


__all__ = ["add_reciprocal_transform", "compute_reciprocal"]
