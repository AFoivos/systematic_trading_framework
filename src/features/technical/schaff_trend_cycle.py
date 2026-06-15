from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd

from .ema import compute_ema


def add_schaff_trend_cycle_features(
    df: pd.DataFrame,
    price_col: str = "close",
    fast: int = 23,
    slow: int = 50,
    cycle: int = 10,
    smooth: int = 3,
    long_cross_level: float = 25.0,
    short_cross_level: float = 75.0,
    stc_col: str = "stc",
    stc_signal_col: str = "stc_signal",
    cross_up_col: str = "stc_cross_up_25",
    cross_down_col: str = "stc_cross_down_75",
    rising_col: str = "stc_rising",
    falling_col: str = "stc_falling",
    inplace: bool = False,
) -> pd.DataFrame:
    """Add a causal Schaff Trend Cycle feature set.

    The implementation follows the common STC construction: EMA fast/slow
    oscillator, trailing stochastic normalization, and two causal EMA smoothing
    passes. All rolling windows are trailing windows.
    """
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")
    _validate_params(
        fast=fast,
        slow=slow,
        cycle=cycle,
        smooth=smooth,
        long_cross_level=long_cross_level,
        short_cross_level=short_cross_level,
    )
    _validate_output_cols(
        stc_col,
        stc_signal_col,
        cross_up_col,
        cross_down_col,
        rising_col,
        falling_col,
    )

    out = df if inplace else df.copy()
    close = out[price_col].astype(float)
    stc = compute_schaff_trend_cycle(close, fast=fast, slow=slow, cycle=cycle, smooth=smooth)
    stc_signal = stc.ewm(span=smooth, adjust=False, min_periods=smooth).mean()

    out[stc_col] = stc
    out[stc_signal_col] = stc_signal
    out[cross_up_col] = stc.shift(1).le(float(long_cross_level)) & stc.gt(float(long_cross_level))
    out[cross_down_col] = stc.shift(1).ge(float(short_cross_level)) & stc.lt(float(short_cross_level))
    out[rising_col] = stc.gt(stc.shift(1))
    out[falling_col] = stc.lt(stc.shift(1))
    return out


def compute_schaff_trend_cycle(
    close: pd.Series,
    *,
    fast: int = 23,
    slow: int = 50,
    cycle: int = 10,
    smooth: int = 3,
) -> pd.Series:
    if not isinstance(close, pd.Series):
        raise TypeError("close must be a pandas Series.")
    _validate_params(
        fast=fast,
        slow=slow,
        cycle=cycle,
        smooth=smooth,
        long_cross_level=25.0,
        short_cross_level=75.0,
    )

    ema_fast = compute_ema(close.astype(float), span=fast)
    ema_slow = compute_ema(close.astype(float), span=slow)
    oscillator = ema_fast - ema_slow
    first_stoch = _stochastic_normalize(oscillator, window=cycle)
    first_smooth = first_stoch.ewm(span=smooth, adjust=False, min_periods=smooth).mean()
    second_stoch = _stochastic_normalize(first_smooth, window=cycle)
    stc = second_stoch.ewm(span=smooth, adjust=False, min_periods=smooth).mean()
    stc = stc.clip(lower=0.0, upper=100.0)
    stc.name = "stc"
    return stc


def _stochastic_normalize(series: pd.Series, *, window: int) -> pd.Series:
    low = series.rolling(window=window, min_periods=window).min()
    high = series.rolling(window=window, min_periods=window).max()
    span = high - low
    normalized = 100.0 * (series - low) / span.replace(0.0, np.nan)
    return normalized.clip(lower=0.0, upper=100.0)


def _validate_params(
    *,
    fast: int,
    slow: int,
    cycle: int,
    smooth: int,
    long_cross_level: float,
    short_cross_level: float,
) -> None:
    for name, value in (("fast", fast), ("slow", slow), ("cycle", cycle), ("smooth", smooth)):
        if isinstance(value, bool) or not isinstance(value, Integral) or int(value) <= 1:
            raise ValueError(f"{name} must be an integer greater than 1.")
    if int(fast) >= int(slow):
        raise ValueError("fast must be less than slow.")
    for name, value in (("long_cross_level", long_cross_level), ("short_cross_level", short_cross_level)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(float(value)):
            raise ValueError(f"{name} must be a finite number.")
        if not 0.0 <= float(value) <= 100.0:
            raise ValueError(f"{name} must be in [0, 100].")
    if float(long_cross_level) >= float(short_cross_level):
        raise ValueError("long_cross_level must be less than short_cross_level.")


def _validate_output_cols(*columns: str) -> None:
    for column in columns:
        if not isinstance(column, str) or not column.strip():
            raise ValueError("STC output columns must be non-empty strings.")
    if len(set(columns)) != len(columns):
        raise ValueError("STC output columns must be unique.")


__all__ = [
    "add_schaff_trend_cycle_features",
    "compute_schaff_trend_cycle",
]
