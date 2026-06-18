from __future__ import annotations

import numpy as np
import pandas as pd

from ._ehlers import EPSILON, as_float_array, require_columns, resolve_output_col, validate_int


def add_center_of_gravity(
    df: pd.DataFrame,
    price_col: str = "close",
    window: int = 10,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Add Ehlers' causal Center of Gravity oscillator.

    YAML declaration::

        features:
          - step: center_of_gravity
            params: {}
    """
    require_columns(df, [price_col], feature="Center of Gravity")
    resolved_window = validate_int(window, name="window", minimum=2)
    col = resolve_output_col(output_col, f"center_of_gravity_{resolved_window}")

    out = df.copy()
    values = as_float_array(out[price_col])
    cog = np.full(values.size, np.nan, dtype=float)
    weights = np.arange(1.0, resolved_window + 1.0)

    for idx in range(resolved_window - 1, values.size):
        sample = values[idx - resolved_window + 1 : idx + 1]
        if not np.isfinite(sample).all():
            continue
        ordered = sample[::-1]
        denominator = float(np.sum(ordered))
        if abs(denominator) <= EPSILON:
            continue
        cog[idx] = -float(np.dot(weights, ordered)) / denominator

    out[col] = cog
    return out


__all__ = ["add_center_of_gravity"]
