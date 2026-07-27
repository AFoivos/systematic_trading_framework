from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.prepare_ftmo_relative_value_data import prepare_dataset


def _write_m1(path: Path, timestamps: pd.DatetimeIndex, base: float) -> None:
    frame = pd.DataFrame(
        {
            "timestamp_utc": timestamps,
            "open": base,
            "high": base + 2.0,
            "low": base - 1.0,
            "close": base + 1.0,
            "tick_volume": 3.0,
        }
    )
    frame.to_csv(path, index=False)


def test_prepare_dataset_uses_hour_end_timestamps_and_common_complete_hours(tmp_path: Path) -> None:
    first_hour = pd.date_range("2026-01-01T00:00:00Z", periods=60, freq="min")
    second_hour = pd.date_range("2026-01-01T01:00:00Z", periods=60, freq="min")
    btc_times = first_hour.append(second_hour)
    eth_times = first_hour.append(second_hour[:30])
    btc_path = tmp_path / "btcusd_m1.csv"
    eth_path = tmp_path / "ethusd_m1.csv"
    _write_m1(btc_path, btc_times, 100.0)
    _write_m1(eth_path, eth_times, 10.0)

    dataset, manifest = prepare_dataset(btc_path, eth_path, min_minutes_per_hour=45)

    assert list(dataset.index) == [pd.Timestamp("2026-01-01T01:00:00Z")]
    assert dataset.iloc[0]["btc_source_minutes"] == 60
    assert dataset.iloc[0]["eth_source_minutes"] == 60
    assert manifest["synchronized_h1_rows"] == 1
    assert manifest["btc_only_complete_hours"] == 1


def test_prepare_dataset_rejects_duplicate_timestamps(tmp_path: Path) -> None:
    timestamps = pd.DatetimeIndex(
        [pd.Timestamp("2026-01-01T00:00:00Z"), pd.Timestamp("2026-01-01T00:00:00Z")]
    )
    btc_path = tmp_path / "btcusd_m1.csv"
    eth_path = tmp_path / "ethusd_m1.csv"
    _write_m1(btc_path, timestamps, 100.0)
    _write_m1(eth_path, timestamps[:1], 10.0)

    try:
        prepare_dataset(btc_path, eth_path)
    except ValueError as exc:
        assert "duplicate M1 timestamps" in str(exc)
    else:
        raise AssertionError("Expected duplicate-timestamp validation failure.")

