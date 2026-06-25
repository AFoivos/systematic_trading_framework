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
    Add John Ehlers' causal MESA Adaptive Moving Average.
    
    YAML declaration::
    
        features:
          - step: mama
            params: {}
    
    Required input columns
    ----------------------
    mama:
        Required dataframe column read directly by this component.
    price_col:
        Input column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column name consumed by the component. Default: ``close``.
    fast_limit:
        Configuration value used by the registered component. Default: ``0.5``.
    slow_limit:
        Configuration value used by the registered component. Default: ``0.05``.
    output_col:
        Output column name emitted by the component. Default: ``None``.
    """
    require_columns(df, [price_col], feature="MAMA")
    validate_mama_limits(fast_limit, slow_limit)
    col = resolve_output_col(output_col, "mama")

    out = df.copy()
    components = compute_mesa_components(as_float_array(out[price_col]), fast_limit=fast_limit, slow_limit=slow_limit)
    out[col] = components["mama"]
    return out


__all__ = ["add_mama"]
