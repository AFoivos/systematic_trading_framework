from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


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
    vol_window_pairs: Sequence[Sequence[int]] | None = None,
) -> pd.DataFrame:
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame.")

    out = df.copy()
    if returns_col in out.columns:
        returns = out[returns_col].astype(float)
    else:
        prices = out[price_col].astype(float)
        returns = prices.pct_change()
        out[returns_col] = returns

    for short_window, long_window in _resolve_vol_window_pairs(
        vol_short_window=vol_short_window,
        vol_long_window=vol_long_window,
        vol_window_pairs=vol_window_pairs,
    ):
        short_vol = returns.rolling(short_window, min_periods=short_window).std()
        long_vol = returns.rolling(long_window, min_periods=long_window).std()
        vol_ratio = short_vol / long_vol.replace(0.0, np.nan)

        vol_ratio_col = f"regime_vol_ratio_{short_window}_{long_window}"
        out[vol_ratio_col] = vol_ratio.astype("float32")
        out[f"regime_high_vol_state_{short_window}_{long_window}"] = (
            (vol_ratio > float(vol_ratio_high_threshold)).astype("float32")
        )
        out[f"regime_low_vol_state_{short_window}_{long_window}"] = (
            (vol_ratio < float(vol_ratio_low_threshold)).astype("float32")
        )

        vol_ratio_mean = vol_ratio.rolling(long_window, min_periods=long_window).mean()
        vol_ratio_std = vol_ratio.rolling(long_window, min_periods=long_window).std(ddof=0)
        out[f"regime_vol_ratio_z_{short_window}_{long_window}"] = (
            (vol_ratio - vol_ratio_mean) / vol_ratio_std.replace(0.0, np.nan)
        ).astype("float32")

        abs_ret = returns.abs()
        abs_ret_mean = abs_ret.rolling(long_window, min_periods=long_window).mean()
        abs_ret_std = abs_ret.rolling(long_window, min_periods=long_window).std(ddof=0)
        out[f"regime_absret_z_{short_window}_{long_window}"] = (
            (abs_ret.rolling(short_window, min_periods=short_window).mean() - abs_ret_mean)
            / abs_ret_std.replace(0.0, np.nan)
        ).astype("float32")

    prices = out[price_col].astype(float)
    ema_fast = prices.ewm(span=trend_fast_span, adjust=False).mean()
    ema_slow = prices.ewm(span=trend_slow_span, adjust=False).mean()
    trend_ratio = ema_fast / ema_slow.replace(0.0, np.nan) - 1.0

    out[f"regime_trend_ratio_{trend_fast_span}_{trend_slow_span}"] = trend_ratio.astype("float32")
    trend_state = np.sign(trend_ratio).astype("float32")
    trend_state = trend_state.where(~trend_ratio.isna(), other=np.nan)
    out[f"regime_trend_state_{trend_fast_span}_{trend_slow_span}"] = trend_state

    return out


def _resolve_vol_window_pairs(
    *,
    vol_short_window: int,
    vol_long_window: int,
    vol_window_pairs: Sequence[Sequence[int]] | None,
) -> list[tuple[int, int]]:
    raw_pairs = vol_window_pairs if vol_window_pairs is not None else [(vol_short_window, vol_long_window)]
    resolved: list[tuple[int, int]] = []
    for raw_pair in raw_pairs:
        if len(raw_pair) != 2:
            raise ValueError("regime_context vol_window_pairs entries must contain exactly two integers.")
        short_window = int(raw_pair[0])
        long_window = int(raw_pair[1])
        if short_window <= 0 or long_window <= 0:
            raise ValueError("regime_context vol windows must be positive integers.")
        pair = (short_window, long_window)
        if pair not in resolved:
            resolved.append(pair)
    if not resolved:
        raise ValueError("regime_context vol_window_pairs must not be empty.")
    return resolved


__all__ = ["add_regime_context_features"]
