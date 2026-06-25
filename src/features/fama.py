from __future__ import annotations

import pandas as pd

from ._ehlers import as_float_array, compute_mesa_components, require_columns, resolve_output_col, validate_mama_limits


def add_fama(
    df: pd.DataFrame,
    price_col: str = "close",
    fast_limit: float = 0.5,
    slow_limit: float = 0.05,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Add John Ehlers' causal Following Adaptive Moving Average.
    
    FAMA is the slower companion line of MAMA. It adapts to market phase
    changes using the same MESA components and is commonly used together
    with MAMA for adaptive trend/crossover logic.
    
    YAML declaration::
    
        features:
          - step: fama
            params:
              price_col: close
              fast_limit: 0.5
              slow_limit: 0.05
              output_col: fama
            output_cols:
              - fama
    
    Required input columns
    ----------------------
    fama:
        Required dataframe column read directly by this component.
    price_col:
        Input column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input price column used for the FAMA calculation.
    fast_limit:
        Maximum adaptive smoothing limit used by the MESA calculation.
    slow_limit:
        Minimum adaptive smoothing limit used by the MESA calculation.
    output_col:
        Output column for the Following Adaptive Moving Average.
    """

    require_columns(df, [price_col], feature="FAMA")
    validate_mama_limits(fast_limit, slow_limit)
    col = resolve_output_col(output_col, "fama")

    out = df.copy()
    components = compute_mesa_components(as_float_array(out[price_col]), fast_limit=fast_limit, slow_limit=slow_limit)
    out[col] = components["fama"]
    return out


__all__ = ["add_fama"]
