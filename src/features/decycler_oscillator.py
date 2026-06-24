from __future__ import annotations

import numpy as np
import pandas as pd

from ._ehlers import EPSILON, as_float_array, compute_decycler, require_columns, resolve_output_col, validate_int


def add_decycler_oscillator(
    df: pd.DataFrame,
    price_col: str = "close",
    fast_period: int = 30,
    slow_period: int = 60,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Add a causal Ehlers decycler oscillator from fast and slow decyclers.

    The oscillator compares a fast decycler with a slow decycler and normalizes
    their difference by price. Positive values indicate that the faster
    decycled trend is above the slower decycled trend, while negative values
    indicate the opposite.

    YAML declaration::

        features:
          - step: decycler_oscillator
            params:
              price_col: close
              fast_period: 30
              slow_period: 60
              output_col: decycler_oscillator_30_60
            output_cols:
              - decycler_oscillator_30_60

    Parameters
    ----------
    price_col:
        Input price column used for the decycler oscillator calculation.
    fast_period:
        Period of the fast Ehlers decycler. Must be less than slow_period.
    slow_period:
        Period of the slow Ehlers decycler. Must be greater than fast_period.
    output_col:
        Output column for the decycler oscillator.
    """

    require_columns(df, [price_col], feature="Decycler Oscillator")
    fast = validate_int(fast_period, name="fast_period", minimum=3)
    slow = validate_int(slow_period, name="slow_period", minimum=3)
    if fast >= slow:
        raise ValueError("fast_period must be less than slow_period.")
    col = resolve_output_col(output_col, f"decycler_oscillator_{fast}_{slow}")

    out = df.copy()
    values = as_float_array(out[price_col])
    fast_decycler = compute_decycler(values, period=fast)
    slow_decycler = compute_decycler(values, period=slow)
    oscillator = np.full(values.size, np.nan, dtype=float)
    valid = np.isfinite(values) & (np.abs(values) > EPSILON) & np.isfinite(fast_decycler) & np.isfinite(slow_decycler)
    oscillator[valid] = 100.0 * (fast_decycler[valid] - slow_decycler[valid]) / values[valid]
    out[col] = oscillator
    return out


__all__ = ["add_decycler_oscillator"]
