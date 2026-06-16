from __future__ import annotations

import pandas as pd

from ._ehlers import as_float_array, compute_mesa_components, require_columns, resolve_output_col


def add_dominant_cycle_phase(
    df: pd.DataFrame,
    price_col: str = "close",
    output_col: str | None = None,
) -> pd.DataFrame:
    """Add Ehlers' causal dominant cycle phase estimate in degrees."""
    require_columns(df, [price_col], feature="dominant cycle phase")
    col = resolve_output_col(output_col, "dominant_cycle_phase")

    out = df.copy()
    components = compute_mesa_components(as_float_array(out[price_col]))
    out[col] = components["phase"]
    return out


__all__ = ["add_dominant_cycle_phase"]
