from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np
import pandas as pd


def _index_in_timezone(index: pd.Index, timezone: str) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(pd.to_datetime(index, errors="raise"))
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    return idx.tz_convert(str(timezone))


def _session_mask(hours: pd.Index, index: pd.Index, *, start_hour: int, end_hour: int) -> pd.Series:
    if not (0 <= start_hour <= 23 and 0 <= end_hour <= 24):
        raise ValueError("Session hours must satisfy 0 <= start_hour <= 23 and 0 <= end_hour <= 24.")
    if start_hour == end_hour:
        return pd.Series(True, index=index, dtype="float32")
    if start_hour < end_hour:
        mask = (hours >= start_hour) & (hours < end_hour)
    else:
        mask = (hours >= start_hour) | (hours < end_hour)
    return pd.Series(mask.astype("float32"), index=index, dtype="float32")


def add_session_context_features(
    df: pd.DataFrame,
    *,
    timezone: str = "UTC",
    add_cyclical_time: bool = True,
    include_weekend_flag: bool = True,
    sessions: Mapping[str, Sequence[int]] | None = None,
) -> pd.DataFrame:
    """
    Add reusable session-aware intraday context features from the DatetimeIndex.

    The function assumes the frame index is already PIT-aligned and uses an explicit timezone
    conversion before deriving hour/day features, so downstream models do not rely on implicit
    local-time behavior.
    """
    out = df.copy()
    local_idx = _index_in_timezone(out.index, timezone)
    hours = pd.Index(local_idx.hour, dtype="int32")
    day_of_week = pd.Index(local_idx.dayofweek, dtype="int32")

    if add_cyclical_time:
        out["hour_sin_24"] = np.sin(2.0 * np.pi * hours.to_numpy(dtype=float) / 24.0).astype("float32")
        out["hour_cos_24"] = np.cos(2.0 * np.pi * hours.to_numpy(dtype=float) / 24.0).astype("float32")
        out["day_of_week_sin_7"] = np.sin(2.0 * np.pi * day_of_week.to_numpy(dtype=float) / 7.0).astype(
            "float32"
        )
        out["day_of_week_cos_7"] = np.cos(2.0 * np.pi * day_of_week.to_numpy(dtype=float) / 7.0).astype(
            "float32"
        )

    default_sessions: dict[str, tuple[int, int]] = {
        "asia": (0, 8),
        "europe": (7, 16),
        "us": (13, 21),
    }
    raw_sessions = dict(default_sessions)
    if sessions is not None:
        for name, bounds in dict(sessions).items():
            if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
                raise ValueError("sessions entries must be [start_hour, end_hour] pairs.")
            raw_sessions[str(name)] = (int(bounds[0]), int(bounds[1]))

    session_flags: dict[str, pd.Series] = {}
    for session_name, (start_hour, end_hour) in sorted(raw_sessions.items()):
        col_name = f"session_{session_name}"
        session_flags[col_name] = _session_mask(hours, out.index, start_hour=start_hour, end_hour=end_hour)
        out[col_name] = session_flags[col_name]

    if {"session_europe", "session_us"}.issubset(session_flags):
        out["session_europe_us_overlap"] = (
            (session_flags["session_europe"] > 0.0) & (session_flags["session_us"] > 0.0)
        ).astype("float32")

    if include_weekend_flag:
        out["is_weekend"] = (day_of_week >= 5).astype("float32")

    return out


def add_regime_context_features(
    df: pd.DataFrame,
    *,
    price_col: str = "close",
    returns_col: str = "close_ret",
    vol_short_window: int = 24,
    vol_long_window: int = 168,
    trend_fast_span: int = 24,
    trend_slow_span: int = 72,
    vol_ratio_high_threshold: float = 1.25,
    vol_ratio_low_threshold: float = 0.85,
) -> pd.DataFrame:
    """
    Add reusable regime-aware features that summarize volatility and trend state.

    The emitted features are causal rolling transforms intended to be reused across classical
    models without introducing learned encoders into the feature layer.
    """
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame.")

    out = df.copy()
    if returns_col in out.columns:
        returns = out[returns_col].astype(float)
    else:
        prices = out[price_col].astype(float)
        returns = prices.pct_change()
        out[returns_col] = returns

    short_vol = returns.rolling(vol_short_window, min_periods=vol_short_window).std()
    long_vol = returns.rolling(vol_long_window, min_periods=vol_long_window).std()
    vol_ratio = short_vol / long_vol.replace(0.0, np.nan)

    vol_ratio_col = f"regime_vol_ratio_{vol_short_window}_{vol_long_window}"
    out[vol_ratio_col] = vol_ratio.astype("float32")
    out[f"regime_high_vol_state_{vol_short_window}_{vol_long_window}"] = (
        (vol_ratio > float(vol_ratio_high_threshold)).astype("float32")
    )
    out[f"regime_low_vol_state_{vol_short_window}_{vol_long_window}"] = (
        (vol_ratio < float(vol_ratio_low_threshold)).astype("float32")
    )

    vol_ratio_mean = vol_ratio.rolling(vol_long_window, min_periods=vol_long_window).mean()
    vol_ratio_std = vol_ratio.rolling(vol_long_window, min_periods=vol_long_window).std(ddof=0)
    out[f"regime_vol_ratio_z_{vol_short_window}_{vol_long_window}"] = (
        (vol_ratio - vol_ratio_mean) / vol_ratio_std.replace(0.0, np.nan)
    ).astype("float32")

    prices = out[price_col].astype(float)
    ema_fast = prices.ewm(span=trend_fast_span, adjust=False).mean()
    ema_slow = prices.ewm(span=trend_slow_span, adjust=False).mean()
    trend_ratio = ema_fast / ema_slow.replace(0.0, np.nan) - 1.0

    out[f"regime_trend_ratio_{trend_fast_span}_{trend_slow_span}"] = trend_ratio.astype("float32")
    trend_state = np.sign(trend_ratio).astype("float32")
    trend_state = trend_state.where(~trend_ratio.isna(), other=np.nan)
    out[f"regime_trend_state_{trend_fast_span}_{trend_slow_span}"] = trend_state

    abs_ret = returns.abs()
    abs_ret_mean = abs_ret.rolling(vol_long_window, min_periods=vol_long_window).mean()
    abs_ret_std = abs_ret.rolling(vol_long_window, min_periods=vol_long_window).std(ddof=0)
    out[f"regime_absret_z_{vol_short_window}_{vol_long_window}"] = (
        (abs_ret.rolling(vol_short_window, min_periods=vol_short_window).mean() - abs_ret_mean)
        / abs_ret_std.replace(0.0, np.nan)
    ).astype("float32")

    return out


__all__ = [
    "add_regime_context_features",
    "add_session_context_features",
]
