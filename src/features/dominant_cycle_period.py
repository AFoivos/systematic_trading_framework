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
    
    Required input columns
    ----------------------
    smooth_period:
        Required dataframe column read directly by this component.
    price_col:
        Input column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column name consumed by the component. Default: ``close``.
    output_col:
        Output column name emitted by the component. Default: ``None``.
    """
    require_columns(df, [price_col], feature="dominant cycle period")
    col = resolve_output_col(output_col, "dominant_cycle_period")

    out = df.copy()
    components = compute_mesa_components(as_float_array(out[price_col]))
    out[col] = components["smooth_period"]
    return out


__all__ = ["add_dominant_cycle_period"]
