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


def add_fisher_transform(
    df: pd.DataFrame,
    price_col: str = "close",
    window: int = 10,
    clip: float = 0.999,
    output_col: str | None = None,
    signal_col: str | None = None,
    add_signal: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``fisher_transform`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: fisher_transform
            params:
              price_col: close
              window: 10
              clip: 0.999
              output_col: null
              signal_col: null
              add_signal: false
            output_cols:
              - configured by output_col
              - configured by signal_col
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``10``.
    clip:
        Configuration parameter accepted by this feature. Default: ``0.999``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    signal_col:
        Deprecated helper-derived output. Use ``transforms.lag``.
    add_signal:
        Deprecated switch. Must remain false; use ``transforms.lag``.
    """
    require_columns(df, [price_col], feature="Fisher Transform")
    resolved_window = validate_int(window, name="window", minimum=2)
    clip_value = validate_float(clip, name="clip", minimum=0.1, maximum=0.999999)
    validate_bool(add_signal, name="add_signal")
    col = resolve_output_col(output_col, f"fisher_transform_{resolved_window}")
    if add_signal or signal_col is not None:
        raise ValueError(
            "Fisher signal output is helper-derived; use transforms.lag with "
            "source_col set to the raw Fisher output."
        )

    out = df.copy()
    values = as_float_array(out[price_col])
    smoothed = np.zeros(values.size, dtype=float)
    fisher = np.full(values.size, np.nan, dtype=float)

    for idx in range(values.size):
        min_max = rolling_min_max(values, idx=idx, window=resolved_window)
        if min_max is None:
            continue
        low, high = min_max
        raw = normalize_to_unit_interval(values[idx], low, high)
        previous_smoothed = smoothed[idx - 1] if idx > 0 else 0.0
        smoothed[idx] = np.clip(0.33 * raw + 0.67 * previous_smoothed, -clip_value, clip_value)
        previous_fisher = fisher[idx - 1] if idx > 0 and np.isfinite(fisher[idx - 1]) else 0.0
        fisher[idx] = 0.5 * np.log((1.0 + smoothed[idx]) / (1.0 - smoothed[idx])) + 0.5 * previous_fisher

    out[col] = fisher
    return out


__all__ = ["add_fisher_transform"]
