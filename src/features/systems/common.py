from __future__ import annotations

from dataclasses import dataclass
from numbers import Real

import numpy as np
import pandas as pd

from src.src_data.quote_contract import (
    QuoteColumnNames,
    SpreadSemantics,
    classify_spread_bps_semantics,
)


MIDPOINT_COLUMNS = ("mid_open", "mid_high", "mid_low", "mid_close")
FALLBACK_COLUMNS = ("open", "high", "low", "close")
BID_COLUMNS = ("bid_open", "bid_high", "bid_low", "bid_close")
ASK_COLUMNS = ("ask_open", "ask_high", "ask_low", "ask_close")
QUOTE_COLUMNS = BID_COLUMNS + ASK_COLUMNS

EXPECTED_BAR_MINUTES = 1.0
SMALL_GAP_MAX_MINUTES = 5.0
HARD_GAP_MINUTES = 30.0


@dataclass(frozen=True)
class MarketData:
    open: pd.Series
    high: pd.Series
    low: pd.Series
    close: pd.Series
    spread_bps: pd.Series
    source_mode: str

    def as_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "mid_open": self.open,
                "mid_high": self.high,
                "mid_low": self.low,
                "mid_close": self.close,
                "spread_bps": self.spread_bps,
            },
            index=self.close.index,
        )


@dataclass(frozen=True)
class GapDiagnostics:
    elapsed_minutes: pd.Series
    elapsed_bars: pd.Series
    missing_minutes: pd.Series
    is_gap: pd.Series
    is_small_gap: pd.Series
    is_hard_gap: pd.Series
    is_weekend_gap: pd.Series
    expected_market_gap: pd.Series
    unexpected_data_gap: pd.Series
    post_gap_age: pd.Series
    contiguous_bars: pd.Series


def compute_gap_diagnostics(
    index: pd.DatetimeIndex,
    *,
    expected_bar_minutes: float = EXPECTED_BAR_MINUTES,
    small_gap_max_minutes: float | None = None,
    hard_gap_minutes: float | None = None,
) -> GapDiagnostics:
    """Return causal timestamp-gap diagnostics for a regular-bar feature stream."""
    expected_bar_minutes = validate_bar_minutes(expected_bar_minutes)
    resolved_small_gap = (
        SMALL_GAP_MAX_MINUTES * expected_bar_minutes
        if small_gap_max_minutes is None
        else _positive_minutes(small_gap_max_minutes, field="small_gap_max_minutes")
    )
    resolved_hard_gap = (
        HARD_GAP_MINUTES * expected_bar_minutes
        if hard_gap_minutes is None
        else _positive_minutes(hard_gap_minutes, field="hard_gap_minutes")
    )
    if resolved_small_gap <= expected_bar_minutes:
        raise ValueError("small_gap_max_minutes must exceed expected_bar_minutes.")
    if resolved_hard_gap <= resolved_small_gap:
        raise ValueError("hard_gap_minutes must exceed small_gap_max_minutes.")

    size = len(index)
    elapsed = np.full(size, expected_bar_minutes, dtype=np.float64)
    if size > 1:
        elapsed[1:] = np.diff(index.asi8).astype(np.float64) / 60_000_000_000.0
    elapsed_series = pd.Series(elapsed, index=index, dtype="float64")
    is_gap = elapsed_series > expected_bar_minutes + 1e-9
    is_small_gap = is_gap & (elapsed_series <= resolved_small_gap)
    is_hard_gap = elapsed_series >= resolved_hard_gap

    weekend = np.zeros(size, dtype=bool)
    for position in np.flatnonzero(is_hard_gap.to_numpy(dtype=bool)):
        if position == 0:
            continue
        previous = index[position - 1]
        current = index[position]
        days = pd.date_range(previous.normalize(), current.normalize(), freq="D")
        weekend[position] = bool((days.dayofweek >= 5).any())
    is_weekend_gap = pd.Series(weekend, index=index, dtype=bool)
    expected_market_gap = is_hard_gap & is_weekend_gap
    unexpected_data_gap = is_hard_gap & ~expected_market_gap

    post_gap_age_values = np.zeros(size, dtype=np.int64)
    contiguous_values = np.zeros(size, dtype=np.int64)
    for position in range(size):
        if position == 0 or bool(is_gap.iloc[position]):
            post_gap_age_values[position] = 0
            contiguous_values[position] = 1
        else:
            post_gap_age_values[position] = post_gap_age_values[position - 1] + 1
            contiguous_values[position] = contiguous_values[position - 1] + 1

    return GapDiagnostics(
        elapsed_minutes=elapsed_series,
        elapsed_bars=(elapsed_series / expected_bar_minutes).astype("float64"),
        missing_minutes=(elapsed_series - expected_bar_minutes).clip(lower=0.0),
        is_gap=is_gap.astype(bool),
        is_small_gap=is_small_gap.astype(bool),
        is_hard_gap=is_hard_gap.astype(bool),
        is_weekend_gap=is_weekend_gap,
        expected_market_gap=expected_market_gap.astype(bool),
        unexpected_data_gap=unexpected_data_gap.astype(bool),
        post_gap_age=pd.Series(post_gap_age_values, index=index, dtype="int64"),
        contiguous_bars=pd.Series(contiguous_values, index=index, dtype="int64"),
    )


