from __future__ import annotations

import math
from typing import Literal

import numpy as np
import pandas as pd


def _validate_bar_count(value: int, *, field: str, min_value: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or int(value) < int(min_value):
        raise ValueError(f"{field} must be an integer >= {min_value}.")
    return int(value)


def _validate_prefix(prefix: str) -> str:
    if not isinstance(prefix, str) or not prefix.strip():
        raise ValueError("prefix must be a non-empty string.")
    return prefix.strip()


def _resolve_extrema_sources(
    data: pd.DataFrame | pd.Series,
    *,
    high_col: str,
    low_col: str,
    close_col: str,
    use_col_for_high: str,
    use_col_for_low: str,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    if isinstance(data, pd.Series):
        series = pd.to_numeric(data, errors="coerce").astype(float)
        return series, series, series

    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame or Series.")

    required = [close_col, use_col_for_high, use_col_for_low]
    missing = [col for col in required if col not in data.columns]
    if missing:
        raise KeyError(f"Missing columns for extrema detection: {missing}")

    high = pd.to_numeric(data[use_col_for_high], errors="coerce").astype(float)
    low = pd.to_numeric(data[use_col_for_low], errors="coerce").astype(float)
    close = pd.to_numeric(data[close_col], errors="coerce").astype(float)
    return high, low, close


def _safe_normalizer(
    df: pd.DataFrame,
    *,
    close_col: str,
    normalizer_col: str | None,
    normalizer_mode: Literal["price", "return_vol"],
) -> pd.Series:
    close = pd.to_numeric(df[close_col], errors="coerce").astype(float)

    if normalizer_mode not in {"price", "return_vol"}:
        raise ValueError("normalizer_mode must be one of: 'price', 'return_vol'.")

    if normalizer_col is None:
        if normalizer_mode == "return_vol":
            raise ValueError(
                "normalizer_col must be provided when normalizer_mode='return_vol'."
            )
        base = close.abs()
    else:
        if normalizer_col not in df.columns:
            raise KeyError(f"normalizer_col '{normalizer_col}' not found in DataFrame.")
        raw = pd.to_numeric(df[normalizer_col], errors="coerce").astype(float)
        base = raw if normalizer_mode == "price" else close.abs() * raw

    return base.where(np.isfinite(base) & (base > 0.0), other=np.nan)


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.astype(float).div(
        denominator.where(np.isfinite(denominator) & (denominator > 0.0), other=np.nan)
    )


def _bars_since_event(event_mask: pd.Series) -> pd.Series:
    event = event_mask.fillna(False).astype(bool)
    positions = np.arange(len(event), dtype=float)
    last_event = pd.Series(
        np.where(event.to_numpy(), positions, np.nan),
        index=event.index,
        dtype=float,
    ).ffill()
    ages = pd.Series(positions, index=event.index, dtype=float) - last_event
    return ages.where(last_event.notna(), other=np.nan).astype("float32")


def _state_from_confirmed_relation(
    event_mask: pd.Series,
    event_prices: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    previous_price = event_prices.ffill().shift(1)
    relation_event = pd.Series(np.nan, index=event_prices.index, dtype=float)
    comparable = event_mask & event_prices.notna() & previous_price.notna()
    relation_event.loc[comparable] = np.sign(
        event_prices.loc[comparable] - previous_price.loc[comparable]
    )
    relation_state = relation_event.ffill()
    higher = (relation_state > 0.0).astype("int8")
    lower = (relation_state < 0.0).astype("int8")
    return higher, lower


def detect_local_extrema(
    data: pd.DataFrame | pd.Series,
    *,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    left_bars: int = 3,
    right_bars: int = 3,
    use_col_for_high: str = "high",
    use_col_for_low: str = "low",
    strict: bool = True,
) -> pd.DataFrame:
    """
    Detect raw local extrema around a centered window.

    Important:
    This function looks forward by `right_bars` and therefore the emitted `raw_*` columns are
    diagnostic/research outputs only. They must not be used as live model features without a
    separate confirmation shift.
    """
    left = _validate_bar_count(left_bars, field="left_bars", min_value=1)
    right = _validate_bar_count(right_bars, field="right_bars", min_value=1)
    if not isinstance(strict, bool):
        raise TypeError("strict must be boolean.")

    high, low, close = _resolve_extrema_sources(
        data,
        high_col=high_col,
        low_col=low_col,
        close_col=close_col,
        use_col_for_high=use_col_for_high,
        use_col_for_low=use_col_for_low,
    )
    index = close.index

    high_mask = high.notna()
    low_mask = low.notna()
    high_cmp = pd.Series.gt if strict else pd.Series.ge
    low_cmp = pd.Series.lt if strict else pd.Series.le

    for lag in range(1, left + 1):
        high_mask &= high_cmp(high, high.shift(lag))
        low_mask &= low_cmp(low, low.shift(lag))

    for lead in range(1, right + 1):
        high_mask &= high_cmp(high, high.shift(-lead))
        low_mask &= low_cmp(low, low.shift(-lead))

    out = pd.DataFrame(index=index)
    out["raw_local_high"] = high_mask.astype("int8")
    out["raw_local_low"] = low_mask.astype("int8")
    out["raw_local_high_price"] = high.where(high_mask).astype("float32")
    out["raw_local_low_price"] = low.where(low_mask).astype("float32")
    return out


def confirm_extrema_without_lookahead(
    raw_extrema: pd.DataFrame,
    *,
    right_bars: int,
) -> pd.DataFrame:
    """
    Shift raw extrema forward by `right_bars` so they only appear once they become knowable.

    Example:
    If a raw local high occurs at bar `i` and `right_bars=3`, the confirmed marker appears at
    bar `i+3`, not at `i`.
    """
    right = _validate_bar_count(right_bars, field="right_bars", min_value=1)
    required = [
        "raw_local_high",
        "raw_local_low",
        "raw_local_high_price",
        "raw_local_low_price",
    ]
    missing = [col for col in required if col not in raw_extrema.columns]
    if missing:
        raise KeyError(f"Missing raw extrema columns for confirmation: {missing}")

    out = pd.DataFrame(index=raw_extrema.index)
    out["confirmed_local_high"] = (
        pd.to_numeric(raw_extrema["raw_local_high"], errors="coerce")
        .shift(right)
        .fillna(0.0)
        .astype("int8")
    )
    out["confirmed_local_low"] = (
        pd.to_numeric(raw_extrema["raw_local_low"], errors="coerce")
        .shift(right)
        .fillna(0.0)
        .astype("int8")
    )
    out["confirmed_local_high_price"] = (
        pd.to_numeric(raw_extrema["raw_local_high_price"], errors="coerce")
        .shift(right)
        .astype("float32")
    )
    out["confirmed_local_low_price"] = (
        pd.to_numeric(raw_extrema["raw_local_low_price"], errors="coerce")
        .shift(right)
        .astype("float32")
    )
    return out


def build_last_confirmed_extrema_context(
    df: pd.DataFrame,
    *,
    confirmed_high_col: str = "confirmed_local_high",
    confirmed_low_col: str = "confirmed_local_low",
    confirmed_high_price_col: str = "confirmed_local_high_price",
    confirmed_low_price_col: str = "confirmed_local_low_price",
    close_col: str = "close",
    normalizer_col: str | None = None,
    normalizer_mode: Literal["price", "return_vol"] = "price",
    near_high_threshold_atr: float = 0.25,
    near_low_threshold_atr: float = 0.25,
    overextended_long_threshold_atr: float = 2.0,
    prefix: str = "swing",
) -> pd.DataFrame:
    """
    Build live-safe swing context features from confirmed extrema only.

    Notes:
    - `last_high_age` / `last_low_age` are measured from the confirmation bar, not the raw pivot
      bar, so they become 0.0 exactly when the extremum first becomes knowable in live trading.
    - All distances are normalized by `normalizer_col` when available. When
      `normalizer_mode='return_vol'`, the normalizer is converted into price units as
      `close * normalizer_col`.
    """
    normalized_prefix = _validate_prefix(prefix)
    required = [
        confirmed_high_col,
        confirmed_low_col,
        confirmed_high_price_col,
        confirmed_low_price_col,
        close_col,
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for confirmed extrema context: {missing}")

    for field_name, raw_value in (
        ("near_high_threshold_atr", near_high_threshold_atr),
        ("near_low_threshold_atr", near_low_threshold_atr),
        ("overextended_long_threshold_atr", overextended_long_threshold_atr),
    ):
        value = float(raw_value)
        if not math.isfinite(value):
            raise ValueError(f"{field_name} must be finite.")

    close = pd.to_numeric(df[close_col], errors="coerce").astype(float)
    normalizer = _safe_normalizer(
        df,
        close_col=close_col,
        normalizer_col=normalizer_col,
        normalizer_mode=normalizer_mode,
    )

    confirmed_high_event = pd.to_numeric(df[confirmed_high_col], errors="coerce").fillna(0.0).astype(bool)
    confirmed_low_event = pd.to_numeric(df[confirmed_low_col], errors="coerce").fillna(0.0).astype(bool)
    confirmed_high_price = pd.to_numeric(df[confirmed_high_price_col], errors="coerce").astype(float)
    confirmed_low_price = pd.to_numeric(df[confirmed_low_price_col], errors="coerce").astype(float)

    last_high = confirmed_high_price.where(confirmed_high_event).ffill()
    last_low = confirmed_low_price.where(confirmed_low_event).ffill()

    dist_to_last_high = _safe_divide(last_high - close, normalizer).astype("float32")
    dist_from_last_low = _safe_divide(close - last_low, normalizer).astype("float32")
    swing_range = (last_high - last_low).astype(float)
    swing_range_atr = _safe_divide(swing_range, normalizer).astype("float32")
    swing_position = _safe_divide(close - last_low, swing_range.where(swing_range > 0.0, other=np.nan)).astype(
        "float32"
    )

    higher_high, lower_high = _state_from_confirmed_relation(
        confirmed_high_event,
        confirmed_high_price.where(confirmed_high_event),
    )
    higher_low, lower_low = _state_from_confirmed_relation(
        confirmed_low_event,
        confirmed_low_price.where(confirmed_low_event),
    )

    above_high = last_high.notna() & close.gt(last_high)
    below_low = last_low.notna() & close.lt(last_low)
    high_breakout_event = above_high & ~above_high.shift(1, fill_value=False)
    low_breakdown_event = below_low & ~below_low.shift(1, fill_value=False)

    near_last_high = (
        last_high.notna()
        & _safe_divide((last_high - close).abs(), normalizer).le(float(near_high_threshold_atr))
    ).astype("int8")
    near_last_low = (
        last_low.notna()
        & _safe_divide((close - last_low).abs(), normalizer).le(float(near_low_threshold_atr))
    ).astype("int8")
    overextended_long = (
        dist_from_last_low.ge(float(overextended_long_threshold_atr)).fillna(False)
    ).astype("int8")

    out = pd.DataFrame(index=df.index)
    out[f"{normalized_prefix}_last_high"] = last_high.astype("float32")
    out[f"{normalized_prefix}_last_low"] = last_low.astype("float32")
    out[f"{normalized_prefix}_last_high_age"] = _bars_since_event(confirmed_high_event)
    out[f"{normalized_prefix}_last_low_age"] = _bars_since_event(confirmed_low_event)
    out[f"{normalized_prefix}_dist_to_last_high_atr"] = dist_to_last_high
    out[f"{normalized_prefix}_dist_from_last_low_atr"] = dist_from_last_low
    out[f"{normalized_prefix}_range_atr"] = swing_range_atr
    out[f"{normalized_prefix}_position_in_range"] = swing_position
    out[f"{normalized_prefix}_higher_high"] = higher_high
    out[f"{normalized_prefix}_higher_low"] = higher_low
    out[f"{normalized_prefix}_lower_high"] = lower_high
    out[f"{normalized_prefix}_lower_low"] = lower_low
    out[f"{normalized_prefix}_structure_score"] = (
        higher_high.astype(float)
        + higher_low.astype(float)
        - lower_high.astype(float)
        - lower_low.astype(float)
    ).astype("float32")
    out[f"{normalized_prefix}_bars_since_high_breakout"] = _bars_since_event(high_breakout_event)
    out[f"{normalized_prefix}_bars_since_low_breakdown"] = _bars_since_event(low_breakdown_event)
    out[f"{normalized_prefix}_near_last_high"] = near_last_high
    out[f"{normalized_prefix}_near_last_low"] = near_last_low
    out[f"{normalized_prefix}_overextended_long"] = overextended_long
    return out


def make_pre_extrema_research_label(
    raw_extrema: pd.DataFrame,
    *,
    lead_bars: int = 3,
    kind: Literal["high", "low"] = "high",
) -> pd.Series:
    """
    Build a future-looking research/target label for pre-extrema studies.

    Important:
    This output is not live-safe and must never be used as a model feature. It is intended for
    research labels or diagnostics only.
    """
    lead = _validate_bar_count(lead_bars, field="lead_bars", min_value=1)
    if kind not in {"high", "low"}:
        raise ValueError("kind must be one of: 'high', 'low'.")

    source_col = "raw_local_high" if kind == "high" else "raw_local_low"
    if source_col not in raw_extrema.columns:
        raise KeyError(f"Missing raw extrema column for research label: {source_col}")

    label_name = f"pre_local_{kind}_{lead}"
    shifted = pd.to_numeric(raw_extrema[source_col], errors="coerce").shift(-lead)
    return shifted.astype("float32").rename(label_name)


__all__ = [
    "detect_local_extrema",
    "confirm_extrema_without_lookahead",
    "build_last_confirmed_extrema_context",
    "make_pre_extrema_research_label",
]
