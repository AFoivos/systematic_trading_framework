from __future__ import annotations

import numpy as np
import pandas as pd

from src.signals._common import resolve_signal_output_name


def forecast_threshold_hysteresis_signal(
    df: pd.DataFrame,
    forecast_col: str = "pred_ret",
    signal_col: str | None = None,
    long_entry: float = 0.75,
    long_exit: float = 0.25,
    short_entry: float = -0.75,
    short_exit: float = -0.25,
    cooldown_bars: int = 0,
    min_holding_bars: int = 0,
) -> pd.Series:
    """
    Apply a stateful hysteresis threshold to regression forecasts.

    The transform is causal: each output only depends on forecasts observed up to
    the current row plus prior signal state.

    YAML declaration::

        signals:
          kind: forecast_threshold_hysteresis
          params:
            forecast_col: pred_ret
            signal_col: signal_forecast_hysteresis
            long_entry: 0.75
            long_exit: 0.25
            short_entry: -0.75
            short_exit: -0.25
            cooldown_bars: 0
            min_holding_bars: 0
            output_cols:
              - configured by signal_col

    Required input columns
    ----------------------
    forecast_col:
        Input dataframe column configured by ``forecast_col``. Default: ``pred_ret``.

    Parameters
    ----------
    forecast_col:
        Input dataframe column configured by ``forecast_col``. Default: ``pred_ret``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``null``.
    long_entry:
        Numeric threshold used by this signal. Default: ``0.75``.
    long_exit:
        Numeric threshold used by this signal. Default: ``0.25``.
    short_entry:
        Numeric threshold used by this signal. Default: ``-0.75``.
    short_exit:
        Numeric threshold used by this signal. Default: ``-0.25``.
    cooldown_bars:
        Configuration parameter accepted by this signal. Default: ``0``.
    min_holding_bars:
        Configuration parameter accepted by this signal. Default: ``0``.
    """
    if forecast_col not in df.columns:
        raise KeyError(f"forecast_col '{forecast_col}' not found in DataFrame")
    if not long_exit < long_entry:
        raise ValueError("long_exit must be < long_entry.")
    if not short_entry < short_exit:
        raise ValueError("short_entry must be < short_exit.")
    if int(cooldown_bars) < 0:
        raise ValueError("cooldown_bars must be >= 0.")
    if int(min_holding_bars) < 0:
        raise ValueError("min_holding_bars must be >= 0.")

    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_forecast_hysteresis",
    )
    values = df[forecast_col].astype(float)
    signal = pd.Series(0.0, index=df.index, name=output_col, dtype=float)

    state = 0.0
    bars_in_state = 0
    cooldown_remaining = 0
    min_hold = int(min_holding_bars)

    for ts, raw_value in values.items():
        value = float(raw_value) if np.isfinite(raw_value) else np.nan
        can_exit = bars_in_state >= min_hold
        next_state = state

        if np.isfinite(value):
            if state > 0.0:
                if can_exit and value <= float(long_exit):
                    next_state = 0.0
            elif state < 0.0:
                if can_exit and value >= float(short_exit):
                    next_state = 0.0
            elif cooldown_remaining <= 0:
                if value >= float(long_entry):
                    next_state = 1.0
                elif value <= float(short_entry):
                    next_state = -1.0

        if next_state != state:
            if state != 0.0 and next_state == 0.0:
                cooldown_remaining = int(cooldown_bars)
            elif state != 0.0 and next_state != 0.0:
                cooldown_remaining = int(cooldown_bars)
            bars_in_state = 0
            state = next_state
        else:
            bars_in_state += 1 if state != 0.0 else 0
            if state == 0.0 and cooldown_remaining > 0:
                cooldown_remaining -= 1

        signal.loc[ts] = state

    return signal.astype(float)


__all__ = ["forecast_threshold_hysteresis_signal"]
