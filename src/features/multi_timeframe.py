from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


_INTERNAL_TS_COL = "__mtf_timestamp_utc"


def _coerce_utc_index(
    values: pd.Index | pd.Series, *, timezone: str
) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(pd.to_datetime(values, errors="raise"))
    if idx.tz is None:
        idx = idx.tz_localize(str(timezone))
    else:
        idx = idx.tz_convert(str(timezone))
    return idx.tz_convert("UTC")


def _input_was_tz_naive(values: pd.Index | pd.Series) -> bool:
    return pd.DatetimeIndex(pd.to_datetime(values, errors="raise")).tz is None


def _restore_timestamp_convention(
    index: pd.DatetimeIndex, *, tz_naive: bool
) -> pd.DatetimeIndex:
    utc_index = index.tz_convert("UTC")
    if tz_naive:
        return utc_index.tz_localize(None)
    return utc_index


def _timeframe_minutes(timeframe: str) -> int:
    delta = pd.Timedelta(str(timeframe))
    minutes = int(delta.total_seconds() // 60)
    if minutes <= 0 or not np.isclose(delta.total_seconds(), minutes * 60):
        raise ValueError(
            f"timeframe '{timeframe}' must resolve to whole positive minutes."
        )
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
    time_values: pd.Index | pd.Series = (
        df[timestamp_col] if has_timestamp_col else df.index
    )
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
        raise ValueError(
            "Higher timeframes must be integer multiples of base_interval_minutes."
        )
    expected_rows = timeframe_minutes // int(base_interval_minutes)

    # Timestamp convention:
    # - bar_close keeps the legacy contract: each 30m row is labeled by the bar close.
    #   HTF bars use `closed='right'`, so the 1h bar ending at 01:00 includes 00:30 and
    #   01:00 base rows and becomes mergeable at timestamp 01:00.
    # - bar_start is for feeds like Dukascopy where the 30m timestamp is the bar open.
    #   HTF bars use `closed='left'`, so [00:00, 01:00) is labeled 01:00 and only rows
    #   at or after 01:00 can receive that fully closed 1h feature.
    closed = "left" if timestamp_convention == "bar_start" else "right"
    resampler = df.resample(
        str(timeframe), label="right", closed=closed, origin="epoch"
    )
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
    bars = bars.loc[counts >= expected_rows].dropna(
        subset=[open_col, high_col, low_col, close_col]
    )
    bars.index.name = _INTERNAL_TS_COL
    return bars


def _prefix_higher_timeframe_candles(
    bars: pd.DataFrame,
    *,
    prefix: str,
    open_col: str,
    high_col: str,
    low_col: str,
    close_col: str,
    volume_col: str,
) -> pd.DataFrame:
    candles = pd.DataFrame(
        {
            f"mtf_{prefix}_open": bars[open_col],
            f"mtf_{prefix}_high": bars[high_col],
            f"mtf_{prefix}_low": bars[low_col],
            f"mtf_{prefix}_close": bars[close_col],
            f"mtf_{prefix}_volume": bars[volume_col],
        },
        index=bars.index,
    )
    return candles.astype("float32")


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
    timezone: str,
    timestamp_col: str,
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
        features = _prefix_higher_timeframe_candles(
            bars,
            prefix=prefix,
            open_col=open_col,
            high_col=high_col,
            low_col=low_col,
            close_col=price_col,
            volume_col=volume_col,
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
    Apply the registered ``multi_timeframe`` feature transformation.

    This feature resamples the base OHLCV input to each configured higher timeframe and
    aligns the last fully closed higher-timeframe raw candle to the base frame. It does
    not compute derived returns, indicators, helpers, or normalizations; downstream
    feature steps should derive those explicitly from the raw ``mtf_{timeframe}_*``
    candle columns.

    YAML declaration::

        features:
          - step: multi_timeframe
            params:
              base_interval_minutes: 30
              timeframes: [1h, 4h]
              price_col: close
              high_col: high
              low_col: low
              open_col: open
              volume_col: volume
              timezone: UTC
              shift_to_last_closed: true
              timestamp_convention: bar_close
              timestamp_col: timestamp
              asset_col: asset

    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    open_col:
        Input dataframe column configured by ``open_col``. Default: ``open``.
    volume_col:
        Input dataframe column configured by ``volume_col``. Default: ``volume``.
    timestamp_col:
        Input dataframe column configured by ``timestamp_col``. Default: ``timestamp``.
    asset_col:
        Input dataframe column configured by ``asset_col``. Default: ``asset``.

    Parameters
    ----------
    base_interval_minutes:
        Configuration parameter accepted by this feature. Default: ``30``.
    timeframes:
        Configuration parameter accepted by this feature. Default: ``[1h, 4h]``.
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    open_col:
        Input dataframe column configured by ``open_col``. Default: ``open``.
    volume_col:
        Input dataframe column configured by ``volume_col``. Default: ``volume``.
    returns_col:
        Deprecated compatibility parameter. Ignored by this transform.
    timezone:
        Configuration parameter accepted by this feature. Default: ``UTC``.
    shift_to_last_closed:
        Configuration parameter accepted by this feature. Default: ``true``.
    timestamp_convention:
        Configuration parameter accepted by this feature. Default: ``bar_close``.
    timestamp_col:
        Input dataframe column configured by ``timestamp_col``. Default: ``timestamp``.
    asset_col:
        Input dataframe column configured by ``asset_col``. Default: ``asset``.
    volatility_window:
        Deprecated compatibility parameter. Ignored by this transform.
    trend_ema_span:
        Deprecated compatibility parameter. Ignored by this transform.
    trend_sma_window:
        Deprecated compatibility parameter. Ignored by this transform.
    atr_window:
        Deprecated compatibility parameter. Ignored by this transform.
    adx_window:
        Deprecated compatibility parameter. Ignored by this transform.
    regime_short_window:
        Deprecated compatibility parameter. Ignored by this transform.
    regime_long_window:
        Deprecated compatibility parameter. Ignored by this transform.
    """
    if not shift_to_last_closed:
        raise ValueError(
            "multi_timeframe currently supports only shift_to_last_closed=true."
        )
    timestamp_convention = str(timestamp_convention).strip().lower()
    if timestamp_convention not in {"bar_start", "bar_close"}:
        raise ValueError("timestamp_convention must be one of: bar_start, bar_close.")
    if int(base_interval_minutes) <= 0:
        raise ValueError("base_interval_minutes must be positive.")
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
                    timezone=timezone,
                    timestamp_col=timestamp_col,
                    timestamp_convention=timestamp_convention,
                )
            )
        if not frames:
            return df.copy()
        return (
            pd.concat(frames, axis=0, ignore_index=True, sort=False)
            .sort_values(
                [timestamp_col, asset_col],
                kind="mergesort",
            )
            .reset_index(drop=True)
        )

    return _add_multi_timeframe_single_asset(
        df,
        base_interval_minutes=int(base_interval_minutes),
        timeframes=timeframes,
        price_col=price_col,
        high_col=high_col,
        low_col=low_col,
        open_col=open_col,
        volume_col=volume_col,
        timezone=timezone,
        timestamp_col=timestamp_col,
        timestamp_convention=timestamp_convention,
    )


__all__ = ["add_multi_timeframe_features"]
