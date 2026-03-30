from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.technical.atr import compute_atr


def _validate_positive_int(value: int, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer.")
    return int(value)


def _bars_since_last_true(mask: pd.Series, *, name: str) -> pd.Series:
    out = np.full(len(mask), np.nan, dtype=float)
    last_idx: int | None = None
    for idx, is_true in enumerate(mask.fillna(False).astype(bool).to_numpy(dtype=bool)):
        if is_true:
            last_idx = idx
            out[idx] = 0.0
        elif last_idx is not None:
            out[idx] = float(idx - last_idx)
    return pd.Series(out, index=mask.index, name=name, dtype="float32")


def add_support_resistance_v2_features(
    df: pd.DataFrame,
    *,
    price_col: str = "close",
    high_col: str = "high",
    low_col: str = "low",
    atr_col: str | None = None,
    atr_window: int = 24,
    pivot_left_window: int = 24,
    pivot_confirm_bars: int = 6,
    touch_tolerance_atr: float = 0.25,
    breakout_tolerance_atr: float = 0.05,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Add PIT-safe pivot-based support and resistance context.

    A pivot is confirmed only after `pivot_confirm_bars` future bars have elapsed, so all
    emitted levels are available without lookahead at the current timestamp.
    """
    missing = [col for col in (price_col, high_col, low_col) if col not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for support_resistance_v2: {missing}")

    pivot_left_window = _validate_positive_int(pivot_left_window, field="pivot_left_window")
    pivot_confirm_bars = _validate_positive_int(pivot_confirm_bars, field="pivot_confirm_bars")
    atr_window = _validate_positive_int(atr_window, field="atr_window")
    if float(touch_tolerance_atr) < 0.0:
        raise ValueError("touch_tolerance_atr must be >= 0.")
    if float(breakout_tolerance_atr) < 0.0:
        raise ValueError("breakout_tolerance_atr must be >= 0.")

    out = df if inplace else df.copy()
    close = out[price_col].astype(float)
    high = out[high_col].astype(float)
    low = out[low_col].astype(float)

    if atr_col is not None:
        if atr_col not in out.columns:
            raise KeyError(
                f"support_resistance_v2 atr_col '{atr_col}' not found in DataFrame. "
                "Provide an existing ATR column or omit atr_col to use atr_window fallback."
            )
        atr = out[atr_col].astype(float)
    else:
        atr = compute_atr(high, low, close, window=atr_window, method="wilder").astype(float)
    atr = atr.where(atr > 0.0, other=np.nan)

    confirm = int(pivot_confirm_bars)
    total_window = int(pivot_left_window) + confirm + 1

    pivot_high_candidate = high.shift(confirm)
    pivot_low_candidate = low.shift(confirm)

    rolling_high = high.rolling(total_window, min_periods=total_window).max()
    rolling_low = low.rolling(total_window, min_periods=total_window).min()

    pivot_high_confirmed = pivot_high_candidate.where(pivot_high_candidate.eq(rolling_high))
    pivot_low_confirmed = pivot_low_candidate.where(pivot_low_candidate.eq(rolling_low))

    out["pivot_high_confirmed"] = pivot_high_confirmed.astype("float32")
    out["pivot_low_confirmed"] = pivot_low_confirmed.astype("float32")

    resistance_level = pivot_high_confirmed.ffill()
    support_level = pivot_low_confirmed.ffill()
    out["sr_v2_resistance_level"] = resistance_level.astype("float32")
    out["sr_v2_support_level"] = support_level.astype("float32")

    resistance_pivot_event = pivot_high_confirmed.notna()
    support_pivot_event = pivot_low_confirmed.notna()
    out["sr_v2_resistance_age"] = _bars_since_last_true(
        resistance_pivot_event,
        name="sr_v2_resistance_age",
    )
    out["sr_v2_support_age"] = _bars_since_last_true(
        support_pivot_event,
        name="sr_v2_support_age",
    )

    touch_tol = atr * float(touch_tolerance_atr)
    support_touch = support_level.notna() & ((low - support_level).abs() <= touch_tol)
    resistance_touch = resistance_level.notna() & ((high - resistance_level).abs() <= touch_tol)

    support_level_id = support_pivot_event.cumsum()
    resistance_level_id = resistance_pivot_event.cumsum()
    out["sr_v2_support_touch_count"] = (
        support_touch.astype(int)
        .groupby(support_level_id)
        .cumsum()
        .where(support_level.notna(), other=np.nan)
        .astype("float32")
    )
    out["sr_v2_resistance_touch_count"] = (
        resistance_touch.astype(int)
        .groupby(resistance_level_id)
        .cumsum()
        .where(resistance_level.notna(), other=np.nan)
        .astype("float32")
    )

    breakout_tol = atr * float(breakout_tolerance_atr)
    breakout_up = resistance_level.notna() & (close > (resistance_level + breakout_tol))
    breakout_down = support_level.notna() & (close < (support_level - breakout_tol))
    out["sr_v2_breakout_up"] = breakout_up.astype("float32")
    out["sr_v2_breakout_down"] = breakout_down.astype("float32")

    breakout_up_state = pd.Series(
        np.where(breakout_up.to_numpy(dtype=bool), 1.0, np.nan),
        index=out.index,
        dtype=float,
    )
    breakout_down_state = pd.Series(
        np.where(breakout_down.to_numpy(dtype=bool), 1.0, np.nan),
        index=out.index,
        dtype=float,
    )
    breakout_up_active = breakout_up_state.ffill().notna()
    breakout_down_active = breakout_down_state.ffill().notna()

    resistance_retest = (
        breakout_up_active
        & resistance_level.notna()
        & (low <= (resistance_level + touch_tol))
        & (close >= resistance_level)
    )
    support_retest = (
        breakout_down_active
        & support_level.notna()
        & (high >= (support_level - touch_tol))
        & (close <= support_level)
    )
    out["sr_v2_retest_resistance"] = resistance_retest.astype("float32")
    out["sr_v2_retest_support"] = support_retest.astype("float32")

    out["sr_v2_support_distance_atr"] = ((close - support_level) / atr).astype("float32")
    out["sr_v2_resistance_distance_atr"] = ((resistance_level - close) / atr).astype("float32")
    return out


__all__ = ["add_support_resistance_v2_features"]
