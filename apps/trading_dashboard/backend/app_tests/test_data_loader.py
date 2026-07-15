from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.paths import DashboardPaths
from app.services.data_loader import DataLoader
from app.services.schema_mapper import DataSchemaError


def _paths(tmp_path: Path) -> DashboardPaths:
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "processed").mkdir(parents=True)
    (tmp_path / "logs" / "experiments").mkdir(parents=True)
    return DashboardPaths.from_project_root(tmp_path)


def test_discovers_raw_dataset_and_loads_ohlcv_with_epoch_timestamps(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    source_dir = tmp_path / "data" / "raw" / "dukascopy_30m_clean"
    source_dir.mkdir(parents=True)
    (source_dir / "xauusd_30m.csv").write_text(
        "\n".join(
            [
                "timestamp,Open,High,Low,Close,Volume,rsi_14",
                "1672531200000,1.0,1.2,0.9,1.1,100,55.0",
                "1672533000000,1.1,1.3,1.0,1.2,120,57.5",
            ]
        ),
        encoding="utf-8",
    )

    loader = DataLoader(paths)
    datasets = loader.discover_datasets()

    assert len(datasets) == 1
    assert datasets[0].assets == ("XAUUSD",)
    assert datasets[0].timeframe == "M30"

    candles = loader.load_ohlcv(asset="XAUUSD", timeframe="M30", source="dukascopy_30m_clean")
    assert candles[0] == {
        "time": "2023-01-01T00:00:00Z",
        "open": 1.0,
        "high": 1.2,
        "low": 0.9,
        "close": 1.1,
        "volume": 100,
    }
    assert loader.load_ohlcv(dataset_id=datasets[0].id)[0]["close"] == 1.1


def test_load_series_applies_tail_limit_to_match_candle_window(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    source_dir = tmp_path / "data" / "raw" / "dukascopy_30m_clean"
    source_dir.mkdir(parents=True)
    (source_dir / "xauusd_30m.csv").write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume,rsi_14",
                "2024-01-01 00:00:00,1.0,1.2,0.9,1.1,100,50.0",
                "2024-01-01 00:30:00,1.1,1.3,1.0,1.2,120,55.0",
                "2024-01-01 01:00:00,1.2,1.4,1.1,1.3,130,60.0",
            ]
        ),
        encoding="utf-8",
    )

    loader = DataLoader(paths)
    dataset_id = "data/raw/dukascopy_30m_clean/xauusd_30m.csv"
    candles = loader.load_ohlcv(dataset_id=dataset_id)[-2:]
    series = loader.load_series(dataset_id=dataset_id, columns=["rsi_14"], limit=2)

    assert [point["time"] for point in series["rsi_14"]] == [candle["time"] for candle in candles]
    assert [point["value"] for point in series["rsi_14"]] == [55.0, 60.0]


def test_load_ohlcv_applies_tail_limit_before_response_conversion(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    source_dir = tmp_path / "data" / "raw" / "dukascopy_30m_clean"
    source_dir.mkdir(parents=True)
    (source_dir / "xauusd_30m.csv").write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2024-01-01 00:00:00,1.0,1.2,0.9,1.1,100",
                "2024-01-01 00:30:00,1.1,1.3,1.0,1.2,120",
                "2024-01-01 01:00:00,1.2,1.4,1.1,1.3,130",
            ]
        ),
        encoding="utf-8",
    )

    loader = DataLoader(paths)
    candles = loader.load_ohlcv(dataset_id="data/raw/dukascopy_30m_clean/xauusd_30m.csv", limit=2)

    assert [candle["time"] for candle in candles] == ["2024-01-01T00:30:00Z", "2024-01-01T01:00:00Z"]
    assert [candle["close"] for candle in candles] == [1.2, 1.3]


def test_catalogs_are_inferred_from_processed_snapshot_columns(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    snapshot_dir = tmp_path / "data" / "processed" / "processed" / "demo_snapshot"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "metadata.json").write_text(
        '{"assets": ["XAUUSD"], "context": {"interval": "30m"}}',
        encoding="utf-8",
    )
    (snapshot_dir / "dataset.csv").write_text(
        "\n".join(
            [
                "timestamp,asset,open,high,low,close,volume,rsi_14,atr_14,regime_state,manual_signal,r_target_trade_r,pred_prob",
                "2024-01-01 00:00:00,XAUUSD,1,2,0.5,1.5,10,60,0.2,1,1,0.7,0.55",
            ]
        ),
        encoding="utf-8",
    )

    loader = DataLoader(paths)
    dataset_id = "data/processed/processed/demo_snapshot/dataset.csv"
    features = loader.catalog(source_type="feature", asset="XAUUSD", dataset_id=dataset_id)
    signals = loader.catalog(source_type="signal", asset="XAUUSD", dataset_id=dataset_id)
    targets = loader.catalog(source_type="target", asset="XAUUSD", dataset_id=dataset_id)
    predictions = loader.catalog(source_type="prediction", asset="XAUUSD", dataset_id=dataset_id)

    assert [item["name"] for item in features["oscillators"]] == ["rsi_14"]
    assert [item["name"] for item in features["volatility"]] == ["atr_14"]
    assert [item["name"] for item in features["regime"]] == ["regime_state"]
    assert [item["name"] for item in signals] == ["manual_signal"]
    assert [item["name"] for item in targets] == ["r_target_trade_r"]
    assert [item["name"] for item in predictions] == ["pred_prob"]


