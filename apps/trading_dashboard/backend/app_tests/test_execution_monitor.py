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


def _append_jsonl(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
