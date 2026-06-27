from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.helpers.common import output_column, require_columns

from ._common import clean_numeric, finite_non_negative


def add_atr_scaled_distance_features(
    df: pd.DataFrame,
    *,
    base_col: str,
    ref_col: str,
    atr_col: str,
    output_col: str | None = None,
    eps: float = 1e-12,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``atr_scaled_distance`` normalization helper transformation.
    """
    require_columns(df, [base_col, ref_col, atr_col], owner="ATR-scaled distance normalization")
    resolved_eps = finite_non_negative(eps, field="eps")
    out = df if inplace else df.copy()
    base = clean_numeric(out[base_col])
    ref = clean_numeric(out[ref_col])
    atr = clean_numeric(out[atr_col])
    col = output_column(output_col, default=f"{base_col}_minus_{ref_col}_over_{atr_col}")
    out[col] = ((base - ref) / atr.where(atr.abs() > resolved_eps, np.nan)).astype("float32")
    return out


__all__ = ["add_atr_scaled_distance_features"]