def test_feature_catalog_classifies_vwap_as_indicator(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    snapshot_dir = tmp_path / "data" / "processed" / "processed" / "vwap_snapshot"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "metadata.json").write_text(
        '{"assets": ["XAUUSD"], "context": {"interval": "15m"}}',
        encoding="utf-8",
    )
    (snapshot_dir / "dataset.csv").write_text(
        "\n".join(
            [
                "timestamp,asset,open,high,low,close,volume,vwap_20,close_over_vwap_20",
                "2024-01-01 00:00:00,XAUUSD,1,2,0.5,1.5,10,1.45,0.034",
            ]
        ),
        encoding="utf-8",
    )

    loader = DataLoader(paths)
    dataset_id = "data/processed/processed/vwap_snapshot/dataset.csv"
    features = loader.catalog(source_type="feature", asset="XAUUSD", dataset_id=dataset_id)

    assert {item["name"] for item in features["indicators"]} == {"vwap_20", "close_over_vwap_20"}


def test_discovers_flat_processed_dataset_from_filename(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    (tmp_path / "data" / "processed" / "eurusd_m15.csv").write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2025-01-01 22:00:00,1.03503,1.03519,1.03483,1.03485,91.44",
            ]
        ),
        encoding="utf-8",
    )

    loader = DataLoader(paths)
    dataset = next(item for item in loader.discover_datasets() if item.id == "data/processed/eurusd_m15.csv")

    assert dataset.stage == "processed"
    assert dataset.source == "processed"
    assert dataset.assets == ("EURUSD",)
    assert dataset.timeframe == "M15"
    candles = loader.load_ohlcv(asset="EURUSD", timeframe="M15", source="processed")
    assert candles[0]["close"] == 1.03485


def test_timestamped_processed_snapshot_uses_sibling_metadata(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    snapshot_dir = tmp_path / "data" / "processed" / "processed" / "spx500_snapshot"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "metadata.json").write_text(
        '{"assets": ["SPX500"], "context": {"interval": "30m"}}',
        encoding="utf-8",
    )
    snapshot_path = snapshot_dir / "06_spx500_30m_snapshot_20260601_205706.csv"
    snapshot_path.write_text(
        "\n".join(
            [
                "timestamp,asset,open,high,low,close,volume",
                "2025-01-01 22:00:00,SPX500,5900,5910,5890,5905,100",
            ]
        ),
        encoding="utf-8",
    )

    loader = DataLoader(paths)
    dataset = next(item for item in loader.discover_datasets() if item.id.endswith(snapshot_path.name))

    assert dataset.assets == ("SPX500",)
    assert dataset.timeframe == "M30"
    assert dataset.metadata_path == snapshot_dir / "metadata.json"
    assert loader.load_ohlcv(dataset_id=dataset.id)[0]["close"] == 5905


def test_filename_asset_inference_ignores_numeric_snapshot_prefix(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    snapshot_path = tmp_path / "data" / "processed" / "07_btcusd_1h_snapshot.csv"
    snapshot_path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2025-01-01 22:00:00,95000,96000,94000,95500,100",
            ]
        ),
        encoding="utf-8",
    )

    loader = DataLoader(paths)
    dataset = next(item for item in loader.discover_datasets() if item.id.endswith(snapshot_path.name))

    assert dataset.assets == ("BTCUSD",)
    assert dataset.timeframe == "H1"


def test_discovers_supported_files_anywhere_under_data_tree(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    data_dir = tmp_path / "data" / "vendor" / "category" / "nested"
    data_dir.mkdir(parents=True)
    (data_dir / "gbpusd_h1.csv").write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2025-01-01 00:00:00,1.2500,1.2600,1.2400,1.2550,100",
            ]
        ),
        encoding="utf-8",
    )

    loader = DataLoader(paths)
    dataset = next(item for item in loader.discover_datasets() if item.id == "data/vendor/category/nested/gbpusd_h1.csv")

    assert dataset.stage == "vendor"
    assert dataset.source == "category"
    assert dataset.assets == ("GBPUSD",)
    assert dataset.timeframe == "H1"
    assert loader.load_ohlcv(dataset_id=dataset.id)[0]["close"] == 1.255


def test_discovery_skips_empty_supported_files(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    source_dir = tmp_path / "data" / "raw" / "dukascopy_quarterly"
    source_dir.mkdir(parents=True)
    (source_dir / "spx500_30m_bid.csv").write_text("", encoding="utf-8")
    (source_dir / "xauusd_30m.csv").write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2025-01-01 00:00:00,1,2,0.5,1.5,10",
            ]
        ),
        encoding="utf-8",
    )

    loader = DataLoader(paths)
    datasets = loader.discover_datasets()

    assert [dataset.id for dataset in datasets] == ["data/raw/dukascopy_quarterly/xauusd_30m.csv"]


def test_ohlcv_loader_raises_clear_error_for_missing_volume(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    source_dir = tmp_path / "data" / "raw" / "example"
    source_dir.mkdir(parents=True)
    (source_dir / "xauusd_m5.csv").write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close",
                "2024-01-01 00:00:00,1.0,1.2,0.9,1.1",
            ]
        ),
        encoding="utf-8",
    )

    loader = DataLoader(paths)

    with pytest.raises(DataSchemaError, match="missing OHLCV columns"):
        loader.load_ohlcv(asset="XAUUSD", timeframe="M5", source="example")
