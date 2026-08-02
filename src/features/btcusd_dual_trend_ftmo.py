from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd


REQUIRED_OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")


def validate_btcusd_1m_data(
    df: pd.DataFrame,
    *,
    source_timezone: str = "UTC",
    output_timezone: str = "UTC",
) -> pd.DataFrame:
    """Validate and normalize the locked BTCUSD source contract without sorting or filling."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("BTCUSD source data must be a pandas DataFrame.")
    missing = sorted(set(REQUIRED_OHLCV_COLUMNS).difference(df.columns))
    if missing:
        raise ValueError(f"Missing required BTCUSD OHLCV columns: {missing}.")
    if source_timezone != "UTC" or output_timezone != "UTC":
        raise ValueError("BTCUSD Dual-Trend v1 requires explicit UTC source and output timezones.")

    out = df.loc[:, list(REQUIRED_OHLCV_COLUMNS)].copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        try:
            parsed = pd.to_datetime(out.index, errors="raise")
        except (TypeError, ValueError) as exc:
            raise ValueError("BTCUSD timestamps must be unambiguous datetimes.") from exc
        if not isinstance(parsed, pd.DatetimeIndex):
            raise ValueError("BTCUSD timestamps contain mixed or ambiguous timezone values.")
        out.index = parsed

    index = out.index
    if index.tz is None:
        try:
            index = index.tz_localize(source_timezone, ambiguous="raise", nonexistent="raise")
        except (TypeError, ValueError) as exc:
            raise ValueError("BTCUSD timestamps are timezone-ambiguous.") from exc
    else:
        index = index.tz_convert(output_timezone)
    out.index = index
    out.index.name = "timestamp"

    if out.index.has_duplicates:
        raise ValueError("BTCUSD timestamps must be unique; duplicates were found.")
    if not out.index.is_monotonic_increasing:
        raise ValueError("BTCUSD timestamps must be chronological and monotonic increasing.")

    for column in REQUIRED_OHLCV_COLUMNS:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    if out[list(REQUIRED_OHLCV_COLUMNS)].isna().any().any():
        raise ValueError("BTCUSD OHLCV values must be numeric and non-missing; no OHLC fill is allowed.")
    values = out[list(REQUIRED_OHLCV_COLUMNS)].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("BTCUSD OHLCV values must be finite.")

    open_ = out["open"].to_numpy(dtype=float)
    high = out["high"].to_numpy(dtype=float)
    low = out["low"].to_numpy(dtype=float)
    close = out["close"].to_numpy(dtype=float)
    if np.any(np.column_stack((open_, high, low, close)) <= 0.0):
        raise ValueError("BTCUSD OHLC prices, including close, must be positive.")
    if np.any(low > high):
        raise ValueError("Invalid BTCUSD OHLC: low exceeds high.")
    if np.any((open_ < low) | (open_ > high)):
        raise ValueError("Invalid BTCUSD OHLC: open lies outside [low, high].")
    if np.any((close < low) | (close > high)):
        raise ValueError("Invalid BTCUSD OHLC: close lies outside [low, high].")
    if np.any(out["volume"].to_numpy(dtype=float) < 0.0):
        raise ValueError("BTCUSD volume must be non-negative.")
    return out.astype(float)


def aggregate_btcusd_1m_to_30m(df: pd.DataFrame) -> pd.DataFrame:
    """Build real right-labeled/right-closed 30-minute OHLCV bars."""
    source = validate_btcusd_1m_data(df)
    aggregated = source.resample("30min", label="right", closed="right").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        source_rows=("close", "count"),
    )
    aggregated = aggregated.loc[aggregated["source_rows"].gt(0)].copy()
    aggregated["source_rows"] = aggregated["source_rows"].astype(int)
    return aggregated


def _persistent_donchian_state(
    close: pd.Series,
    prior_high: pd.Series,
    prior_low: pd.Series,
) -> pd.Series:
    state = 0.0
    values = np.zeros(len(close), dtype=float)
    close_values = close.to_numpy(dtype=float)
    high_values = prior_high.to_numpy(dtype=float)
    low_values = prior_low.to_numpy(dtype=float)
    for offset in range(len(close_values)):
        if np.isfinite(high_values[offset]) and close_values[offset] > high_values[offset]:
            state = 1.0
        elif np.isfinite(low_values[offset]) and close_values[offset] < low_values[offset]:
            state = -1.0
        values[offset] = state
    return pd.Series(values, index=close.index, name="donchian_state", dtype=float)


def add_btcusd_dual_trend_30m_features(
    df: pd.DataFrame,
    *,
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    volume_col: str = "volume",
    ema_fast_span: int = 96,
    ema_slow_span: int = 672,
    donchian_window: int = 336,
    volatility_ewma_span: int = 336,
    periods_per_year: int = 17_520,
    ema_weight: float = 0.60,
    donchian_weight: float = 0.40,
    execution_return_mode: str = "next_open_to_next_open",
    adverse_excursion_mode: str = "next_30m_high_low",
) -> pd.DataFrame:
    """Add the locked dual-trend features and separately marked future outcome columns.

    YAML declaration::

        features:
          - step: btcusd_dual_trend_30m
            params:
              ema_fast_span: 96
              ema_slow_span: 672
              donchian_window: 336
              volatility_ewma_span: 336
              periods_per_year: 17520
              ema_weight: 0.60
              donchian_weight: 0.40

    Required input columns
    ----------------------
    open_col, high_col, low_col, close_col, volume_col:
        Validated UTC BTCUSD 30-minute OHLCV bars. The frame must be unique and
        chronological and must not contain forward-filled OHLC values.

    Parameters
    ----------
    ema_fast_span, ema_slow_span:
        Log-close EMA spans evaluated with ``adjust=False``.
    donchian_window:
        Prior-only breakout window applied after ``shift(1)``.
    volatility_ewma_span, periods_per_year:
        EWM standard-deviation span and fixed 365-by-48 annualization.
    ema_weight, donchian_weight:
        Ensemble weights, which must sum to one.
    execution_return_mode, adverse_excursion_mode:
        Locked realized-return conventions; these outputs are never signal inputs.
    """
    required = {open_col, high_col, low_col, close_col, volume_col}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise KeyError(f"Missing BTCUSD 30m feature inputs: {missing}.")
    if not isinstance(df.index, pd.DatetimeIndex) or df.index.tz is None:
        raise ValueError("BTCUSD 30m feature index must be timezone-aware UTC.")
    if str(df.index.tz) != "UTC":
        raise ValueError("BTCUSD 30m feature index must use UTC.")
    if df.index.has_duplicates or not df.index.is_monotonic_increasing:
        raise ValueError("BTCUSD 30m feature index must be unique and chronological.")
    if min(ema_fast_span, ema_slow_span, donchian_window, volatility_ewma_span) <= 0:
        raise ValueError("All BTCUSD feature spans/windows must be positive.")
    if periods_per_year != 365 * 48:
        raise ValueError("BTCUSD Dual-Trend v1 periods_per_year must equal 365 * 48 (17520).")
    if not np.isclose(float(ema_weight) + float(donchian_weight), 1.0):
        raise ValueError("EMA and Donchian weights must sum to 1.0.")
    if execution_return_mode != "next_open_to_next_open":
        raise ValueError("Unsupported BTCUSD execution return mode.")
    if adverse_excursion_mode != "next_30m_high_low":
        raise ValueError("Unsupported BTCUSD adverse-excursion mode.")

    out = df.copy()
    open_ = out[open_col].astype(float)
    high = out[high_col].astype(float)
    low = out[low_col].astype(float)
    close = out[close_col].astype(float)
    if close.le(0.0).any():
        raise ValueError("BTCUSD close must be positive before taking logarithms.")

    log_close = np.log(close)
    ema_fast = log_close.ewm(span=int(ema_fast_span), adjust=False).mean()
    ema_slow = log_close.ewm(span=int(ema_slow_span), adjust=False).mean()
    ema_signal = np.sign(ema_fast - ema_slow).astype(float)
    prior_high = high.shift(1).rolling(int(donchian_window)).max()
    prior_low = low.shift(1).rolling(int(donchian_window)).min()
    donchian_state = _persistent_donchian_state(close, prior_high, prior_low)
    ensemble = (
        float(ema_weight) * ema_signal + float(donchian_weight) * donchian_state
    ).clip(lower=-1.0, upper=1.0)
    close_log_return = log_close.diff()
    volatility_ann = (
        close_log_return.ewm(span=int(volatility_ewma_span), adjust=False).std()
        * np.sqrt(float(periods_per_year))
    )
    next_open = open_.shift(-1)

    out["log_close"] = log_close
    out["ema_fast"] = ema_fast
    out["ema_slow"] = ema_slow
    out["ema_signal"] = ema_signal
    out["prior_high"] = prior_high
    out["prior_low"] = prior_low
    out["donchian_state"] = donchian_state
    out["ensemble_signal"] = ensemble
    out["close_log_return"] = close_log_return
    out["volatility_ann"] = volatility_ann
    # The following are realized outcome/accounting columns. The signal layer is
    # contractually restricted to ensemble_signal and volatility_ann.
    out["execution_return"] = open_.shift(-2) / next_open - 1.0
    out["adverse_long_return"] = low.shift(-1) / next_open - 1.0
    out["adverse_short_price_return"] = high.shift(-1) / next_open - 1.0
    return out


def feature_output_mapping(step: Mapping[str, Any]) -> dict[str, str]:
    """Return and validate the declarative output mapping used by the custom pipeline."""
    outputs = dict(step.get("outputs", {}) or {})
    expected = {
        "ema_fast",
        "ema_slow",
        "ema_signal",
        "prior_high",
        "prior_low",
        "donchian_state",
        "ensemble_signal",
        "volatility_ann",
        "execution_return",
        "adverse_long_return",
        "adverse_short_price_return",
    }
    if set(outputs) != expected:
        raise ValueError(f"Locked BTCUSD feature outputs must be exactly {sorted(expected)}.")
    return {str(key): str(value) for key, value in outputs.items()}


__all__ = [
    "REQUIRED_OHLCV_COLUMNS",
    "add_btcusd_dual_trend_30m_features",
    "aggregate_btcusd_1m_to_30m",
    "feature_output_mapping",
    "validate_btcusd_1m_data",
]
