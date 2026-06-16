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


def add_autocorrelation_periodogram(
    df: pd.DataFrame,
    price_col: str = "close",
    min_period: int = 10,
    max_period: int = 48,
    window: int = 96,
    output_col: str | None = None,
    power_col: str | None = None,
    add_power: bool = False,
) -> pd.DataFrame:
    """Add a causal autocorrelation periodogram dominant-period estimate."""
    require_columns(df, [price_col], feature="autocorrelation periodogram")
    min_p = validate_int(min_period, name="min_period", minimum=2)
    max_p = validate_int(max_period, name="max_period", minimum=2)
    resolved_window = validate_int(window, name="window", minimum=4)
    if min_p > max_p:
        raise ValueError("min_period must be less than or equal to max_period.")
    if resolved_window <= max_p:
        raise ValueError("window must be greater than max_period.")
    include_power = validate_bool(add_power, name="add_power")
    col = resolve_output_col(output_col, f"autocorrelation_periodogram_{min_p}_{max_p}")
    resolved_power_col = resolve_named_col(power_col, default=f"{col}_power", name="power_col")
    if include_power:
        ensure_unique_columns([col, resolved_power_col], feature="autocorrelation periodogram")

    out = df.copy()
    values = as_float_array(out[price_col])
    periods = np.arange(min_p, max_p + 1, dtype=float)
    dominant = np.full(values.size, np.nan, dtype=float)
    max_power = np.full(values.size, np.nan, dtype=float)

    for idx in range(resolved_window - 1, values.size):
        sample = values[idx - resolved_window + 1 : idx + 1]
        if not np.isfinite(sample).all():
            continue
        power_values = np.zeros(periods.size, dtype=float)
        for period_idx, period in enumerate(periods.astype(int)):
            first = sample[:-period]
            second = sample[period:]
            first = first - np.mean(first)
            second = second - np.mean(second)
            denominator = np.sqrt(np.sum(first * first) * np.sum(second * second))
            if denominator <= EPSILON:
                continue
            corr = float(np.sum(first * second) / denominator)
            power_values[period_idx] = max(corr, 0.0) ** 2
        total_power = float(np.sum(power_values))
        if total_power <= EPSILON:
            continue
        dominant[idx] = float(np.sum(periods * power_values) / total_power)
        max_power[idx] = float(np.max(power_values))

    out[col] = dominant
    if include_power:
        out[resolved_power_col] = max_power
    return out


__all__ = ["add_autocorrelation_periodogram"]
