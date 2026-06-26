from __future__ import annotations

import pandas as pd

from ._ehlers import as_float_array, compute_mesa_components, require_columns, resolve_output_col, validate_mama_limits


def add_mama(
    df: pd.DataFrame,
    price_col: str = "close",
    fast_limit: float = 0.5,
    slow_limit: float = 0.05,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Apply the registered ``mama`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: mama
            params:
              price_col: close
              fast_limit: 0.5
              slow_limit: 0.05
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
    fast_limit:
        Configuration parameter accepted by this feature. Default: ``0.5``.
    slow_limit:
        Configuration parameter accepted by this feature. Default: ``0.05``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    """
    require_columns(df, [price_col], feature="MAMA")
    validate_mama_limits(fast_limit, slow_limit)
    col = resolve_output_col(output_col, "mama")

    out = df.copy()
    components = compute_mesa_components(as_float_array(out[price_col]), fast_limit=fast_limit, slow_limit=slow_limit)
    out[col] = components["mama"]
    return out


__all__ = ["add_mama"]
