from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.helpers.common import output_column, require_columns

from ._common import clean_numeric, finite_non_negative


def add_volatility_scaled_return_features(
    df: pd.DataFrame,
    *,
    return_col: str,
    volatility_col: str,
    output_col: str | None = None,
    eps: float = 1e-12,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``volatility_scaled_return`` normalization helper transformation.
    """
    require_columns(df, [return_col, volatility_col], owner="volatility-scaled return normalization")
    resolved_eps = finite_non_negative(eps, field="eps")
    out = df if inplace else df.copy()
    returns = clean_numeric(out[return_col])
    vol = clean_numeric(out[volatility_col])
    col = output_column(output_col, default=f"{return_col}_over_{volatility_col}")
    out[col] = (returns / vol.where(vol.abs() > resolved_eps, np.nan)).astype("float32")
    return out


__all__ = ["add_volatility_scaled_return_features"]
