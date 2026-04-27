from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from src.features.technical.adx import compute_adx
from src.features.technical.atr import compute_atr


_INTERNAL_TS_COL = "__mtf_timestamp_utc"


def _coerce_utc_index(values: pd.Index | pd.Series, *, timezone: str) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(pd.to_datetime(values, errors="raise"))
    if idx.tz is None:
        idx = idx.tz_localize(str(timezone))
    else:
        idx = idx.tz_convert(str(timezone))
    return idx.tz_convert("UTC")


def _input_was_tz_naive(values: pd.Index | pd.Series) -> bool:
    return pd.DatetimeIndex(pd.to_datetime(values, errors="raise")).tz is None


def _restore_timestamp_convention(index: pd.DatetimeIndex, *, tz_naive: bool) -> pd.DatetimeIndex:
    utc_index = index.tz_convert("UTC")
    if tz_naive:
        return utc_index.tz_localize(None)
    return utc_index


def _timeframe_minutes(timeframe: str) -> int:
    delta = pd.Timedelta(str(timeframe))
    minutes = int(delta.total_seconds() // 60)
    if minutes <= 0 or not np.isclose(delta.total_seconds(), minutes * 60):
        raise ValueError(f"timeframe '{timeframe}' must resolve to whole positive minutes.")
    return minutes


def _timeframe_prefix(timeframe: str) -> str:
    return str(timeframe).strip().lower().replace(" ", "")


def _require_columns(df: pd.DataFrame, columns: Sequence[str]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for multi_timeframe features: {missing}")


def _prepare_single_asset_frame(
    df: pd.DataFrame,
    *,
    timestamp_col: str,
    timezone: str,
) -> tuple[pd.DataFrame, bool, bool]:
    has_timestamp_col = timestamp_col in df.columns
    time_values: pd.Index | pd.Series = df[timestamp_col] if has_timestamp_col else df.index
    tz_naive = _input_was_tz_naive(time_values)
    utc_index = _coerce_utc_index(time_values, timezone=timezone)

    out = df.copy()
    out[_INTERNAL_TS_COL] = utc_index
    out = out.sort_values(_INTERNAL_TS_COL, kind="mergesort")
    out = out.drop_duplicates(subset=[_INTERNAL_TS_COL], keep="last")
    out = out.set_index(_INTERNAL_TS_COL, drop=False)
    out.index.name = _INTERNAL_TS_COL
    return out, has_timestamp_col, tz_naive


def _resample_ohlcv(
    df: pd.DataFrame,
    *,
    timeframe: str,
    base_interval_minutes: int,
    open_col: str,
    high_col: str,
    low_col: str,
    close_col: str,
    volume_col: str,
    timestamp_convention: str = "bar_close",
) -> pd.DataFrame:
    timestamp_convention = str(timestamp_convention).strip().lower()
    if timestamp_convention not in {"bar_start", "bar_close"}:
        raise ValueError("timestamp_convention must be one of: bar_start, bar_close.")
    timeframe_minutes = _timeframe_minutes(timeframe)
    if timeframe_minutes % int(base_interval_minutes) != 0:
        raise ValueError("Higher timeframes must be integer multiples of base_interval_minutes.")
    expected_rows = timeframe_minutes // int(base_interval_minutes)

    # Timestamp convention:
    # - bar_close keeps the legacy contract: each 30m row is labeled by the bar close.
    #   HTF bars use `closed='right'`, so the 1h bar ending at 01:00 includes 00:30 and
    #   01:00 base rows and becomes mergeable at timestamp 01:00.
    # - bar_start is for feeds like Dukascopy where the 30m timestamp is the bar open.
    #   HTF bars use `closed='left'`, so [00:00, 01:00) is labeled 01:00 and only rows
    #   at or after 01:00 can receive that fully closed 1h feature.
    closed = "left" if timestamp_convention == "bar_start" else "right"
    resampler = df.resample(str(timeframe), label="right", closed=closed, origin="epoch")
    bars = resampler.agg(
        {
            open_col: "first",
            high_col: "max",
            low_col: "min",
            close_col: "last",
            volume_col: "sum",
        }
    )
    counts = resampler[close_col].count()
    bars = bars.loc[counts >= expected_rows].dropna(subset=[open_col, high_col, low_col, close_col])
    bars.index.name = _INTERNAL_TS_COL
    return bars


def _compute_higher_timeframe_features(
    bars: pd.DataFrame,
    *,
    prefix: str,
    price_col: str,
    high_col: str,
    low_col: str,
    returns_col: str,
    volatility_window: int,
    trend_ema_span: int,
    trend_sma_window: int,
    atr_window: int,
    adx_window: int,
    regime_short_window: int,
    regime_long_window: int,
) -> pd.DataFrame:
    close = bars[price_col].astype(float)
    high = bars[high_col].astype(float)
    low = bars[low_col].astype(float)

    ratio = close / close.shift(1)
    logret = np.log(ratio)
    logret = logret.where(ratio > 0.0)

    volatility = logret.rolling(volatility_window, min_periods=volatility_window).std()
    ema = close.ewm(span=trend_ema_span, adjust=False, min_periods=trend_ema_span).mean()
    sma = close.rolling(trend_sma_window, min_periods=trend_sma_window).mean()
    trend_score = ema / sma.replace(0.0, np.nan) - 1.0
    atr = compute_atr(high, low, close, window=atr_window)
    adx_frame = compute_adx(high, low, close, window=adx_window)
    adx = adx_frame[f"adx_{adx_window}"]
    short_vol = logret.rolling(regime_short_window, min_periods=regime_short_window).std()
    long_vol = logret.rolling(regime_long_window, min_periods=regime_long_window).std()
    regime_vol_ratio = short_vol / long_vol.replace(0.0, np.nan)

    features = pd.DataFrame(
        {
            f"mtf_{prefix}_{returns_col}": logret,
            f"mtf_{prefix}_volatility": volatility,
            f"mtf_{prefix}_trend_score": trend_score,
            f"mtf_{prefix}_atr": atr,
            f"mtf_{prefix}_adx": adx,
            f"mtf_{prefix}_regime_vol_ratio": regime_vol_ratio,
        },
        index=bars.index,
    )
    return features.astype("float32")


def _merge_last_closed_features(
    base: pd.DataFrame,
    features: pd.DataFrame,
) -> pd.DataFrame:
    if features.empty:
        out = base.copy()
        for col in features.columns:
            out[col] = np.nan
        return out

    left = base.sort_index(kind="mergesort").reset_index(drop=True)
    right = features.sort_index(kind="mergesort").reset_index()
    merged = pd.merge_asof(
        left,
        right,
        on=_INTERNAL_TS_COL,
        direction="backward",
        allow_exact_matches=True,
    )
    return merged.set_index(_INTERNAL_TS_COL, drop=False)


def _add_multi_timeframe_single_asset(
    df: pd.DataFrame,
    *,
    base_interval_minutes: int,
    timeframes: Sequence[str],
    price_col: str,
    high_col: str,
    low_col: str,
    open_col: str,
    volume_col: str,
    returns_col: str,
    timezone: str,
    timestamp_col: str,
    volatility_window: int,
    trend_ema_span: int,
    trend_sma_window: int,
    atr_window: int,
    adx_window: int,
    regime_short_window: int,
    regime_long_window: int,
    timestamp_convention: str,
) -> pd.DataFrame:
    _require_columns(df, [open_col, high_col, low_col, price_col, volume_col])
    prepared, has_timestamp_col, tz_naive = _prepare_single_asset_frame(
        df,
        timestamp_col=timestamp_col,
        timezone=timezone,
    )

    out = prepared.copy()
    ohlcv = prepared[[open_col, high_col, low_col, price_col, volume_col]].apply(
        pd.to_numeric,
        errors="coerce",
    )

    for timeframe in timeframes:
        prefix = _timeframe_prefix(timeframe)
        bars = _resample_ohlcv(
            ohlcv,
            timeframe=str(timeframe),
            base_interval_minutes=base_interval_minutes,
            open_col=open_col,
            high_col=high_col,
            low_col=low_col,
            close_col=price_col,
            volume_col=volume_col,
            timestamp_convention=timestamp_convention,
        )
        features = _compute_higher_timeframe_features(
            bars,
            prefix=prefix,
            price_col=price_col,
            high_col=high_col,
            low_col=low_col,
            returns_col=returns_col,
            volatility_window=volatility_window,
            trend_ema_span=trend_ema_span,
            trend_sma_window=trend_sma_window,
            atr_window=atr_window,
            adx_window=adx_window,
            regime_short_window=regime_short_window,
            regime_long_window=regime_long_window,
        )
        out = _merge_last_closed_features(out, features)

    restored_index = _restore_timestamp_convention(
        pd.DatetimeIndex(out[_INTERNAL_TS_COL]),
        tz_naive=tz_naive,
    )
    out = out.drop(columns=[_INTERNAL_TS_COL])
    if has_timestamp_col:
        out[timestamp_col] = restored_index
        return out.reset_index(drop=True)
    out.index = restored_index
    out.index.name = df.index.name
    return out


def add_multi_timeframe_features(
    df: pd.DataFrame,
    *,
    base_interval_minutes: int = 30,
    timeframes: Sequence[str] = ("1h", "4h"),
    price_col: str = "close",
    high_col: str = "high",
    low_col: str = "low",
    open_col: str = "open",
    volume_col: str = "volume",
    returns_col: str = "close_logret",
    timezone: str = "UTC",
    shift_to_last_closed: bool = True,
    timestamp_convention: str = "bar_close",
    timestamp_col: str = "timestamp",
    asset_col: str = "asset",
    volatility_window: int = 12,
    trend_ema_span: int = 8,
    trend_sma_window: int = 20,
    atr_window: int = 14,
    adx_window: int = 14,
    regime_short_window: int = 12,
    regime_long_window: int = 48,
) -> pd.DataFrame:
    """
    Build 1h/4h features from 30m OHLCV and align them back point-in-time.

    `shift_to_last_closed=True` is the only supported production mode. The function labels
    resampled HTF bars at their close and asof-merges backward, so a base row cannot receive
    a higher-timeframe feature whose close time is after the row timestamp. Use
    `timestamp_convention="bar_start"` for feeds whose timestamps are bar opens.
    """
    if not shift_to_last_closed:
        raise ValueError("multi_timeframe currently supports only shift_to_last_closed=true.")
    timestamp_convention = str(timestamp_convention).strip().lower()
    if timestamp_convention not in {"bar_start", "bar_close"}:
        raise ValueError("timestamp_convention must be one of: bar_start, bar_close.")
    if int(base_interval_minutes) <= 0:
        raise ValueError("base_interval_minutes must be positive.")
    for key, value in {
        "volatility_window": volatility_window,
        "trend_ema_span": trend_ema_span,
        "trend_sma_window": trend_sma_window,
        "atr_window": atr_window,
        "adx_window": adx_window,
        "regime_short_window": regime_short_window,
        "regime_long_window": regime_long_window,
    }.items():
        if int(value) <= 0:
            raise ValueError(f"{key} must be positive.")
    if int(regime_short_window) > int(regime_long_window):
        raise ValueError("regime_short_window must be <= regime_long_window.")

    if timestamp_col in df.columns and asset_col in df.columns:
        frames: list[pd.DataFrame] = []
        for _, group in df.groupby(asset_col, sort=True, dropna=False):
            frames.append(
                _add_multi_timeframe_single_asset(
                    group,
                    base_interval_minutes=int(base_interval_minutes),
                    timeframes=timeframes,
                    price_col=price_col,
                    high_col=high_col,
                    low_col=low_col,
                    open_col=open_col,
                    volume_col=volume_col,
                    returns_col=returns_col,
                    timezone=timezone,
                    timestamp_col=timestamp_col,
                    volatility_window=int(volatility_window),
                    trend_ema_span=int(trend_ema_span),
                    trend_sma_window=int(trend_sma_window),
                    atr_window=int(atr_window),
                    adx_window=int(adx_window),
                    regime_short_window=int(regime_short_window),
                    regime_long_window=int(regime_long_window),
                    timestamp_convention=timestamp_convention,
                )
            )
        if not frames:
            return df.copy()
        return pd.concat(frames, axis=0, ignore_index=True, sort=False).sort_values(
            [timestamp_col, asset_col],
            kind="mergesort",
        ).reset_index(drop=True)

    return _add_multi_timeframe_single_asset(
        df,
        base_interval_minutes=int(base_interval_minutes),
        timeframes=timeframes,
        price_col=price_col,
        high_col=high_col,
        low_col=low_col,
        open_col=open_col,
        volume_col=volume_col,
        returns_col=returns_col,
        timezone=timezone,
        timestamp_col=timestamp_col,
        volatility_window=int(volatility_window),
        trend_ema_span=int(trend_ema_span),
        trend_sma_window=int(trend_sma_window),
        atr_window=int(atr_window),
        adx_window=int(adx_window),
        regime_short_window=int(regime_short_window),
        regime_long_window=int(regime_long_window),
        timestamp_convention=timestamp_convention,
    )


__all__ = ["add_multi_timeframe_features"]
