"""Causal Trend-VWAP pullback candidate and model feature ladder.

The component implements the deterministic, pre-model part of the US100 M30
expected-R experiment.  ``stage`` mirrors YAML0 through YAML8: every stage
emits the cumulative feature set and activates only the deterministic gates
introduced up to that point.  YAML9 and YAML10 reuse stage 8 unchanged.

All features are available at the close of the current bar.  Historical
normalizers compare the current observation with a window shifted by one bar;
the candidate is a false-to-true event pulse and is intended for execution at
the next bar open.
"""

from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd

from ._ehlers import compute_decycler, compute_mesa_components
from .hilbert_transform import add_hilbert_transform
from .roofing_filter import add_roofing_filter
from .session_context import index_in_timezone
from .technical.mfi import compute_mfi
from .technical.ppo import compute_ppo
from .technical.stochastic_rsi import compute_stochastic_rsi


_EPSILON = 1e-12
_RETURN_HORIZONS = (1, 2, 4, 8, 16)


def _require_columns(df: pd.DataFrame, columns: tuple[str, ...]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for trend_vwap_pullback_candidate: {missing}")


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Divide numeric series and replace invalid results with missing values."""
    den = pd.to_numeric(denominator, errors="coerce").astype(float)
    den = den.where(den.abs() > _EPSILON)
    result = pd.to_numeric(numerator, errors="coerce").astype(float) / den
    return result.replace([np.inf, -np.inf], np.nan)


def _shifted_zscore(values: pd.Series, window: int) -> pd.Series:
    history = pd.to_numeric(values, errors="coerce").astype(float)
    prior_rows = history.shift(1)
    mean = prior_rows.rolling(window, min_periods=window).mean()
    std = prior_rows.rolling(window, min_periods=window).std(ddof=1)
    return _safe_divide(history - mean, std)


def _shifted_robust_zscore(values: pd.Series, window: int) -> pd.Series:
    history = pd.to_numeric(values, errors="coerce").astype(float)
    prior_rows = history.shift(1)
    median = prior_rows.rolling(window, min_periods=window).median()
    mad = prior_rows.rolling(window, min_periods=window).apply(
        lambda sample: float(np.median(np.abs(sample - np.median(sample)))),
        raw=True,
    )
    return _safe_divide(history - median, 1.4826 * mad)


def _shifted_percent_rank(values: pd.Series, window: int) -> pd.Series:
    """Rank each current value against exactly the preceding ``window`` rows."""
    numeric = pd.to_numeric(values, errors="coerce").astype(float).to_numpy()
    result = np.full(numeric.size, np.nan, dtype=float)
    if numeric.size <= window:
        return pd.Series(result, index=values.index, dtype=float)
    windows = np.lib.stride_tricks.sliding_window_view(numeric, window + 1)
    history = windows[:, :-1]
    current = windows[:, -1]
    valid = np.isfinite(current) & np.isfinite(history).all(axis=1)
    ranks = np.full(len(windows), np.nan, dtype=float)
    ranks[valid] = np.mean(history[valid] <= current[valid, None], axis=1)
    result[window:] = ranks
    return pd.Series(result, index=values.index, dtype=float)


def _clock_minutes(value: str, *, field: str) -> int:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string in HH:MM format.")
    parts = value.strip().split(":")
    if len(parts) != 2 or any(not part.isdigit() for part in parts):
        raise ValueError(f"{field} must use HH:MM format.")
    hour, minute = (int(part) for part in parts)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"{field} must be a valid local clock time.")
    return hour * 60 + minute


def _session_window_mask(
    local_index: pd.DatetimeIndex,
    index: pd.Index,
    *,
    session_open: str,
    session_close: str,
    timestamp_convention: str,
) -> pd.Series:
    open_minute = _clock_minutes(session_open, field="session_open")
    close_minute = _clock_minutes(session_close, field="session_close")
    if close_minute <= open_minute:
        raise ValueError("session_close must be later than session_open for the US cash-session contract.")
    convention = str(timestamp_convention).strip().lower()
    minutes = local_index.hour * 60 + local_index.minute
    if convention == "bar_start":
        intraday = (minutes >= open_minute) & (minutes < close_minute)
    elif convention == "bar_close":
        intraday = (minutes > open_minute) & (minutes <= close_minute)
    else:
        raise ValueError("timestamp_convention must be 'bar_start' or 'bar_close'.")
    weekday = local_index.dayofweek < 5
    return pd.Series(intraday & weekday, index=index, dtype=bool)


def _rolling_log_regression(close: pd.Series, window: int = 96) -> tuple[pd.Series, pd.Series]:
    """Return causal rolling log-price slope and coefficient of determination."""
    log_price = np.log(pd.to_numeric(close, errors="coerce").astype(float).where(close > 0.0))
    values = log_price.to_numpy(dtype=float)
    slope = np.full(len(values), np.nan, dtype=float)
    r_squared = np.full(len(values), np.nan, dtype=float)
    if len(values) < window:
        return pd.Series(slope, index=close.index), pd.Series(r_squared, index=close.index)

    x = np.arange(window, dtype=float)
    centered_x = x - x.mean()
    sum_x2 = float(np.dot(centered_x, centered_x))
    sample_windows = np.lib.stride_tricks.sliding_window_view(values, window)
    valid = np.isfinite(sample_windows).all(axis=1)
    if bool(valid.any()):
        samples = sample_windows[valid]
        centered_y = samples - samples.mean(axis=1, keepdims=True)
        covariance = centered_y @ centered_x
        variance_y = np.sum(centered_y * centered_y, axis=1)
        slopes = covariance / sum_x2
        denominators = sum_x2 * variance_y
        scores = np.divide(
            covariance * covariance,
            denominators,
            out=np.zeros_like(covariance),
            where=denominators > _EPSILON,
        )
        valid_positions = np.flatnonzero(valid) + window - 1
        slope[valid_positions] = slopes
        r_squared[valid_positions] = np.clip(scores, 0.0, 1.0)
    return pd.Series(slope, index=close.index), pd.Series(r_squared, index=close.index)


def _session_vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    *,
    timezone: str,
    session_open: str = "09:30",
    session_close: str = "16:00",
    timestamp_convention: str = "bar_start",
) -> tuple[pd.Series, pd.DatetimeIndex]:
    """Compute cash-session VWAP and freeze it outside the configured window."""
    local_index = index_in_timezone(close.index, timezone)
    cash_mask = _session_window_mask(
        local_index,
        close.index,
        session_open=session_open,
        session_close=session_close,
        timestamp_convention=timestamp_convention,
    )
    session_dates = pd.Series(local_index.date, index=close.index, dtype="object")
    typical = (high + low + close) / 3.0
    valid_volume = pd.to_numeric(volume, errors="coerce").astype(float).where(volume > 0.0)
    numerator = (typical * valid_volume).where(cash_mask)
    denominator = valid_volume.where(cash_mask)
    cumulative_numerator = numerator.groupby(session_dates, sort=False).cumsum()
    cumulative_denominator = denominator.groupby(session_dates, sort=False).cumsum()
    # Outside-session rows must not update the cash statistic, but retaining
    # the latest completed cash value keeps downstream row-window features on
    # a fixed elapsed-bar contract.  Eligibility is gated separately.
    session_vwap = _safe_divide(cumulative_numerator, cumulative_denominator).ffill()
    return session_vwap, local_index


def transition_pulse(state: pd.Series) -> pd.Series:
    """Convert a persistent boolean state into false-to-true event pulses."""
    current = state.fillna(False).astype(bool)
    return current & ~current.shift(1, fill_value=False).astype(bool)


def _bars_since_prior_event(event: pd.Series) -> pd.Series:
    values = event.fillna(False).astype(bool).to_numpy()
    result = np.full(len(values), np.nan, dtype=float)
    previous_event: int | None = None
    for idx in range(len(values)):
        if previous_event is not None:
            result[idx] = float(idx - previous_event)
        if bool(values[idx]):
            previous_event = idx
    return pd.Series(result, index=event.index, dtype=float)


def _add_core_features(
    out: pd.DataFrame,
    *,
    timezone: str,
    session_open: str,
    session_close: str,
    timestamp_convention: str,
) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    high = pd.to_numeric(out["high"], errors="coerce").astype(float)
    low = pd.to_numeric(out["low"], errors="coerce").astype(float)
    close = pd.to_numeric(out["close"], errors="coerce").astype(float)
    volume = pd.to_numeric(out["volume"], errors="coerce").astype(float)

    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low).abs(), (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    out["true_range"] = true_range.astype("float32")
    out["atr_20"] = true_range.rolling(20, min_periods=20).mean().astype("float32")
    atr = out["atr_20"].astype(float)
    out["atr_over_price_20"] = _safe_divide(atr, close).astype("float32")

    for span in (50, 100):
        out[f"ema_{span}"] = close.ewm(span=span, adjust=False, min_periods=span).mean().astype("float32")

    session_vwap, local_index = _session_vwap(
        high,
        low,
        close,
        volume,
        timezone=timezone,
        session_open=session_open,
        session_close=session_close,
        timestamp_convention=timestamp_convention,
    )
    out["session_vwap"] = session_vwap.astype("float32")
    out["d_vwap_atr"] = _safe_divide(close - session_vwap, atr).astype("float32")
    out["d_vwap_pct"] = (_safe_divide(close, session_vwap) - 1.0).astype("float32")
    out["d_ema50_atr"] = _safe_divide(close - out["ema_50"], atr).astype("float32")
    out["ema50_ema100_spread_atr"] = _safe_divide(
        out["ema_50"] - out["ema_100"], atr
    ).astype("float32")

    for horizon in (1, 4):
        values = close.div(close.shift(horizon)).sub(1.0)
        out[f"return_{horizon}"] = values.astype("float32")
    out["return_4_atr"] = _safe_divide(out["return_4"], out["atr_over_price_20"]).astype("float32")

    reclaim = (
        close.gt(session_vwap)
        & (
            previous_close.le(session_vwap.shift(1))
            | out["d_vwap_atr"].shift(1).le(0.10)
        )
    )
    out["vwap_reclaim_cross"] = reclaim.fillna(False).astype("int8")
    return out, local_index


def _add_return_features(out: pd.DataFrame) -> pd.DataFrame:
    close = out["close"].astype(float)
    out["log_return_1"] = np.log(close.div(close.shift(1))).replace([np.inf, -np.inf], np.nan).astype("float32")
    for horizon in _RETURN_HORIZONS:
        return_col = f"return_{horizon}"
        if return_col not in out.columns:
            out[return_col] = close.div(close.shift(horizon)).sub(1.0).astype("float32")
        out[f"return_{horizon}_atr"] = _safe_divide(
            out[return_col], out["atr_over_price_20"]
        ).astype("float32")

    vol96 = out["return_1"].astype(float).rolling(96, min_periods=96).std(ddof=1).shift(1)
    for horizon in _RETURN_HORIZONS:
        out[f"return_{horizon}_vol96"] = _safe_divide(
            out[f"return_{horizon}"], vol96 * np.sqrt(float(horizon))
        ).astype("float32")
    for horizon in (1, 4, 8):
        out[f"return_{horizon}_robust_z96"] = _shifted_robust_zscore(
            out[f"return_{horizon}"], 96
        ).astype("float32")

    normalized = [f"return_{horizon}_atr" for horizon in _RETURN_HORIZONS]
    normalized += [f"return_{horizon}_vol96" for horizon in _RETURN_HORIZONS]
    normalized += [f"return_{horizon}_robust_z96" for horizon in (1, 4, 8)]
    for column in normalized:
        for lag in (1, 2, 3):
            out[f"{column}_lag_{lag}"] = out[column].shift(lag).astype("float32")
    return out


def _add_trend_features(out: pd.DataFrame) -> pd.DataFrame:
    close = out["close"].astype(float)
    atr = out["atr_20"].astype(float)
    out["ema_20"] = close.ewm(span=20, adjust=False, min_periods=20).mean().astype("float32")
    out["d_ema20_atr"] = _safe_divide(close - out["ema_20"], atr).astype("float32")
    out["ema20_slope_5_atr"] = _safe_divide(out["ema_20"].diff(5), 5.0 * atr).astype("float32")
    out["ema50_slope_5_atr"] = _safe_divide(out["ema_50"].diff(5), 5.0 * atr).astype("float32")
    out["ema50_slope_10_atr"] = _safe_divide(out["ema_50"].diff(10), 10.0 * atr).astype("float32")
    slope, r_squared = _rolling_log_regression(close, 96)
    out["rolling_log_price_slope_96"] = slope.astype("float32")
    out["rolling_log_price_r2_96"] = r_squared.astype("float32")
    return out


def _add_vwap_features(out: pd.DataFrame) -> pd.DataFrame:
    high = out["high"].astype(float)
    low = out["low"].astype(float)
    close = out["close"].astype(float)
    volume = out["volume"].astype(float)
    atr = out["atr_20"].astype(float)
    typical = (high + low + close) / 3.0
    numerator = (typical * volume).rolling(40, min_periods=40).sum()
    denominator = volume.rolling(40, min_periods=40).sum()
    out["rolling_vwap_40"] = _safe_divide(numerator, denominator).astype("float32")
    out["session_vwap_slope_5_atr"] = _safe_divide(
        out["session_vwap"].diff(5), 5.0 * atr
    ).astype("float32")
    out["d_rolling_vwap40_atr"] = _safe_divide(close - out["rolling_vwap_40"], atr).astype("float32")
    out["d_vwap_atr_robust_z96"] = _shifted_robust_zscore(out["d_vwap_atr"], 96).astype("float32")
    out["d_vwap_atr_percent_rank_252"] = _shifted_percent_rank(out["d_vwap_atr"], 252).astype("float32")
    for lag in (1, 2, 3, 4):
        out[f"d_vwap_atr_lag_{lag}"] = out["d_vwap_atr"].shift(lag).astype("float32")
    loss = close.lt(out["session_vwap"]) & close.shift(1).ge(out["session_vwap"].shift(1))
    out["vwap_loss_cross"] = loss.fillna(False).astype("int8")
    return out


def _add_path_features(out: pd.DataFrame) -> pd.DataFrame:
    distance = out["d_vwap_atr"].astype(float)
    out["prior_8_max_d_vwap_atr"] = distance.shift(1).rolling(8, min_periods=8).max().astype("float32")
    out["prior_4_min_d_vwap_atr"] = distance.shift(1).rolling(4, min_periods=4).min().astype("float32")
    out["pullback_depth_atr"] = (
        out["prior_8_max_d_vwap_atr"].astype(float) - distance
    ).astype("float32")
    out["bars_since_d_vwap_expansion_080"] = _bars_since_prior_event(distance.ge(0.80)).astype("float32")
    return out


def _add_momentum_features(out: pd.DataFrame) -> pd.DataFrame:
    ppo = compute_ppo(
        out["close"].astype(float),
        fast=12,
        slow=26,
        signal=9,
        ppo_col="ppo_12_26",
        ppo_signal_col="ppo_signal_9",
        ppo_hist_col="ppo_hist_12_26_9",
    )
    out = out.join(ppo)
    histogram = out["ppo_hist_12_26_9"].astype(float)
    out["ppo_hist_diff_1"] = histogram.diff(1).astype("float32")
    out["ppo_hist_diff_2"] = histogram.diff(2).astype("float32")
    out["ppo_hist_zero_cross"] = (
        histogram.gt(0.0) & histogram.shift(1).le(0.0)
    ).fillna(False).astype("int8")

    stoch = compute_stochastic_rsi(
        out["close"].astype(float),
        rsi_period=14,
        stoch_period=14,
        k_period=3,
        d_period=3,
        prefix="stoch_rsi_14",
    )
    out = out.join(stoch)
    k = out["stoch_rsi_14_k"].astype(float)
    d = out["stoch_rsi_14_d"].astype(float)
    out["stoch_rsi_bullish_cross"] = (k.gt(d) & k.shift(1).le(d.shift(1))).fillna(False).astype("int8")
    out["stoch_rsi_bearish_cross"] = (k.lt(d) & k.shift(1).ge(d.shift(1))).fillna(False).astype("int8")
    out["mfi_14"] = compute_mfi(
        out["high"].astype(float),
        out["low"].astype(float),
        out["close"].astype(float),
        out["volume"].astype(float),
        window=14,
    ).astype("float32")
    out["mfi_14_centered"] = ((out["mfi_14"].astype(float) - 50.0) / 50.0).astype("float32")
    return out


def _add_ehlers_features(out: pd.DataFrame) -> pd.DataFrame:
    close = out["close"].astype(float)
    close_values = close.to_numpy(dtype=float)
    atr = out["atr_20"].astype(float)
    mesa = compute_mesa_components(close_values, fast_limit=0.5, slow_limit=0.05)
    out["mama"] = mesa["mama"].astype("float32")
    out["fama"] = mesa["fama"].astype("float32")
    out["mama_fama_spread_atr"] = _safe_divide(out["mama"] - out["fama"], atr).astype("float32")
    out["mama_fama_bullish_cross"] = (
        out["mama"].gt(out["fama"]) & out["mama"].shift(1).le(out["fama"].shift(1))
    ).fillna(False).astype("int8")

    out["decycler_30"] = compute_decycler(close_values, period=30).astype("float32")
    out["decycler_60"] = compute_decycler(close_values, period=60).astype("float32")
    out["decycler_oscillator_30_60_atr"] = _safe_divide(
        out["decycler_30"] - out["decycler_60"], atr
    ).astype("float32")

    out = add_roofing_filter(
        out,
        price_col="close",
        high_pass_period=48,
        low_pass_period=10,
        output_col="roofing_filter_48_10",
    )
    roofing = out["roofing_filter_48_10"].astype(float)
    out["roofing_filter_48_10_robust_z96"] = _shifted_robust_zscore(roofing, 96).astype("float32")
    out["roofing_filter_slope_atr"] = _safe_divide(roofing.diff(1), atr).astype("float32")
    out["roofing_filter_zero_cross"] = (
        roofing.gt(0.0) & roofing.shift(1).le(0.0)
    ).fillna(False).astype("int8")

    powers: list[pd.Series] = []
    periods = np.arange(10, 49, dtype=float)
    for lag in periods.astype(int):
        correlation = close.rolling(96 - lag, min_periods=96 - lag).corr(close.shift(lag))
        powers.append(correlation.clip(lower=0.0).pow(2.0))
    power_frame = pd.concat(powers, axis=1)
    power_frame.columns = periods
    total_power = power_frame.sum(axis=1).where(lambda values: values > _EPSILON)
    out["acp_dominant_period_10_48"] = _safe_divide(
        power_frame.mul(periods, axis=1).sum(axis=1), total_power
    ).astype("float32")
    out["acp_power_10_48"] = power_frame.max(axis=1).where(total_power.notna()).astype("float32")
    out["acp_period_std_24"] = (
        out["acp_dominant_period_10_48"].astype(float).rolling(24, min_periods=24).std(ddof=1).shift(1)
    ).astype("float32")

    out = add_hilbert_transform(
        out,
        price_col="close",
        window=64,
        amplitude_col="hilbert_amplitude_64",
        phase_col="hilbert_phase_64",
        instantaneous_frequency_col="hilbert_frequency_64",
        add_derived=False,
    )
    out["hilbert_amplitude_64_atr"] = _safe_divide(out["hilbert_amplitude_64"], atr).astype("float32")
    phase = out["hilbert_phase_64"].astype(float)
    out["hilbert_phase_sin_64"] = np.sin(phase).astype("float32")
    out["hilbert_phase_cos_64"] = np.cos(phase).astype("float32")
    frequency = out["hilbert_frequency_64"].astype(float).abs()
    out["hilbert_period_64"] = _safe_divide(pd.Series(1.0, index=out.index), frequency).clip(6.0, 100.0).astype("float32")
    return out


def _add_context_features(out: pd.DataFrame, local_index: pd.DatetimeIndex) -> pd.DataFrame:
    close = out["close"].astype(float)
    high = out["high"].astype(float)
    low = out["low"].astype(float)
    volume = out["volume"].astype(float)
    true_range = out["true_range"].astype(float)
    atr20 = out["atr_20"].astype(float)

    out["atr_percent_rank_252"] = _shifted_percent_rank(out["atr_over_price_20"], 252).astype("float32")
    out["atr_over_price_z96"] = _shifted_zscore(out["atr_over_price_20"], 96).astype("float32")
    atr10 = true_range.rolling(10, min_periods=10).mean()
    atr40 = true_range.rolling(40, min_periods=40).mean()
    out["atr_short_long_ratio_10_40"] = _safe_divide(atr10, atr40).astype("float32")
    out["rolling_volatility_24"] = (
        out["return_1"].astype(float).rolling(24, min_periods=24).std(ddof=1).shift(1)
    ).astype("float32")
    out["rolling_volatility_96"] = (
        out["return_1"].astype(float).rolling(96, min_periods=96).std(ddof=1).shift(1)
    ).astype("float32")
    out["volatility_ratio_24_96"] = _safe_divide(
        out["rolling_volatility_24"], out["rolling_volatility_96"]
    ).astype("float32")
    out["volatility_of_volatility_24"] = (
        out["rolling_volatility_24"].astype(float).rolling(24, min_periods=24).std(ddof=1).shift(1)
    ).astype("float32")
    out["relative_volume_96"] = _safe_divide(
        volume, volume.shift(1).rolling(96, min_periods=96).mean()
    ).astype("float32")
    out["volume_z96"] = _shifted_zscore(volume, 96).astype("float32")
    prior_low = low.shift(1).rolling(96, min_periods=96).min()
    prior_high = high.shift(1).rolling(96, min_periods=96).max()
    out["range_position_96"] = _safe_divide(close - prior_low, prior_high - prior_low).astype("float32")
    out["bar_range_atr"] = _safe_divide(high - low, atr20).astype("float32")
    out["close_location_value"] = (_safe_divide(2.0 * close - high - low, high - low)).astype("float32")

    minutes_of_day = local_index.hour * 60 + local_index.minute
    day_of_week = local_index.dayofweek.to_numpy(dtype=float)
    out["hour_sin_24"] = np.sin(2.0 * np.pi * minutes_of_day / 1440.0).astype("float32")
    out["hour_cos_24"] = np.cos(2.0 * np.pi * minutes_of_day / 1440.0).astype("float32")
    out["day_of_week_sin_7"] = np.sin(2.0 * np.pi * day_of_week / 7.0).astype("float32")
    out["day_of_week_cos_7"] = np.cos(2.0 * np.pi * day_of_week / 7.0).astype("float32")
    out["minutes_since_ny_cash_open"] = (minutes_of_day - (9 * 60 + 30)).astype("float32")
    local_dates = pd.DatetimeIndex(pd.to_datetime(pd.Series(local_index.date)))
    out["session_id_ny"] = (local_dates.asi8 // 86_400_000_000_000).astype("int32")
    return out


def _add_risk_state_features(out: pd.DataFrame) -> pd.DataFrame:
    return_1 = out["return_1"].astype(float)
    reference_vol = return_1.rolling(96, min_periods=96).std(ddof=1).shift(1)
    shock = return_1.abs().gt(3.0 * reference_vol) | _safe_divide(
        out["true_range"], out["atr_20"]
    ).gt(2.5)
    out["shock_active"] = shock.fillna(False).astype("int8")
    out["prior_resistance_48"] = (
        out["high"].astype(float).shift(1).rolling(48, min_periods=48).max()
    ).astype("float32")
    out["resistance_distance_atr"] = _safe_divide(
        out["prior_resistance_48"] - out["close"].astype(float), out["atr_20"]
    ).astype("float32")
    return out


def _apply_candidate_rules(
    out: pd.DataFrame,
    *,
    stage: int,
    local_index: pd.DatetimeIndex,
    session_open: str = "09:30",
    session_close: str = "16:00",
    timestamp_convention: str = "bar_start",
) -> pd.DataFrame:
    close = out["close"].astype(float)
    low = out["low"].astype(float)
    atr = out["atr_20"].astype(float)
    ema50 = out["ema_50"].astype(float)
    ema100 = out["ema_100"].astype(float)
    mandatory = ema50.gt(ema100) & close.gt(ema50)

    score = mandatory.astype("int8") * 0
    score = ema50.gt(ema100).astype("int8") + close.gt(ema50).astype("int8")
    if stage >= 2:
        score += out["ema50_slope_5_atr"].gt(0.0).astype("int8")
        score += out["rolling_log_price_r2_96"].ge(0.35).astype("int8")
    if stage >= 6:
        score += out["mama"].gt(out["fama"]).astype("int8")
    out["trend_vwap_trend_score"] = score.astype("int8")

    if stage < 2:
        trend_ok = mandatory
    elif stage < 6:
        trend_ok = mandatory & score.ge(3)
    else:
        trend_ok = mandatory & score.ge(4)

    expansion_ok = pd.Series(True, index=out.index, dtype=bool)
    pullback_ok = pd.Series(True, index=out.index, dtype=bool)
    if stage >= 4:
        expansion_ok = out["prior_8_max_d_vwap_atr"].ge(0.80) & out["return_4_atr"].gt(0.0)
        distance = out["d_vwap_atr"].astype(float)
        touch = distance.between(-0.15, 0.35, inclusive="both") | distance.shift(1).between(
            -0.15, 0.35, inclusive="both"
        )
        pullback_ok = (
            touch
            & out["pullback_depth_atr"].between(0.45, 1.50, inclusive="both")
            & close.gt(ema50 - 0.25 * atr)
            & low.gt(ema50 - 0.60 * atr)
            & close.gt(ema100)
        )

    reclaim_ok = out["vwap_reclaim_cross"].astype(bool)
    momentum_ok = pd.Series(True, index=out.index, dtype=bool)
    if stage >= 5:
        histogram = out["ppo_hist_12_26_9"].astype(float)
        momentum_ok = (
            reclaim_ok
            & histogram.gt(histogram.shift(1))
            & (
                close.gt(out["high"].astype(float).shift(1))
                | out["stoch_rsi_bullish_cross"].astype(bool)
            )
        )

    session_ok = _session_window_mask(
        local_index,
        out.index,
        session_open=session_open,
        session_close=session_close,
        timestamp_convention=timestamp_convention,
    )
    if stage >= 7:
        session_ok &= _session_window_mask(
            local_index,
            out.index,
            session_open="10:00",
            session_close="12:30",
            timestamp_convention=timestamp_convention,
        )

    shock_ok = pd.Series(True, index=out.index, dtype=bool)
    resistance_ok = pd.Series(True, index=out.index, dtype=bool)
    volatility_ok = pd.Series(True, index=out.index, dtype=bool)
    if stage >= 8:
        shock_ok = ~out["shock_active"].astype(bool)
        distance_to_resistance = out["resistance_distance_atr"].astype(float)
        near_resistance = distance_to_resistance.ge(0.0) & distance_to_resistance.lt(0.50)
        resistance_ok = ~near_resistance
        volatility_ok = out["atr_percent_rank_252"].le(0.97) & out["atr_percent_rank_252"].notna()

    out["trend_vwap_expansion_ok"] = expansion_ok.fillna(False).astype("int8")
    out["trend_vwap_pullback_ok"] = pullback_ok.fillna(False).astype("int8")
    out["trend_vwap_reclaim_ok"] = reclaim_ok.fillna(False).astype("int8")
    out["trend_vwap_momentum_ok"] = momentum_ok.fillna(False).astype("int8")
    out["trend_vwap_session_ok"] = session_ok.fillna(False).astype("int8")
    out["trend_vwap_shock_ok"] = shock_ok.fillna(False).astype("int8")
    out["trend_vwap_resistance_ok"] = resistance_ok.fillna(False).astype("int8")
    out["trend_vwap_volatility_ok"] = volatility_ok.fillna(False).astype("int8")

    state = (
        trend_ok
        & expansion_ok
        & pullback_ok
        & reclaim_ok
        & momentum_ok
        & session_ok
        & shock_ok
        & resistance_ok
        & volatility_ok
    ).fillna(False)
    candidate = transition_pulse(state)
    out["trend_vwap_base_state"] = state.astype("int8")
    out["trend_vwap_base_candidate"] = candidate.astype("int8")
    out["trend_vwap_candidate_side"] = candidate.astype("int8")
    return out


def trend_vwap_pullback_candidate_feature(
    df: pd.DataFrame,
    *,
    stage: int = 8,
    timezone: str = "America/New_York",
    session_open: str = "09:30",
    session_close: str = "16:00",
    timestamp_convention: str = "bar_start",
) -> pd.DataFrame:
    """Add the cumulative causal feature/candidate ladder through ``stage``.

    YAML declaration::

        features:
          - step: trend_vwap_pullback_candidate
            params:
              stage: 8
              timezone: America/New_York
              session_open: "09:30"
              session_close: "16:00"
              timestamp_convention: bar_start

    Required input columns
    ----------------------
    open:
        Bar open price.
    high:
        Bar high price.
    low:
        Bar low price.
    close:
        Bar close price.
    volume:
        Bar volume used for the causal session VWAP.

    Parameters
    ----------
    df:
        Time-ordered OHLCV frame.  A naive index is interpreted as UTC to
        match the Dukascopy loader contract.
    stage:
        Integer from 0 through 8 corresponding to YAML0 through YAML8.
    timezone:
        IANA timezone used for the cash-session VWAP and entry window.
    session_open, session_close:
        Local cash-session bounds.  The default contract is the US regular
        session from 09:30 through 16:00 New York time.
    timestamp_convention:
        ``bar_start`` uses ``[open, close)`` labels; ``bar_close`` uses
        ``(open, close]`` labels for bars wholly inside the same session.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")
    if isinstance(stage, bool) or not isinstance(stage, Integral) or not 0 <= int(stage) <= 8:
        raise ValueError("stage must be an integer in [0, 8].")
    if not isinstance(timezone, str) or not timezone.strip():
        raise ValueError("timezone must be a non-empty IANA timezone name.")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("trend_vwap_pullback_candidate requires a DatetimeIndex.")
    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        raise ValueError("trend_vwap_pullback_candidate requires a sorted, unique index.")
    _require_columns(df, ("open", "high", "low", "close", "volume"))

    resolved_stage = int(stage)
    out, local_index = _add_core_features(
        df.copy(),
        timezone=timezone,
        session_open=session_open,
        session_close=session_close,
        timestamp_convention=timestamp_convention,
    )
    if resolved_stage >= 1:
        out = _add_return_features(out)
    if resolved_stage >= 2:
        out = _add_trend_features(out)
    if resolved_stage >= 3:
        out = _add_vwap_features(out)
    if resolved_stage >= 4:
        out = _add_path_features(out)
    if resolved_stage >= 5:
        out = _add_momentum_features(out)
    if resolved_stage >= 6:
        out = _add_ehlers_features(out)
    if resolved_stage >= 7:
        out = _add_context_features(out, local_index)
    if resolved_stage >= 8:
        out = _add_risk_state_features(out)
    # Consolidate the cumulatively-added feature blocks before appending the
    # state/candidate columns.  This keeps wide stage-6+ frames from becoming
    # highly fragmented without changing any values or temporal semantics.
    out = out.copy()
    return _apply_candidate_rules(
        out,
        stage=resolved_stage,
        local_index=local_index,
        session_open=session_open,
        session_close=session_close,
        timestamp_convention=timestamp_convention,
    )


__all__ = ["transition_pulse", "trend_vwap_pullback_candidate_feature"]
