from __future__ import annotations

import pandas as pd
import pytest

from src.src_data.ctrader_export import load_ctrader_bar_export, load_ctrader_tick_export


def test_ctrader_bar_export_is_canonical_utc_and_drops_active_tail(tmp_path) -> None:
    path = tmp_path / "bars_M30.csv"
    pd.DataFrame(
        {
            "symbol": ["ETHUSD", "ETHUSD", "ETHUSD"],
            "time": ["2024-01-01 02:00:00", "2024-01-01 02:30:00", "2024-01-01 03:00:00"],
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "tick_volume": [10, 20, 3],
        }
    ).to_csv(path, index=False)

    export = load_ctrader_bar_export(
        path,
        timeframe="M30",
        source_timezone="Europe/Athens",
        drop_incomplete_tail=True,
    )

    assert export.frame.index.tz is None
    assert export.frame.index[0] == pd.Timestamp("2024-01-01 00:00:00")
    assert export.frame.columns.tolist() == ["open", "high", "low", "close", "volume", "tick_volume"]
    assert export.frame["volume"].tolist() == [10.0, 20.0]
    assert export.metadata["source_timezone"] == "Europe/Athens"
    assert export.metadata["output_timezone"] == "UTC"
    assert export.metadata["timestamp_convention"] == "bar_open"
    assert export.metadata["dropped_tail_rows"] == 1


def test_ctrader_bar_export_fails_on_duplicate_timestamp(tmp_path) -> None:
    path = tmp_path / "bars.csv"
    pd.DataFrame(
        {
            "symbol": ["ETHUSD", "ETHUSD"],
            "time": ["2024-01-01 00:00:00", "2024-01-01 00:00:00"],
            "open": [100.0, 100.0],
            "high": [101.0, 101.0],
            "low": [99.0, 99.0],
            "close": [100.0, 100.0],
            "tick_volume": [1, 1],
        }
    ).to_csv(path, index=False)

    with pytest.raises(ValueError, match="duplicate timestamps"):
        load_ctrader_bar_export(path, timeframe="M30", drop_incomplete_tail=False)


def test_ctrader_tick_export_validates_and_recomputes_quote_geometry(tmp_path) -> None:
    path = tmp_path / "ticks.csv"
    pd.DataFrame(
        {
            "symbol": ["ETHUSD", "ETHUSD"],
            "time": ["2024-01-01 00:00:00.000", "2024-01-01 00:00:01.000"],
            "bid": [100.0, 100.1],
            "ask": [100.2, 100.3],
            "mid": [100.1, 100.2],
            "spread": [0.2, 0.2],
        }
    ).to_csv(path, index=False)

    export = load_ctrader_tick_export(path)

    assert export.frame.columns.tolist() == ["bid", "ask", "mid", "spread", "spread_bps"]
    assert export.frame.iloc[0]["mid"] == pytest.approx(100.1)
    assert export.frame.iloc[0]["spread_bps"] == pytest.approx(0.2 / 100.1 * 10_000.0)
    assert export.metadata["duplicate_policy"] == "raise"
    assert export.metadata["interpolation_policy"] == "none"


def test_ctrader_tick_export_rejects_crossed_quotes(tmp_path) -> None:
    path = tmp_path / "crossed.csv"
    pd.DataFrame(
        {
            "symbol": ["ETHUSD"],
            "time": ["2024-01-01 00:00:00"],
            "bid": [100.2],
            "ask": [100.1],
        }
    ).to_csv(path, index=False)

    with pytest.raises(ValueError, match="crossed quotes"):
        load_ctrader_tick_export(path)
