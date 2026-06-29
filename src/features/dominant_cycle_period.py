from __future__ import annotations

import pandas as pd

from ._ehlers import as_float_array, compute_mesa_components, require_columns, resolve_output_col


def add_dominant_cycle_period(
    df: pd.DataFrame,
    price_col: str = "close",
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Apply the registered ``dominant_cycle_period`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: dominant_cycle_period
            params:
              price_col: close
              output_col: null
            output_cols:
              - configured by output_col
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    """
    require_columns(df, [price_col], feature="dominant cycle period")
    col = resolve_output_col(output_col, "dominant_cycle_period")

    out = df.copy()
    components = compute_mesa_components(as_float_array(out[price_col]))
    out[col] = components["smooth_period"]
    return out


__all__ = ["add_dominant_cycle_period"]