def validate_bar_minutes(value: object) -> float:
    """Return a finite positive bar duration expressed in minutes."""
    return _positive_minutes(value, field="bar_minutes")


def _positive_minutes(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a finite number > 0.")
    resolved = float(value)
    if not np.isfinite(resolved) or resolved <= 0.0:
        raise ValueError(f"{field} must be a finite number > 0.")
    return resolved


def validate_timestamp_index(df: pd.DataFrame) -> None:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("Quantitative feature systems require a pandas DatetimeIndex.")
    if not df.index.is_monotonic_increasing:
        raise ValueError("Quantitative feature systems require a monotonic increasing timestamp index.")
    if not df.index.is_unique:
        raise ValueError("Quantitative feature systems require unique timestamps.")


def prepare_market_data(df: pd.DataFrame) -> MarketData:
    """
    Validate OHLC/quote structure and return float64 midpoint series.

    Missing observations are preserved. Structural checks are applied wherever
    the required values for a row are finite; invalid finite rows are never
    silently repaired.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")
    validate_timestamp_index(df)

    present_quotes = [column for column in QUOTE_COLUMNS if column in df.columns]
    if present_quotes and len(present_quotes) != len(QUOTE_COLUMNS):
        missing = sorted(set(QUOTE_COLUMNS).difference(present_quotes))
        raise KeyError(f"Partial bid/ask OHLC input is not supported; missing columns: {missing}.")

    if len(present_quotes) == len(QUOTE_COLUMNS):
        bid = tuple(_numeric(df[column], field=column) for column in BID_COLUMNS)
        ask = tuple(_numeric(df[column], field=column) for column in ASK_COLUMNS)
        _validate_ohlc(*bid, owner="bid")
        for field, bid_values, ask_values in zip(("open", "high", "low", "close"), bid, ask):
            finite = bid_values.notna() & ask_values.notna()
            if bool((ask_values.loc[finite] < bid_values.loc[finite]).any()):
                raise ValueError(f"ask_{field} must be >= bid_{field} where both are finite.")
        _validate_ohlc(*ask, owner="ask")
        open_, high, low, close = tuple(
            ((bid_values + ask_values) / 2.0).astype("float64")
            for bid_values, ask_values in zip(bid, ask)
        )
        _validate_ohlc(open_, high, low, close, owner="midpoint")
        source_mode = "bid_ask"
        if "spread_bps" in df.columns:
            spread = _validate_spread(df["spread_bps"])
            quote_check = pd.DataFrame(
                {
                    "bid_close": bid[3],
                    "ask_close": ask[3],
                    "mid_close": close,
                    "spread_bps": spread,
                },
                index=df.index,
            ).dropna()
            if not quote_check.empty:
                semantics = classify_spread_bps_semantics(
                    quote_check,
                    columns=QuoteColumnNames(
                        bid="bid_close",
                        ask="ask_close",
                        mid="mid_close",
                        spread_bps="spread_bps",
                    ),
                )
                if semantics is not SpreadSemantics.CANONICAL_BPS:
                    raise ValueError(
                        "spread_bps does not match 10000 * (ask_close - bid_close) / "
                        f"mid_close; classified as {semantics.value}."
                    )
        else:
            spread = 10_000.0 * (ask[3] - bid[3]) / close
            spread = spread.where(close > 0.0).astype("float64")
    else:
        missing = [column for column in FALLBACK_COLUMNS if column not in df.columns]
        if missing:
            raise KeyError(
                "Quantitative feature systems require either full bid/ask OHLC "
                f"or fallback OHLC; missing fallback columns: {missing}."
            )
        open_, high, low, close = tuple(
            _numeric(df[column], field=column) for column in FALLBACK_COLUMNS
        )
        _validate_ohlc(open_, high, low, close, owner="fallback")
        source_mode = "fallback"
        spread = (
            _validate_spread(df["spread_bps"])
            if "spread_bps" in df.columns
            else pd.Series(np.nan, index=df.index, dtype="float64", name="spread_bps")
        )

    if "tick_volume" in df.columns:
        tick_volume = _numeric(df["tick_volume"], field="tick_volume")
        finite_volume = tick_volume.notna()
        if bool((tick_volume.loc[finite_volume] < 0.0).any()):
            raise ValueError("tick_volume must be >= 0 where finite.")

    return MarketData(
        open=open_.rename("mid_open"),
        high=high.rename("mid_high"),
        low=low.rename("mid_low"),
        close=close.rename("mid_close"),
        spread_bps=spread.rename("spread_bps"),
        source_mode=source_mode,
    )


def causal_baseline(
    series: pd.Series,
    *,
    window: int,
    statistic: str = "median",
    min_periods: int | None = None,
) -> pd.Series:
    resolved_min_periods = min_periods or min(window, max(5, window // 4))
    rolling = series.rolling(window=window, min_periods=resolved_min_periods)
    if statistic == "median":
        baseline = rolling.median()
    elif statistic == "mean":
        baseline = rolling.mean()
    else:
        raise ValueError("statistic must be one of: median, mean.")
    return baseline.shift(1).astype("float64")


def safe_ratio(
    numerator: pd.Series,
    denominator: pd.Series,
    *,
    epsilon: float,
    zero_over_zero: float | None = None,
) -> pd.Series:
    values = numerator.astype(float) / (denominator.astype(float) + float(epsilon))
    if zero_over_zero is not None:
        both_zero = numerator.eq(0.0) & denominator.eq(0.0)
        values = values.mask(both_zero, float(zero_over_zero))
    return values.replace([np.inf, -np.inf], np.nan).astype("float64")


def _numeric(series: pd.Series, *, field: str) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").astype("float64")
    original_missing = series.isna()
    coerced_invalid = values.isna() & ~original_missing
    if bool(coerced_invalid.any()):
        raise ValueError(f"{field} contains non-numeric values.")
    if bool(np.isinf(values.to_numpy(dtype=float)).any()):
        raise ValueError(f"{field} must not contain infinite values.")
    return values


def _validate_spread(series: pd.Series) -> pd.Series:
    spread = _numeric(series, field="spread_bps")
    finite = spread.notna()
    if bool((spread.loc[finite] < 0.0).any()):
        raise ValueError("spread_bps must be >= 0 where finite.")
    return spread


def _validate_ohlc(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    *,
    owner: str,
) -> None:
    fields = {"open": open_, "high": high, "low": low, "close": close}
    for field, values in fields.items():
        finite = values.notna()
        if bool((values.loc[finite] <= 0.0).any()):
            raise ValueError(f"{owner}_{field} prices must be > 0 where finite.")

    complete = open_.notna() & high.notna() & low.notna() & close.notna()
    if not bool(complete.any()):
        return
    complete_open = open_.loc[complete]
    complete_high = high.loc[complete]
    complete_low = low.loc[complete]
    complete_close = close.loc[complete]
    if bool((complete_high < np.maximum(complete_open, complete_close)).any()):
        raise ValueError(f"{owner} high must be >= max(open, close).")
    if bool((complete_low > np.minimum(complete_open, complete_close)).any()):
        raise ValueError(f"{owner} low must be <= min(open, close).")
    if bool((complete_high < complete_low).any()):
        raise ValueError(f"{owner} high must be >= low.")


__all__ = [
    "ASK_COLUMNS",
    "BID_COLUMNS",
    "EXPECTED_BAR_MINUTES",
    "FALLBACK_COLUMNS",
    "GapDiagnostics",
    "HARD_GAP_MINUTES",
    "MIDPOINT_COLUMNS",
    "MarketData",
    "SMALL_GAP_MAX_MINUTES",
    "causal_baseline",
    "compute_gap_diagnostics",
    "prepare_market_data",
    "safe_ratio",
    "validate_bar_minutes",
    "validate_timestamp_index",
]
