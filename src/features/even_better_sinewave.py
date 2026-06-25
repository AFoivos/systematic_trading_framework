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
    Add Ehlers' causal Even Better Sinewave oscillator.
    
    YAML declaration::
    
        features:
          - step: even_better_sinewave
            params: {}
    
    Required input columns
    ----------------------
    price_col:
        Input column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column name consumed by the component. Default: ``close``.
    duration:
        Configuration value used by the registered component. Default: ``40``.
    smoothing_period:
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``10``.
    power_window:
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``3``.
    output_col:
        Output column name emitted by the component. Default: ``None``.
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
