from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.multi_timeframe import add_multi_timeframe_features
from src.features.multi_timeframe import _resample_ohlcv


def _base_30m_frame(periods: int = 12, *, start: str = "2024-01-01 00:30:00") -> pd.DataFrame:
    idx = pd.date_range(start, periods=periods, freq="30min", tz="UTC")
    close = pd.Series(np.arange(100.0, 100.0 + periods), index=idx)
    return pd.DataFrame(
        {
            "open": close - 0.25,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.arange(10.0, 10.0 + periods),
        },
        index=idx,
    )


def test_multi_timeframe_resamples_1h_ohlcv_correctly() -> None:
    df = _base_30m_frame(periods=6)

    bars = _resample_ohlcv(
        df,
        timeframe="1h",
        base_interval_minutes=30,
        open_col="open",
        high_col="high",
        low_col="low",
        close_col="close",
        volume_col="volume",
    )

    first = bars.loc[pd.Timestamp("2024-01-01 01:00:00", tz="UTC")]
    assert first["open"] == pytest.approx(df.iloc[0]["open"])
    assert first["high"] == pytest.approx(max(df.iloc[0]["high"], df.iloc[1]["high"]))
    assert first["low"] == pytest.approx(min(df.iloc[0]["low"], df.iloc[1]["low"]))
    assert first["close"] == pytest.approx(df.iloc[1]["close"])
    assert first["volume"] == pytest.approx(df.iloc[0]["volume"] + df.iloc[1]["volume"])


def test_multi_timeframe_resamples_4h_ohlcv_correctly() -> None:
    df = _base_30m_frame(periods=10)

    bars = _resample_ohlcv(
        df,
        timeframe="4h",
        base_interval_minutes=30,
        open_col="open",
        high_col="high",
        low_col="low",
        close_col="close",
        volume_col="volume",
    )

    first = bars.loc[pd.Timestamp("2024-01-01 04:00:00", tz="UTC")]
    expected = df.iloc[:8]
    assert first["open"] == pytest.approx(expected.iloc[0]["open"])
    assert first["high"] == pytest.approx(expected["high"].max())
    assert first["low"] == pytest.approx(expected["low"].min())
    assert first["close"] == pytest.approx(expected.iloc[-1]["close"])
    assert first["volume"] == pytest.approx(expected["volume"].sum())


def test_multi_timeframe_alignment_uses_last_closed_1h_without_lookahead() -> None:
    df = _base_30m_frame(periods=8)

    out = add_multi_timeframe_features(
        df,
        timeframes=["1h"],
        volatility_window=2,
        trend_ema_span=1,
        trend_sma_window=1,
        atr_window=1,
        adx_window=1,
        regime_short_window=1,
        regime_long_window=2,
    )

    row_0130 = out.loc[pd.Timestamp("2024-01-01 01:30:00", tz="UTC")]
    row_0200 = out.loc[pd.Timestamp("2024-01-01 02:00:00", tz="UTC")]
    expected_0200_ret = np.log(df.loc[pd.Timestamp("2024-01-01 02:00:00", tz="UTC"), "close"] / df.loc[pd.Timestamp("2024-01-01 01:00:00", tz="UTC"), "close"])

    assert pd.isna(row_0130["mtf_1h_close_logret"])
    assert row_0200["mtf_1h_close_logret"] == pytest.approx(expected_0200_ret)


def test_multi_timeframe_alignment_uses_last_closed_4h_without_lookahead() -> None:
    df = _base_30m_frame(periods=12)

    out = add_multi_timeframe_features(
        df,
        timeframes=["4h"],
        volatility_window=2,
        trend_ema_span=1,
        trend_sma_window=1,
        atr_window=1,
        adx_window=1,
        regime_short_window=1,
        regime_long_window=2,
    )

    assert pd.isna(out.loc[pd.Timestamp("2024-01-01 03:30:00", tz="UTC"), "mtf_4h_close_logret"])
    assert pd.isna(out.loc[pd.Timestamp("2024-01-01 04:00:00", tz="UTC"), "mtf_4h_close_logret"])
    longer = _base_30m_frame(periods=18)
    expected = np.log(
        longer.loc[pd.Timestamp("2024-01-01 08:00:00", tz="UTC"), "close"]
        / longer.loc[pd.Timestamp("2024-01-01 04:00:00", tz="UTC"), "close"]
    )
    longer_out = add_multi_timeframe_features(
        longer,
        timeframes=["4h"],
        volatility_window=2,
        trend_ema_span=1,
        trend_sma_window=1,
        atr_window=1,
        adx_window=1,
        regime_short_window=1,
        regime_long_window=2,
    )
    assert longer_out.loc[pd.Timestamp("2024-01-01 08:00:00", tz="UTC"), "mtf_4h_close_logret"] == pytest.approx(expected)


def test_multi_timeframe_handles_missing_30m_rows_without_partial_htf_bar() -> None:
    df = _base_30m_frame(periods=8).drop(pd.Timestamp("2024-01-01 01:30:00", tz="UTC"))

    bars = _resample_ohlcv(
        df,
        timeframe="1h",
        base_interval_minutes=30,
        open_col="open",
        high_col="high",
        low_col="low",
        close_col="close",
        volume_col="volume",
    )

    assert pd.Timestamp("2024-01-01 02:00:00", tz="UTC") not in bars.index


def test_multi_timeframe_processes_assets_independently() -> None:
    left = _base_30m_frame(periods=8)
    right = _base_30m_frame(periods=8)
    right["close"] = [200.0, 201.0, 203.0, 206.0, 210.0, 215.0, 221.0, 228.0]
    right["open"] = right["close"] - 0.25
    right["high"] = right["close"] + 1.0
    right["low"] = right["close"] - 1.0
    long = pd.concat(
        [
            left.assign(timestamp=left.index, asset="AAA").reset_index(drop=True),
            right.assign(timestamp=right.index, asset="BBB").reset_index(drop=True),
        ],
        ignore_index=True,
    )

    out = add_multi_timeframe_features(
        long,
        timeframes=["1h"],
        volatility_window=2,
        trend_ema_span=1,
        trend_sma_window=1,
        atr_window=1,
        adx_window=1,
        regime_short_window=1,
        regime_long_window=2,
    )

    ts = pd.Timestamp("2024-01-01 02:00:00", tz="UTC")
    aaa = out.loc[(out["asset"] == "AAA") & (out["timestamp"] == ts), "mtf_1h_close_logret"].iloc[0]
    bbb = out.loc[(out["asset"] == "BBB") & (out["timestamp"] == ts), "mtf_1h_close_logret"].iloc[0]
    assert aaa != pytest.approx(bbb)
