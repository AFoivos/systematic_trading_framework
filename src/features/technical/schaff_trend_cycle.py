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
    cross_up_col: str | None = None,
    cross_down_col: str | None = None,
    rising_col: str | None = None,
    falling_col: str | None = None,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``schaff_trend_cycle`` feature transformation.

    The implementation follows the common STC construction: EMA fast/slow
    oscillator, trailing stochastic normalization, and two causal EMA smoothing
    passes. The raw feature writes only STC and its signal line. Cross-up,
    cross-down, rising, and falling flags are derived signals and should be
    produced with helpers when needed.

    YAML declaration::

        features:
          - step: schaff_trend_cycle
            params:
              price_col: close
              fast: 23
              slow: 50
              cycle: 10
              smooth: 3
              long_cross_level: 25.0
              short_cross_level: 75.0
              stc_col: stc
              stc_signal_col: stc_signal
              inplace: false
            transforms:
              crossing_flag:
                items:
                  - source_col: stc
                    threshold: 25.0
                    direction: up
                    output_col: stc_cross_up_25
                  - source_col: stc
                    threshold: 75.0
                    direction: down
                    output_col: stc_cross_down_75
              rising_flag:
                source_col: stc
                periods: 1
                output_col: stc_rising
              difference:
                source_col: stc
                periods: 1
                output_col: stc_delta_1
              threshold_flag:
                source_col: stc_delta_1
                threshold: 0.0
                op: lt
                output_col: stc_falling
          output_cols:
            - stc
            - stc_signal

    Required input columns
    ----------------------
    price_col:
        Price input column.

    Parameters
    ----------
    price_col:
        Input price column used for the STC calculation.
    fast:
        Fast EMA span used in the EMA oscillator.
    slow:
        Slow EMA span used in the EMA oscillator. Must be greater than fast.
    cycle:
        Rolling stochastic normalization window.
    smooth:
        EMA smoothing span applied during the STC construction.
    long_cross_level:
        Lower STC threshold used for bullish cross-up detection.
    short_cross_level:
        Upper STC threshold used for bearish cross-down detection.
    stc_col:
        Output column for the Schaff Trend Cycle value.
    stc_signal_col:
        Output column for the smoothed STC signal line.
    cross_up_col:
        Deprecated derived output. Use ``transforms.crossing_flag`` with
        ``direction: up``.
    cross_down_col:
        Deprecated derived output. Use ``transforms.crossing_flag`` with
        ``direction: down``.
    rising_col:
        Deprecated derived output. Use ``transforms.rising_flag``.
    falling_col:
        Deprecated derived output. Use ``transforms.difference`` followed by
        ``transforms.threshold_flag`` with ``op: lt``.
    inplace:
        If true, add the columns directly to the input DataFrame.
        If false, return a copied DataFrame with the new columns.
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
    _validate_output_cols(stc_col, stc_signal_col)
    _reject_derived_outputs(
        cross_up_col=cross_up_col,
        cross_down_col=cross_down_col,
        rising_col=rising_col,
        falling_col=falling_col,
    )

    out = df if inplace else df.copy()
    close = out[price_col].astype(float)
    stc = compute_schaff_trend_cycle(close, fast=fast, slow=slow, cycle=cycle, smooth=smooth)
    stc_signal = stc.ewm(span=smooth, adjust=False, min_periods=smooth).mean()

    out[stc_col] = stc
    out[stc_signal_col] = stc_signal
    return out


def compute_schaff_trend_cycle(
    close: pd.Series,
    *,
    fast: int = 23,
    slow: int = 50,
    cycle: int = 10,
    smooth: int = 3,
) -> pd.Series:
    """
    Compute the ``compute_schaff_trend_cycle`` feature value.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: compute_schaff_trend_cycle
            params:
              close: <required>
              fast: 23
              slow: 50
              cycle: 10
              smooth: 3
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    close:
        Configuration parameter accepted by this feature.
    fast:
        Trailing lookback or forecast horizon controlling this feature. Default: ``23``.
    slow:
        Trailing lookback or forecast horizon controlling this feature. Default: ``50``.
    cycle:
        Configuration parameter accepted by this feature. Default: ``10``.
    smooth:
        Configuration parameter accepted by this feature. Default: ``3``.
    """
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


def _reject_derived_outputs(
    *,
    cross_up_col: str | None,
    cross_down_col: str | None,
    rising_col: str | None,
    falling_col: str | None,
) -> None:
    requested = {
        "cross_up_col": cross_up_col,
        "cross_down_col": cross_down_col,
        "rising_col": rising_col,
        "falling_col": falling_col,
    }
    enabled = [name for name, value in requested.items() if value is not None]
    if enabled:
        raise ValueError(
            "STC derived outputs are no longer produced by schaff_trend_cycle "
            f"({', '.join(enabled)} requested). Use transforms.crossing_flag, "
            "transforms.rising_flag, transforms.difference, and transforms.threshold_flag."
        )


__all__ = [
    "add_schaff_trend_cycle_features",
    "compute_schaff_trend_cycle",
]
