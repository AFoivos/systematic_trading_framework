from __future__ import annotations

import pandas as pd

from ._ehlers import as_float_array, compute_decycler, require_columns, resolve_output_col, validate_int


def add_decycler(
    df: pd.DataFrame,
    price_col: str = "close",
    period: int = 60,
    output_col: str | None = None,
) -> pd.DataFrame:
    """Add Ehlers' causal decycler trend filter."""
    require_columns(df, [price_col], feature="Decycler")
    resolved_period = validate_int(period, name="period", minimum=3)
    col = resolve_output_col(output_col, f"decycler_{resolved_period}")

    out = df.copy()
    out[col] = compute_decycler(as_float_array(out[price_col]), period=resolved_period)
    return out


__all__ = ["add_decycler"]
