from __future__ import annotations

from numbers import Real

import numpy as np
import pandas as pd

from .common import output_column, resolve_configured_column


def compute_product(left: pd.Series, right: pd.Series, *, scale: float = 1.0) -> pd.Series:
    """Multiply two index-aligned series and an optional finite scale."""
    if not isinstance(left, pd.Series) or not isinstance(right, pd.Series):
        raise TypeError("left and right must be pandas Series.")
    if isinstance(scale, bool) or not isinstance(scale, Real) or not np.isfinite(float(scale)):
        raise ValueError("scale must be a finite number.")
    lhs = pd.to_numeric(left, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
    rhs = pd.to_numeric(right, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
    out = lhs * rhs * float(scale)
    out.name = left.name
    return out.astype("float32")


def add_product_transform(
    df: pd.DataFrame, *, left_col: str | None = None,
    left_selector: dict[str, object] | None = None, right_col: str | None = None,
    right_selector: dict[str, object] | None = None, output_col: str | None = None,
    scale: float = 1.0, inplace: bool = False,
) -> pd.DataFrame:
    """Apply causal column-to-column multiplication.

    YAML declaration::

        transforms:
          product:
            items:
              - left_col: direction
                right_col: rsi_14
                output_col: dir_rsi_14

    Required input columns
    ----------------------
    left_col, right_col:
        Explicit columns or their matching selectors.

    Parameters
    ----------
    scale:
        Finite multiplier. Pandas index alignment and NaN propagation apply.
    """
    out = df if inplace else df.copy()
    cfg = {"left_col": left_col, "left_selector": left_selector,
           "right_col": right_col, "right_selector": right_selector}
    left_name = resolve_configured_column(out, cfg, col_key="left_col", selector_key="left_selector", field_prefix="product")
    right_name = resolve_configured_column(out, cfg, col_key="right_col", selector_key="right_selector", field_prefix="product")
    col = output_column(output_col, default=f"{left_name}_times_{right_name}")
    out[col] = compute_product(out[left_name], out[right_name], scale=scale)
    return out


__all__ = ["add_product_transform", "compute_product"]
