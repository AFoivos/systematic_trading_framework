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

    assert [item["name"] for item in features["oscillators"]] == ["rsi_14"]
    assert [item["name"] for item in features["volatility"]] == ["atr_14"]
    assert [item["name"] for item in features["regime"]] == ["regime_state"]
    assert [item["name"] for item in signals] == ["manual_signal"]
    assert [item["name"] for item in targets] == ["r_target_trade_r"]


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

