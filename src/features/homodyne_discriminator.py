from __future__ import annotations

import pandas as pd

from ._ehlers import as_float_array, compute_mesa_components, require_columns, resolve_output_col, validate_bool


def add_homodyne_discriminator(
    df: pd.DataFrame,
    price_col: str = "close",
    use_smoothed_period: bool = False,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Apply the registered ``homodyne_discriminator`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: homodyne_discriminator
            params:
              price_col: close
              use_smoothed_period: false
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
    use_smoothed_period:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    """
    require_columns(df, [price_col], feature="homodyne discriminator")
    validate_bool(use_smoothed_period, name="use_smoothed_period")
    col = resolve_output_col(output_col, "homodyne_discriminator")

    out = df.copy()
    components = compute_mesa_components(as_float_array(out[price_col]))
    out[col] = components["smooth_period" if use_smoothed_period else "period"]
    return out


__all__ = ["add_homodyne_discriminator"]
