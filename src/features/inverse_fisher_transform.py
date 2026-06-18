from __future__ import annotations

import numpy as np
import pandas as pd

from ._ehlers import (
    as_float_array,
    normalize_to_unit_interval,
    require_columns,
    resolve_output_col,
    rolling_min_max,
    validate_bool,
    validate_float,
    validate_int,
)


def add_inverse_fisher_transform(
    df: pd.DataFrame,
    input_col: str = "close",
    window: int = 10,
    scale: float = 1.0,
    normalize: bool = True,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Add a causal inverse Fisher transform bounded between -1 and 1.

    YAML declaration::

        features:
          - step: inverse_fisher_transform
            params: {}
    """
    require_columns(df, [input_col], feature="inverse Fisher Transform")
    resolved_window = validate_int(window, name="window", minimum=2)
    resolved_scale = validate_float(scale, name="scale", minimum=0.0)
    normalize_input = validate_bool(normalize, name="normalize")
    col = resolve_output_col(output_col, f"inverse_fisher_transform_{resolved_window}")

    out = df.copy()
    values = as_float_array(out[input_col])
    transformed = np.full(values.size, np.nan, dtype=float)

    for idx in range(values.size):
        if not np.isfinite(values[idx]):
            continue
        if normalize_input:
            min_max = rolling_min_max(values, idx=idx, window=resolved_window)
            if min_max is None:
                continue
            low, high = min_max
            value = normalize_to_unit_interval(values[idx], low, high) * resolved_scale
        else:
            value = values[idx] * resolved_scale
        transformed[idx] = np.tanh(value)

    out[col] = transformed
    return out


__all__ = ["add_inverse_fisher_transform"]
