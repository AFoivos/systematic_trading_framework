from __future__ import annotations

import pandas as pd

from ._ehlers import as_float_array, compute_mesa_components, require_columns, resolve_output_col


def add_dominant_cycle_period(
    df: pd.DataFrame,
    price_col: str = "close",
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Add Ehlers' causal dominant cycle period estimate.

    YAML declaration::

        features:
          - step: dominant_cycle_period
            params: {}
    """
    require_columns(df, [price_col], feature="dominant cycle period")
    col = resolve_output_col(output_col, "dominant_cycle_period")

    out = df.copy()
    components = compute_mesa_components(as_float_array(out[price_col]))
    out[col] = components["smooth_period"]
    return out


__all__ = ["add_dominant_cycle_period"]
