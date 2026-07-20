from __future__ import annotations

"""Causal features and deterministic candidates for the MATB strategy family."""

from collections.abc import Sequence

import numpy as np
import pandas as pd


MATB_OUTPUT_COLUMNS = (
    "matb_atr",
    "matb_atr_pct",
    "matb_vol_short",
    "matb_vol_long",
    "matb_vol_ratio_5d_60d",
    "matb_mom_5d_z",
    "matb_mom_20d_z",
    "matb_mom_60d_z",
    "matb_trend_score",
    "matb_prior_high",
    "matb_prior_low",
    "matb_channel_width_atr",
    "matb_breakout_distance_atr",
    "matb_close_location",
    "matb_bar_range_atr",
    "matb_gap_atr",
    "matb_spread_to_median",
    "matb_decision_bar",
    "matb_long_candidate",
    "matb_short_candidate",
    "matb_candidate",
    "matb_side",
    "matb_direction",
)


def _positive_int(value: int, *, field: str) -> int:
    if isinstance(value, bool) or int(value) <= 0 or float(value) != float(int(value)):
        raise ValueError(f"multi_asset_trend_breakout {field} must be a positive integer.")
    return int(value)


def _finite_non_negative(value: float, *, field: str) -> float:
    resolved = float(value)
    if not np.isfinite(resolved) or resolved < 0.0:
        raise ValueError(f"multi_asset_trend_breakout {field} must be finite and >= 0.")
    return resolved


def _finite_positive(value: float, *, field: str) -> float:
    resolved = float(value)
    if not np.isfinite(resolved) or resolved <= 0.0:
        raise ValueError(f"multi_asset_trend_breakout {field} must be finite and > 0.")
    return resolved


def _require_datetime_index(index: pd.Index) -> pd.DatetimeIndex:
    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError("multi_asset_trend_breakout requires a DatetimeIndex.")
    if index.has_duplicates:
        raise ValueError("multi_asset_trend_breakout requires unique timestamps.")
    if not index.is_monotonic_increasing:
        raise ValueError("multi_asset_trend_breakout requires chronologically sorted timestamps.")
    return index


