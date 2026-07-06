from __future__ import annotations

from typing import Any

import pandas as pd

from src.signals._common import resolve_signal_output_name


def _time_index(
    df: pd.DataFrame,
    *,
    timestamp_col: str,
    timezone_input: str,
    timezone: str,
) -> pd.DatetimeIndex:
    raw = df[timestamp_col] if timestamp_col in df.columns else df.index
    idx = pd.DatetimeIndex(pd.to_datetime(raw, errors="coerce"))
    if idx.hasnans:
        raise ValueError("weekday_prev_daily_return_reversal requires parseable timestamps.")
    if idx.tz is None:
        idx = idx.tz_localize(timezone_input)
    return idx.tz_convert(timezone)


def weekday_prev_daily_return_reversal_signal(
    df: pd.DataFrame,
    *,
    close_col: str = "close",
    timestamp_col: str = "timestamp",
    timezone_input: str = "UTC",
    timezone: str = "America/New_York",
    weekday: int = 3,
    signal_hour: int = 9,
    signal_minute: int = 0,
    prev_daily_return_max: float = -0.0006369942365362478,
    side: float = 1.0,
    signal_col: str | None = None,
    candidate_col: str = "signal_candidate",
    prev_daily_return_col: str = "prev_daily_return",
    local_weekday_col: str = "local_weekday",
    local_hour_col: str = "local_hour",
) -> pd.DataFrame:
    """
    Emit a fixed-time weekday reversal signal after a weak previous daily return.

    The signal is causal at intraday timestamp ``t``: the daily return mapped to
    each row is the previous completed local trading day's close-to-close return.
    The framework backtester then enters on the next bar open.
    """
    if close_col not in df.columns:
        raise KeyError(f"Missing close column for weekday_prev_daily_return_reversal: {close_col}")
    if not 0 <= int(weekday) <= 6:
        raise ValueError("weekday must use pandas convention: Monday=0 ... Sunday=6.")
    if not 0 <= int(signal_hour) <= 23:
        raise ValueError("signal_hour must be in [0, 23].")
    if not 0 <= int(signal_minute) <= 59:
        raise ValueError("signal_minute must be in [0, 59].")

    out = df.copy()
    signal_name = resolve_signal_output_name(signal_col=signal_col, default="signal_side")
    local_idx = _time_index(
        out,
        timestamp_col=timestamp_col,
        timezone_input=timezone_input,
        timezone=timezone,
    )
    close = pd.to_numeric(out[close_col], errors="coerce").astype(float)
    local_dates = pd.Index(local_idx.date)

    daily_close = close.groupby(local_dates).last()
    prev_daily_return_by_date = daily_close.pct_change().shift(1)
    prev_daily_return = pd.Series(local_dates, index=out.index).map(prev_daily_return_by_date)

    local_weekday = pd.Series(local_idx.dayofweek, index=out.index, dtype="int16")
    local_hour_float = pd.Series(
        local_idx.hour + local_idx.minute / 60.0,
        index=out.index,
        dtype="float32",
    )
    is_signal_time = (local_idx.hour == int(signal_hour)) & (local_idx.minute == int(signal_minute))
    setup = (
        local_weekday.eq(int(weekday))
        & pd.Series(is_signal_time, index=out.index)
        & pd.to_numeric(prev_daily_return, errors="coerce").lt(float(prev_daily_return_max))
    )

    out[prev_daily_return_col] = pd.to_numeric(prev_daily_return, errors="coerce").astype(float)
    out[local_weekday_col] = local_weekday
    out[local_hour_col] = local_hour_float
    out[candidate_col] = setup.fillna(False).astype("int8")
    out[signal_name] = out[candidate_col].astype(float) * float(side)
    return out


__all__ = ["weekday_prev_daily_return_reversal_signal"]
