from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.paths import DashboardPaths
from app.services.backtest_loader import BacktestLoader
from app.services.experiment_loader import ExperimentLoader


def _paths(tmp_path: Path) -> DashboardPaths:
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "processed").mkdir(parents=True)
    (tmp_path / "logs" / "experiments").mkdir(parents=True)
    (tmp_path / "logs" / "bot").mkdir(parents=True)
    return DashboardPaths.from_project_root(tmp_path)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_list_runs_includes_logs_bot_with_prefixed_run_id(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    experiment_dir = tmp_path / "logs" / "experiments" / "offline_demo"
    bot_dir = tmp_path / "logs" / "bot" / "live_demo"
    experiment_dir.mkdir(parents=True)
    bot_dir.mkdir(parents=True)

    for run_dir, run_name, created_at in (
        (experiment_dir, "offline_demo", "2026-06-07T00:00:00+00:00"),
        (bot_dir, "live_demo", "2026-06-08T00:00:00+00:00"),
    ):
        _write_json(
            run_dir / "run_metadata.json",
            {
                "created_at_utc": created_at,
                "config_hash_sha256": "abc123",
                "config_hash_input": {
                    "logging": {"run_name": run_name},
                    "data": {"symbol": "SPX500", "interval": "30m"},
                },
            },
        )
        _write_json(run_dir / "summary.json", {"summary": {"total_return": 0.1}})
        (run_dir / "config_used.yaml").write_text("data:\n  symbol: SPX500\n", encoding="utf-8")

    loader = ExperimentLoader(paths)
    runs = {run["run_id"]: run for run in loader.list_runs()}

    assert "offline_demo" in runs
    assert "bot__live_demo" in runs
    assert runs["bot__live_demo"]["name"] == "live_demo"
    assert runs["bot__live_demo"]["asset"] == "SPX500"
    assert loader.resolve_run_dir("bot__live_demo") == bot_dir
    assert runs["bot__live_demo"]["run_type"] == "experiment"


def test_list_runs_exposes_processed_dataset_and_market_making_summary(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    experiment_dir = tmp_path / "logs" / "experiments" / "processed_demo"
    experiment_dir.mkdir(parents=True)
    processed_dir = tmp_path / "data" / "processed" / "processed" / "processed_demo_deadbeef"
    processed_dir.mkdir(parents=True)
    (processed_dir / "dataset.csv").write_text(
        "\n".join(["timestamp,asset,open,high,low,close", "2026-06-08T09:00:00Z,SPX500,1,1,1,1"]),
        encoding="utf-8",
    )
    _write_json(
        processed_dir / "metadata.json",
        {
            "dataset_id": "processed_demo_deadbeef",
            "stage": "processed",
            "assets": ["SPX500"],
            "context": {"base_dataset_id": "processed_demo"},
        },
    )
    _write_json(
        experiment_dir / "run_metadata.json",
        {
            "created_at_utc": "2026-06-08T00:00:00+00:00",
            "config_hash_input": {
                "logging": {"run_name": "processed_demo"},
                "data": {
                    "symbol": "SPX500",
                    "interval": "30m",
                    "storage": {"dataset_id": "processed_demo", "save_processed": True},
                },
            },
        },
    )
    _write_json(experiment_dir / "summary.json", {"summary": {"total_return": 0.2}})
    (experiment_dir / "config_used.yaml").write_text(
        "data:\n  symbol: SPX500\n  interval: 30m\n  storage:\n    dataset_id: processed_demo\n    save_processed: true\n",
        encoding="utf-8",
    )

    mm_dir = tmp_path / "reports" / "market_making"
    mm_dir.mkdir(parents=True)
    _write_json(mm_dir / "summary.json", {"total_pnl": 12.5})
    (mm_dir / "orderbook_events.csv").write_text(
        "\n".join(
            [
                "timestamp,symbol,event_type,best_bid,best_ask,mid_price,spread,spread_bps",
                "2026-07-01T20:27:01+00:00,BTC/USD,snapshot,1,2,1.5,1,100",
            ]
        ),
        encoding="utf-8",
    )

    loader = ExperimentLoader(paths)
    runs = {run["run_id"]: run for run in loader.list_runs()}

    assert runs["processed_demo"]["processed_dataset_id"] == "data/processed/processed/processed_demo_deadbeef/dataset.csv"
    assert runs["processed_demo"]["processed_dataset_path"].endswith("/data/processed/processed/processed_demo_deadbeef/dataset.csv")
    assert runs["market_making__latest"]["run_type"] == "market_making"
    assert runs["market_making__latest"]["asset"] == "BTC/USD"


def test_backtest_equity_loads_from_logs_bot_run_id(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    bot_dir = tmp_path / "logs" / "bot" / "live_demo"
    bot_dir.mkdir(parents=True)
    _write_json(bot_dir / "summary.json", {})
    (bot_dir / "equity_curve.csv").write_text(
        "\n".join(["timestamp,equity", "2026-06-08 09:00:00,100000.0", "2026-06-08 09:30:00,100500.0"]),
        encoding="utf-8",
    )

    loader = BacktestLoader(ExperimentLoader(paths))
    equity = loader.load_equity("bot__live_demo")

    assert equity == [
        {"time": "2026-06-08T09:00:00Z", "value": 100000.0},
        {"time": "2026-06-08T09:30:00Z", "value": 100500.0},
    ]
