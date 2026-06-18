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

    YAML declaration::

        features:
          - step: fama
            params: {}
    """
    require_columns(df, [price_col], feature="FAMA")
    validate_mama_limits(fast_limit, slow_limit)
    col = resolve_output_col(output_col, "fama")

    out = df.copy()
    components = compute_mesa_components(as_float_array(out[price_col]), fast_limit=fast_limit, slow_limit=slow_limit)
    out[col] = components["fama"]
    return out


__all__ = ["add_fama"]
