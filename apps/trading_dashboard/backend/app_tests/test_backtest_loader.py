from __future__ import annotations

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
    return DashboardPaths.from_project_root(tmp_path)


def test_loads_paired_trades_from_trade_events_when_trades_csv_is_absent(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    run_dir = tmp_path / "logs" / "experiments" / "demo_run"
    report_assets = run_dir / "report_assets"
    report_assets.mkdir(parents=True)
    (run_dir / "summary.json").write_text("{}", encoding="utf-8")
    (report_assets / "trade_events.csv").write_text(
        "\n".join(
            [
                "timestamp,asset,event_type,side,position_before,position_after,price",
                "2024-01-01 09:00:00,XAUUSD,entry,long,0.0,0.5,2050.0",
                "2024-01-01 10:00:00,XAUUSD,exit,long,0.5,0.0,2055.0",
                "2024-01-01 11:00:00,SPX500,entry,short,0.0,-0.25,5100.0",
                "2024-01-01 12:00:00,SPX500,exit,short,-0.25,0.0,5090.0",
            ]
        ),
        encoding="utf-8",
    )

    loader = BacktestLoader(ExperimentLoader(paths))
    trades = loader.load_trades("demo_run", asset="XAUUSD")

    assert trades == [
        {
            "entry_time": "2024-01-01T09:00:00Z",
            "exit_time": "2024-01-01T10:00:00Z",
            "side": "long",
            "entry_price": 2050.0,
            "exit_price": 2055.0,
            "pnl": None,
            "return": None,
            "size": 0.5,
        }
    ]


def test_loads_and_filters_canonical_trades_csv(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    run_dir = tmp_path / "logs" / "experiments" / "demo_run"
    report_assets = run_dir / "report_assets"
    report_assets.mkdir(parents=True)
    (run_dir / "summary.json").write_text("{}", encoding="utf-8")
    (report_assets / "trades.csv").write_text(
        "\n".join(
            [
                "asset,entry_timestamp,exit_timestamp,side,entry_price,exit_price,net_return,position_size",
                "XAUUSD,2024-01-01 09:00:00,2024-01-01 10:00:00,long,2050.0,2055.0,0.01,0.5",
                "SPX500,2024-01-01 11:00:00,2024-01-01 12:00:00,short,5100.0,5090.0,0.02,0.25",
            ]
        ),
        encoding="utf-8",
    )

    loader = BacktestLoader(ExperimentLoader(paths))
    trades = loader.load_trades("demo_run", asset="SPX500")

    assert len(trades) == 1
    assert trades[0]["side"] == "short"
    assert trades[0]["entry_price"] == 5100.0
    assert trades[0]["return"] == 0.02
