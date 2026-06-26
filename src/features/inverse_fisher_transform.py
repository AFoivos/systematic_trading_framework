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
    Apply the registered ``inverse_fisher_transform`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: inverse_fisher_transform
            params:
              input_col: close
              window: 10
              scale: 1.0
              normalize: true
              output_col: null
          output_cols:
            - configured by output_col
    
    Required input columns
    ----------------------
    input_col:
        Input dataframe column configured by ``input_col``. Default: ``close``.
    
    Parameters
    ----------
    input_col:
        Input dataframe column configured by ``input_col``. Default: ``close``.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``10``.
    scale:
        Configuration parameter accepted by this feature. Default: ``1.0``.
    normalize:
        Configuration parameter accepted by this feature. Default: ``true``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
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