def _utc_index(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    if index.tz is None:
        return index.tz_localize("UTC")
    return index.tz_convert("UTC")


def _gap_aware_true_range(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    *,
    expected_bar_minutes: int,
    maximum_gap_multiple: float,
) -> tuple[pd.Series, pd.Series]:
    index = _require_datetime_index(close.index)
    previous_close = close.shift(1)
    deltas = index.to_series(index=index).diff()
    maximum_delta = pd.Timedelta(minutes=expected_bar_minutes * maximum_gap_multiple)
    contiguous = deltas.le(maximum_delta) & deltas.gt(pd.Timedelta(0))
    usable_previous_close = previous_close.where(contiguous)
    true_range = pd.concat(
        [
            high - low,
            (high - usable_previous_close).abs(),
            (low - usable_previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1, skipna=True)
    true_range = true_range.where(high.notna() & low.notna())
    return true_range.astype(float), (~contiguous & deltas.notna()).astype(bool)


def _wilder_atr(true_range: pd.Series, *, window: int) -> pd.Series:
    return true_range.ewm(
        alpha=1.0 / float(window),
        adjust=False,
        min_periods=window,
        ignore_na=True,
    ).mean()


def _decision_bar_mask(index: pd.DatetimeIndex, *, decision_hours_utc: Sequence[int]) -> pd.Series:
    hours = tuple(int(hour) for hour in decision_hours_utc)
    if not hours or any(hour < 0 or hour > 23 for hour in hours):
        raise ValueError("multi_asset_trend_breakout decision_hours_utc must contain UTC hours in [0, 23].")
    utc = _utc_index(index)
    mask = utc.hour.isin(hours) & (utc.minute == 30) & (utc.second == 0)
    return pd.Series(mask, index=index, dtype=bool)


def add_multi_asset_trend_breakout_features(
    df: pd.DataFrame,
    *,
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    spread_col: str = "spread_bps",
    bars_per_day: int = 48,
    atr_window: int = 48,
    short_vol_days: int = 5,
    long_vol_days: int = 60,
    momentum_days: Sequence[int] = (5, 20, 60),
    donchian_days: int = 20,
    spread_median_days: int = 20,
    decision_hours_utc: Sequence[int] = (3, 7, 11, 15, 19, 23),
    expected_bar_minutes: int = 30,
    maximum_gap_multiple: float = 1.5,
    trend_threshold: float = 0.20,
    maximum_breakout_distance_atr: float = 0.50,
    minimum_channel_width_atr: float = 4.0,
    minimum_volatility_ratio: float = 0.50,
    maximum_volatility_ratio: float = 2.50,
    maximum_spread_to_median: float = 2.0,
) -> pd.DataFrame:
    """
    Build the causal Multi-Asset Trend Breakout feature and candidate set.

    The current closed 30-minute bar is observable, while every Donchian
    boundary and spread baseline ends at ``t-1``. Signals generated from these
    columns are therefore intended for next-open execution.

    YAML declaration::

        features:
          - step: multi_asset_trend_breakout
            params:
              bars_per_day: 48
              atr_window: 48
              short_vol_days: 5
              long_vol_days: 60
              momentum_days: [5, 20, 60]
              donchian_days: 20
              trend_threshold: 0.20

    Required input columns
    ----------------------
    open_col, high_col, low_col, close_col:
        Point-in-time OHLC columns for each closed 30-minute bar.
    spread_col:
        Optional observed spread column. Missing spread data remains NaN and
        never gets imputed to zero.

    Parameters
    ----------
    bars_per_day:
        Structural conversion from trading days to 30-minute bars. Default: ``48``.
    atr_window:
        Wilder ATR lookback in bars. Default: ``48``.
    momentum_days:
        Momentum horizons in days; MATB requires exactly ``[5, 20, 60]``.
    donchian_days:
        Prior-only Donchian lookback in days. Default: ``20``.
    decision_hours_utc:
        UTC hours whose ``:30`` bar closes a four-hour decision block.
    """
    required = [open_col, high_col, low_col, close_col]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns for multi_asset_trend_breakout: {missing}")
    index = _require_datetime_index(df.index)

    bars_per_day = _positive_int(bars_per_day, field="bars_per_day")
    atr_window = _positive_int(atr_window, field="atr_window")
    short_vol_days = _positive_int(short_vol_days, field="short_vol_days")
    long_vol_days = _positive_int(long_vol_days, field="long_vol_days")
    donchian_days = _positive_int(donchian_days, field="donchian_days")
    spread_median_days = _positive_int(spread_median_days, field="spread_median_days")
    expected_bar_minutes = _positive_int(expected_bar_minutes, field="expected_bar_minutes")
    maximum_gap_multiple = _finite_positive(maximum_gap_multiple, field="maximum_gap_multiple")
    if maximum_gap_multiple < 1.0:
        raise ValueError("multi_asset_trend_breakout maximum_gap_multiple must be >= 1.")
    resolved_momentum_days = tuple(_positive_int(value, field="momentum_days") for value in momentum_days)
    if resolved_momentum_days != (5, 20, 60):
        raise ValueError("multi_asset_trend_breakout momentum_days must be exactly [5, 20, 60].")
    if short_vol_days >= long_vol_days:
        raise ValueError("multi_asset_trend_breakout short_vol_days must be < long_vol_days.")

    trend_threshold = _finite_non_negative(trend_threshold, field="trend_threshold")
    maximum_breakout_distance_atr = _finite_non_negative(
        maximum_breakout_distance_atr,
        field="maximum_breakout_distance_atr",
    )
    minimum_channel_width_atr = _finite_non_negative(
        minimum_channel_width_atr,
        field="minimum_channel_width_atr",
    )
    minimum_volatility_ratio = _finite_non_negative(
        minimum_volatility_ratio,
        field="minimum_volatility_ratio",
    )
    maximum_volatility_ratio = _finite_positive(
        maximum_volatility_ratio,
        field="maximum_volatility_ratio",
    )
    maximum_spread_to_median = _finite_positive(
        maximum_spread_to_median,
        field="maximum_spread_to_median",
    )
    if minimum_volatility_ratio > maximum_volatility_ratio:
        raise ValueError("multi_asset_trend_breakout volatility ratio bounds are inverted.")

    out = df.copy()
    open_ = pd.to_numeric(out[open_col], errors="coerce").astype(float)
    high = pd.to_numeric(out[high_col], errors="coerce").astype(float)
    low = pd.to_numeric(out[low_col], errors="coerce").astype(float)
    close = pd.to_numeric(out[close_col], errors="coerce").astype(float)
    valid_close = close.where(close > 0.0)

    true_range, abnormal_gap = _gap_aware_true_range(
        high,
        low,
        close,
        expected_bar_minutes=expected_bar_minutes,
        maximum_gap_multiple=maximum_gap_multiple,
    )
    atr = _wilder_atr(true_range, window=atr_window)
    atr_valid = atr.where(atr > 0.0)
    out["matb_atr"] = atr.astype(float)
    out["matb_atr_pct"] = (atr_valid / valid_close).astype(float)

    log_returns = np.log(valid_close / valid_close.shift(1))
    short_window = short_vol_days * bars_per_day
    long_window = long_vol_days * bars_per_day
    vol_short = log_returns.ewm(
        span=short_window,
        adjust=False,
        min_periods=short_window,
    ).std(bias=False)
    vol_long = log_returns.ewm(
        span=long_window,
        adjust=False,
        min_periods=long_window,
    ).std(bias=False)
    vol_long_valid = vol_long.where(vol_long > 0.0)
    out["matb_vol_short"] = vol_short.astype(float)
    out["matb_vol_long"] = vol_long.astype(float)
    out["matb_vol_ratio_5d_60d"] = (vol_short / vol_long_valid).astype(float)

    momentum_columns: list[str] = []
    for days in resolved_momentum_days:
        horizon = days * bars_per_day
        raw_momentum = np.log(valid_close / valid_close.shift(horizon))
        normalized = raw_momentum / (vol_long_valid * np.sqrt(float(horizon)))
        column = f"matb_mom_{days}d_z"
        out[column] = normalized.clip(lower=-3.0, upper=3.0).astype(float)
        momentum_columns.append(column)
    out["matb_trend_score"] = out[momentum_columns].mean(axis=1, skipna=False).astype(float)

    donchian_lookback = donchian_days * bars_per_day
    prior_high = high.shift(1).rolling(donchian_lookback, min_periods=donchian_lookback).max()
    prior_low = low.shift(1).rolling(donchian_lookback, min_periods=donchian_lookback).min()
    out["matb_prior_high"] = prior_high.astype(float)
    out["matb_prior_low"] = prior_low.astype(float)
    out["matb_channel_width_atr"] = ((prior_high - prior_low) / atr_valid).astype(float)

    long_cross = close.gt(prior_high) & close.shift(1).le(prior_high.shift(1))
    short_cross = close.lt(prior_low) & close.shift(1).ge(prior_low.shift(1))
    breakout_distance = pd.Series(np.nan, index=index, dtype=float)
    breakout_distance.loc[long_cross] = ((close - prior_high) / atr_valid).loc[long_cross]
    breakout_distance.loc[short_cross] = ((prior_low - close) / atr_valid).loc[short_cross]
    out["matb_breakout_distance_atr"] = breakout_distance.astype(float)

    bar_range = high - low
    out["matb_close_location"] = ((close - low) / bar_range.where(bar_range > 0.0)).astype(float)
    out["matb_bar_range_atr"] = (bar_range / atr_valid).astype(float)
    out["matb_gap_atr"] = ((open_ - close.shift(1)).abs() / atr_valid).astype(float)

    spread_available = spread_col in out.columns
    if spread_available:
        spread = pd.to_numeric(out[spread_col], errors="coerce").astype(float)
        spread_window = spread_median_days * bars_per_day
        trailing_median = spread.shift(1).rolling(
            spread_window,
            min_periods=spread_window,
        ).median()
        out["matb_spread_to_median"] = (
            spread / trailing_median.where(trailing_median > 0.0)
        ).astype(float)
    else:
        out["matb_spread_to_median"] = np.nan

    decision_bar = _decision_bar_mask(index, decision_hours_utc=decision_hours_utc)
    volatility_ratio = out["matb_vol_ratio_5d_60d"].astype(float)
    spread_ratio = out["matb_spread_to_median"].astype(float)
    spread_pass = spread_ratio.le(maximum_spread_to_median) | spread_ratio.isna()
    common = (
        decision_bar
        & breakout_distance.ge(0.0)
        & breakout_distance.le(maximum_breakout_distance_atr)
        & out["matb_channel_width_atr"].ge(minimum_channel_width_atr)
        & volatility_ratio.ge(minimum_volatility_ratio)
        & volatility_ratio.le(maximum_volatility_ratio)
        & spread_pass
    )
    long_candidate = (
        common
        & long_cross
        & out["matb_trend_score"].ge(trend_threshold)
        & out["matb_mom_20d_z"].gt(0.0)
    )
    short_candidate = (
        common
        & short_cross
        & out["matb_trend_score"].le(-trend_threshold)
        & out["matb_mom_20d_z"].lt(0.0)
    )
    # A valid channel cannot cross in both directions, but keep the invariant
    # explicit so malformed OHLC data cannot emit ambiguous trades.
    ambiguous = long_candidate & short_candidate
    if bool(ambiguous.any()):
        long_candidate = long_candidate & ~ambiguous
        short_candidate = short_candidate & ~ambiguous
    candidate = long_candidate | short_candidate
    side = long_candidate.astype(np.int8) - short_candidate.astype(np.int8)

    out["matb_decision_bar"] = decision_bar.astype("int8")
    out["matb_long_candidate"] = long_candidate.astype("int8")
    out["matb_short_candidate"] = short_candidate.astype("int8")
    out["matb_candidate"] = candidate.astype("int8")
    out["matb_side"] = side.astype("int8")
    out["matb_direction"] = side.astype("int8")
    out.attrs["matb_feature_audit"] = {
        "spread_column": spread_col,
        "spread_available": bool(spread_available),
        "abnormal_gap_count": int(abnormal_gap.sum()),
        "bars_per_day": int(bars_per_day),
        "donchian_lookback_bars": int(donchian_lookback),
        "decision_hours_utc": [int(hour) for hour in decision_hours_utc],
        "bar_timestamp_convention": "bar_start",
    }

    if len(out) != len(df) or not out.index.equals(df.index):
        raise AssertionError("multi_asset_trend_breakout must preserve input index and row count.")
    return out


__all__ = ["MATB_OUTPUT_COLUMNS", "add_multi_asset_trend_breakout_features"]
