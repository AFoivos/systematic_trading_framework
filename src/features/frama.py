from __future__ import annotations

import numpy as np
import pandas as pd

from ._ehlers import (
    EPSILON,
    as_float_array,
    ensure_unique_columns,
    require_columns,
    resolve_named_col,
    resolve_output_col,
    validate_bool,
    validate_int,
)


def add_frama(
    df: pd.DataFrame,
    price_col: str = "close",
    high_col: str = "high",
    low_col: str = "low",
    window: int = 16,
    fast_period: int = 4,
    slow_period: int = 300,
    output_col: str | None = None,
    alpha_col: str | None = None,
    fractal_dimension_col: str | None = None,
    add_diagnostics: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``frama`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: frama
            params:
              price_col: close
              high_col: high
              low_col: low
              window: 16
              fast_period: 4
              slow_period: 300
              output_col: null
              alpha_col: null
              fractal_dimension_col: null
              add_diagnostics: false
          output_cols:
            - configured by output_col
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    alpha_col:
        Input dataframe column configured by ``alpha_col``. Default: ``null``.
    fractal_dimension_col:
        Input dataframe column configured by ``fractal_dimension_col``. Default: ``null``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``16``.
    fast_period:
        Configuration parameter accepted by this feature. Default: ``4``.
    slow_period:
        Configuration parameter accepted by this feature. Default: ``300``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    alpha_col:
        Input dataframe column configured by ``alpha_col``. Default: ``null``.
    fractal_dimension_col:
        Input dataframe column configured by ``fractal_dimension_col``. Default: ``null``.
    add_diagnostics:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    """
    require_columns(df, [price_col, high_col, low_col], feature="FRAMA")
    resolved_window = validate_int(window, name="window", minimum=4)
    if resolved_window % 2 != 0:
        raise ValueError("window must be an even integer.")
    fast = validate_int(fast_period, name="fast_period", minimum=1)
    slow = validate_int(slow_period, name="slow_period", minimum=2)
    if fast >= slow:
        raise ValueError("fast_period must be less than slow_period.")
    diagnostics = validate_bool(add_diagnostics, name="add_diagnostics")
    col = resolve_output_col(output_col, f"frama_{resolved_window}")
    alpha_output = resolve_named_col(alpha_col, default=f"{col}_alpha", name="alpha_col")
    dimension_output = resolve_named_col(
        fractal_dimension_col,
        default=f"{col}_fractal_dimension",
        name="fractal_dimension_col",
    )
    if diagnostics:
        ensure_unique_columns([col, alpha_output, dimension_output], feature="FRAMA")

    out = df.copy()
    price = as_float_array(out[price_col])
    high = as_float_array(out[high_col])
    low = as_float_array(out[low_col])
    frama = np.full(price.size, np.nan, dtype=float)
    alpha_values = np.full(price.size, np.nan, dtype=float)
    dimensions = np.full(price.size, np.nan, dtype=float)

    half = resolved_window // 2
    fast_alpha = 2.0 / (fast + 1.0)
    slow_alpha = 2.0 / (slow + 1.0)
    previous = np.nan

    for idx in range(price.size):
        if not np.isfinite(price[idx]):
            continue
        if not np.isfinite(previous):
            previous = price[idx]
        if idx + 1 < resolved_window:
            frama[idx] = price[idx]
            previous = frama[idx]
            continue

        start = idx - resolved_window + 1
        high_window = high[start : idx + 1]
        low_window = low[start : idx + 1]
        if not np.isfinite(high_window).all() or not np.isfinite(low_window).all():
            continue

        n1 = (np.max(high_window[:half]) - np.min(low_window[:half])) / half
        n2 = (np.max(high_window[half:]) - np.min(low_window[half:])) / half
        n3 = (np.max(high_window) - np.min(low_window)) / resolved_window
        if n1 > EPSILON and n2 > EPSILON and n3 > EPSILON:
            dimension = (np.log(n1 + n2) - np.log(n3)) / np.log(2.0)
        else:
            dimension = 1.0
        alpha = float(np.exp(-4.6 * (dimension - 1.0)))
        alpha = min(fast_alpha, max(slow_alpha, alpha))

        current = alpha * price[idx] + (1.0 - alpha) * previous
        frama[idx] = current
        alpha_values[idx] = alpha
        dimensions[idx] = dimension
        previous = current

    out[col] = frama
    if diagnostics:
        out[alpha_output] = alpha_values
        out[dimension_output] = dimensions
    return out


__all__ = ["add_frama"]
