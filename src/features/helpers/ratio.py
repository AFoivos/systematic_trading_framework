from __future__ import annotations

import numpy as np
import pandas as pd

from .common import output_column, resolve_configured_column


def compute_ratio(
    numerator: pd.Series,
    denominator: pd.Series,
    *,
    eps: float = 1e-8,
    subtract: float = 0.0,
) -> pd.Series:
    if not isinstance(numerator, pd.Series):
        raise TypeError("numerator must be a pandas Series.")
    if not isinstance(denominator, pd.Series):
        raise TypeError("denominator must be a pandas Series.")
    denom = denominator.astype(float)
    out = numerator.astype(float) / denom.where(denom.abs() > float(eps), np.nan) - float(subtract)
    out.name = numerator.name
    return out.astype("float32")


def add_ratio_transform(
    df: pd.DataFrame,
    *,
    numerator_col: str | None = None,
    numerator_selector: dict[str, object] | None = None,
    denominator_col: str | None = None,
    denominator_selector: dict[str, object] | None = None,
    output_col: str | None = None,
    eps: float = 1e-8,
    subtract: float = 0.0,
    inplace: bool = False,
) -> pd.DataFrame:
    out = df if inplace else df.copy()
    cfg = {
        "numerator_col": numerator_col,
        "numerator_selector": numerator_selector,
        "denominator_col": denominator_col,
        "denominator_selector": denominator_selector,
    }
    numerator = resolve_configured_column(
        out,
        cfg,
        col_key="numerator_col",
        selector_key="numerator_selector",
        field_prefix="ratio",
    )
    denominator = resolve_configured_column(
        out,
        cfg,
        col_key="denominator_col",
        selector_key="denominator_selector",
        field_prefix="ratio",
    )
    col = output_column(output_col, default=f"{numerator}_over_{denominator}")
    out[col] = compute_ratio(out[numerator], out[denominator], eps=float(eps), subtract=float(subtract))
    return out


__all__ = ["add_ratio_transform", "compute_ratio"]
