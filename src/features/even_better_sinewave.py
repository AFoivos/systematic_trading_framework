from __future__ import annotations

import numpy as np
import pandas as pd

from ._ehlers import EPSILON, as_float_array, compute_supersmoother, require_columns, resolve_output_col, validate_int


def add_even_better_sinewave(
    df: pd.DataFrame,
    price_col: str = "close",
    duration: int = 40,
    smoothing_period: int = 10,
    power_window: int = 3,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Apply the registered ``even_better_sinewave`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: even_better_sinewave
            params:
              price_col: close
              duration: 40
              smoothing_period: 10
              power_window: 3
              output_col: null
          output_cols:
            - configured by output_col
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    duration:
        Configuration parameter accepted by this feature. Default: ``40``.
    smoothing_period:
        Configuration parameter accepted by this feature. Default: ``10``.
    power_window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``3``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    """
    require_columns(df, [price_col], feature="Even Better Sinewave")
    resolved_duration = validate_int(duration, name="duration", minimum=4)
    resolved_smoothing = validate_int(smoothing_period, name="smoothing_period", minimum=2)
    resolved_power_window = validate_int(power_window, name="power_window", minimum=1)
    col = resolve_output_col(output_col, "even_better_sinewave")

    out = df.copy()
    values = as_float_array(out[price_col])
    high_pass = np.full(values.size, np.nan, dtype=float)
    hp_state = np.zeros(values.size, dtype=float)
    angle = 2.0 * np.pi / resolved_duration
    alpha = (1.0 - np.sin(angle)) / np.cos(angle)

    for idx in range(values.size):
        if idx == 0 or not np.isfinite(values[idx]) or not np.isfinite(values[idx - 1]):
            continue
        hp_state[idx] = 0.5 * (1.0 + alpha) * (values[idx] - values[idx - 1]) + alpha * hp_state[idx - 1]
        high_pass[idx] = hp_state[idx]

    filtered = compute_supersmoother(high_pass, period=resolved_smoothing)
    wave = np.full(values.size, np.nan, dtype=float)
    for idx in range(resolved_power_window - 1, values.size):
        sample = filtered[idx - resolved_power_window + 1 : idx + 1]
        if not np.isfinite(sample).all():
            continue
        numerator = float(np.mean(sample))
        power = float(np.mean(sample * sample))
        if power <= EPSILON:
            continue
        wave[idx] = numerator / np.sqrt(power)

    out[col] = np.clip(wave, -1.0, 1.0)
    return out


__all__ = ["add_even_better_sinewave"]
