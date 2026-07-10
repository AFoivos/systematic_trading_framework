from __future__ import annotations

from datetime import datetime, timezone
import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.paths import DashboardPaths
from app.services.execution_monitor import ExecutionMonitorService


def test_execution_status_reads_latest_decision_and_heartbeat(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs" / "mt5_demo"
    log_dir.mkdir(parents=True)
    now = datetime.now(timezone.utc).isoformat()
    _append_jsonl(
        log_dir / "account_equity.jsonl",
        {"logged_at": now, "equity": 100000.0, "balance": 100000.0, "margin_free": 100000.0},
    )
    _append_jsonl(
        log_dir / "decision_trace.jsonl",
        {
            "logged_at": now,
            "asset": "SPX500",
            "mt5_symbol": "US500.cash",
            "bar_time": "2026-06-15T13:30:00+00:00",
            "execution": {"poll_seconds": 30},
            "market_data": {"latest_ohlcv": {"close": 7523.88, "spread": 55.0}},
            "signal": {"signal_side": 0},
            "order": {"action": "none", "status": "not_sent", "reason": "flat_signal"},
        },
    )

    service = ExecutionMonitorService(paths=DashboardPaths.from_project_root(tmp_path))
    status = service.status()

    assert status["health"]["state"] == "running"
    assert status["account"]["equity"] == 100000.0
    assert status["latest_by_asset"] == [
        {
            "asset": "SPX500",
            "mt5_symbol": "US500.cash",
            "bar_time": "2026-06-15T13:30:00+00:00",
            "logged_at": now,
            "close": 7523.88,
            "spread": 55.0,
            "signal_side": 0,
            "order_action": "none",
            "order_status": "not_sent",
            "order_reason": "flat_signal",
            "has_decision_trace": True,
        }
    ]


def test_execution_log_dir_must_stay_under_project_logs(tmp_path: Path) -> None:
    service = ExecutionMonitorService(paths=DashboardPaths.from_project_root(tmp_path))

    with pytest.raises(ValueError, match="project logs"):
        service.status(log_dir=str(tmp_path / "elsewhere"))


def test_execution_bot_options_merge_configs_and_existing_logs(tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "execution"
    config_dir.mkdir(parents=True)
    (config_dir / "eth_demo_trade.yaml").write_text(
        "\n".join(
            [
                "execution:",
                "  mode: demo_mt5",
                "symbols:",
                "  ETHUSD:",
                "    enabled: true",
                "logging:",
                "  output_dir: logs/eth_demo_trade",
            ]
        ),
        encoding="utf-8",
    )
    now = datetime.now(timezone.utc).isoformat()
    log_dir = tmp_path / "logs" / "eth_demo_trade"
    log_dir.mkdir(parents=True)
    _append_jsonl(log_dir / "account_equity.jsonl", {"logged_at": now, "equity": 100000.0})
    (log_dir / "mt5_demo_bot.lock").write_text(
        json.dumps(
            {
                "pid": 999999,
                "execution_mode": "demo_mt5",
                "config_path": str(config_dir / "eth_demo_trade.yaml"),
            }
        ),
        encoding="utf-8",
    )
    stale_log_dir = tmp_path / "logs" / "old_bot"
    stale_log_dir.mkdir(parents=True)
    _append_jsonl(stale_log_dir / "signals.jsonl", {"asset": "SPX500", "logged_at": "2026-01-01T00:00:00+00:00"})

    service = ExecutionMonitorService(paths=DashboardPaths.from_project_root(tmp_path))
    options = service.bot_options()["options"]

    assert [option["log_dir"] for option in options] == ["logs/eth_demo_trade", "logs/old_bot"]
    assert options[0]["config_path"] == "config/execution/eth_demo_trade.yaml"
    assert options[0]["mode"] == "demo_mt5"
    assert options[0]["symbols"] == ["ETHUSD"]
    assert options[0]["has_logs"] is True
    assert options[1]["label"].startswith("old_bot")


def test_execution_feature_snapshot_reads_asset_file(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs" / "mt5_demo" / "feature_snapshots"
    log_dir.mkdir(parents=True)
    (log_dir / "US100.json").write_text(
        json.dumps(
            {
                "asset": "US100",
                "mt5_symbol": "US100.cash",
                "bar_time": "2026-06-15T13:30:00+00:00",
                "timeframe": "M30",
                "row_count": 2,
                "columns": ["close", "ema_50"],
                "numeric_columns": ["close", "ema_50"],
                "feature_columns": ["ema_50"],
                "market_columns": ["close"],
                "records": [
                    {"time": "2026-06-15T13:00:00+00:00", "close": 30244.73, "ema_50": 30100.1},
                    {"time": "2026-06-15T13:30:00+00:00", "close": 30238.63, "ema_50": 30105.2},
                ],
            }
        ),
        encoding="utf-8",
    )

    service = ExecutionMonitorService(paths=DashboardPaths.from_project_root(tmp_path))
    snapshot = service.feature_snapshot("US100")

    assert snapshot["asset"] == "US100"
    assert snapshot["feature_columns"] == ["ema_50"]
    assert snapshot["records"][-1]["ema_50"] == 30105.2


def test_execution_feature_snapshot_returns_empty_payload_when_missing(tmp_path: Path) -> None:
    service = ExecutionMonitorService(paths=DashboardPaths.from_project_root(tmp_path))

    snapshot = service.feature_snapshot("XAUUSD")

    assert snapshot["asset"] == "XAUUSD"
    assert snapshot["row_count"] == 0
    assert snapshot["records"] == []


def test_market_making_snapshot_builds_chart_rows_and_trade_markers(tmp_path: Path) -> None:
    run_dir = tmp_path / "logs" / "experiments" / "market_making" / "runs" / "latest_demo"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(json.dumps({"number_of_fills": 1, "total_pnl": 12.5}), encoding="utf-8")
    (run_dir / "orderbook_events.csv").write_text(
        "\n".join(
            [
                "timestamp,symbol,event_type,best_bid,best_ask,mid_price,spread,spread_bps,imbalance_1,imbalance_5,bid_depth_5,ask_depth_5",
                "2026-07-01T20:27:01+00:00,BTC/USD,snapshot,59916.9,59917.0,59916.95,0.1,0.0166,0.94,0.07,0.16,2.05",
                "2026-07-01T20:27:02+00:00,BTC/USD,update,59917.0,59917.2,59917.1,0.2,0.0333,0.75,0.03,0.25,1.12",
            ]
        ),
        encoding="utf-8",
    )
    (run_dir / "inventory_timeseries.csv").write_text(
        "\n".join(
            [
                "timestamp,inventory,mark_price",
                "2026-07-01T20:27:01+00:00,0.0,59916.95",
                "2026-07-01T20:27:02+00:00,-0.001,59917.1",
            ]
        ),
        encoding="utf-8",
    )
    (run_dir / "pnl_timeseries.csv").write_text(
        "\n".join(
            [
                "timestamp,realized_pnl,unrealized_pnl,total_pnl,fees",
                "2026-07-01T20:27:01+00:00,0.0,0.0,0.0,0.0",
                "2026-07-01T20:27:02+00:00,10.0,2.5,12.5,0.1",
            ]
        ),
        encoding="utf-8",
    )
    (run_dir / "trades.csv").write_text(
        "\n".join(
            [
                "order_id,symbol,side,price,quantity,fee,timestamp",
                "paper-1,BTC/USD,sell,59917.1,0.001,0.1,2026-07-01T20:27:02+00:00",
            ]
        ),
        encoding="utf-8",
    )

    service = ExecutionMonitorService(paths=DashboardPaths.from_project_root(tmp_path))
    snapshot = service.market_making_snapshot()

    assert snapshot["asset"] == "BTC/USD"
    assert snapshot["row_count"] == 2
    assert snapshot["records"][-1]["total_pnl"] == 12.5
    assert snapshot["records"][-1]["inventory"] == -0.001
    assert snapshot["trades"] == [
        {
            "entry_time": "2026-07-01T20:27:02+00:00",
            "exit_time": None,
            "side": "short",
            "entry_price": 59917.1,
            "exit_price": None,
            "pnl": None,
            "return": None,
            "size": 0.001,
            "exit_reason": None,
        }
    ]
    assert snapshot["summary"]["number_of_fills"] == 1


def test_market_making_snapshot_reads_quote_events_from_logs_experiments(tmp_path: Path) -> None:
    run_dir = tmp_path / "logs" / "experiments" / "market_making" / "runs" / "quote_demo"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(json.dumps({"number_of_quotes": 1}), encoding="utf-8")
    (run_dir / "quote_events.csv").write_text(
        "\n".join(
            [
                "timestamp,symbol,fair_price,book_mid_price,book_spread_bps,book_imbalance_1,book_imbalance_5",
                "2026-07-03T22:16:10+00:00,BTC/USD,62561.67,62561.65,0.015984,0.70642,0.70642",
            ]
        ),
        encoding="utf-8",
    )

    service = ExecutionMonitorService(paths=DashboardPaths.from_project_root(tmp_path))
    snapshot = service.market_making_snapshot()

    assert snapshot["run_dir"] == str(run_dir.resolve())
    assert snapshot["asset"] == "BTC/USD"
    assert snapshot["row_count"] == 1
    assert snapshot["records"][0]["close"] == 62561.65


def _append_jsonl(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
