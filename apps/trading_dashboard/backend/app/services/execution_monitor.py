from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
from typing import Any, Iterable

from app.core.paths import DashboardPaths, get_paths


DEFAULT_LOG_DIR = "logs/mt5_demo"
STREAMS = (
    "account_equity",
    "signals",
    "decision_trace",
    "orders",
    "fills",
    "rejected_orders",
    "errors",
)


class ExecutionMonitorService:
    def __init__(self, paths: DashboardPaths | None = None) -> None:
        self.paths = paths or get_paths()

    def status(self, *, log_dir: str | None = None) -> dict[str, Any]:
        resolved = self._resolve_log_dir(log_dir)
        account_tail = self._read_jsonl_tail(resolved / "account_equity.jsonl", limit=10)
        decision_tail = self._read_jsonl_tail(resolved / "decision_trace.jsonl", limit=500)
        signal_tail = self._read_jsonl_tail(resolved / "signals.jsonl", limit=500)
        lock = self._read_json(resolved / "mt5_demo_bot.lock")
        command = self._read_text(resolved / "command.txt")
        latest_account = account_tail[-1] if account_tail else None
        latest_records = self._latest_by_asset(decision_tail, fallback_signals=signal_tail)
        health = self._health(
            latest_account=latest_account,
            lock=lock,
            poll_seconds=_latest_poll_seconds(decision_tail),
        )
        return {
            "log_dir": str(resolved),
            "health": health,
            "lock": lock,
            "command": command,
            "account": latest_account,
            "latest_by_asset": latest_records,
            "recent_events": self.events(log_dir=str(resolved), limit=100)["records"],
            "files": self._files(resolved),
        }

    def decisions(
        self,
        *,
        log_dir: str | None = None,
        asset: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        resolved = self._resolve_log_dir(log_dir)
        records = self._read_jsonl_tail(
            resolved / "decision_trace.jsonl",
            limit=max(1, min(int(limit), 1000)),
            asset=asset,
        )
        return {"log_dir": str(resolved), "records": list(reversed(records))}

    def events(self, *, log_dir: str | None = None, limit: int = 100) -> dict[str, Any]:
        resolved = self._resolve_log_dir(log_dir)
        records: list[dict[str, Any]] = []
        for stream in ("orders", "fills", "rejected_orders", "errors"):
            records.extend(
                {
                    "stream": stream,
                    **record,
                }
                for record in self._read_jsonl_tail(resolved / f"{stream}.jsonl", limit=limit)
            )
        records.sort(key=lambda item: str(item.get("logged_at") or item.get("bar_time") or ""), reverse=True)
        return {"log_dir": str(resolved), "records": records[: max(1, min(int(limit), 1000))]}

    def feature_snapshot(self, asset: str, *, log_dir: str | None = None) -> dict[str, Any]:
        resolved = self._resolve_log_dir(log_dir)
        normalized_asset = str(asset).strip().upper()
        path = resolved / "feature_snapshots" / f"{_safe_filename(normalized_asset)}.json"
        payload = self._read_json(path)
        if not payload:
            return {
                "log_dir": str(resolved),
                "asset": normalized_asset,
                "mt5_symbol": None,
                "bar_time": None,
                "timeframe": None,
                "row_count": 0,
                "columns": [],
                "numeric_columns": [],
                "feature_columns": [],
                "market_columns": [],
                "records": [],
            }
        payload["log_dir"] = str(resolved)
        return payload

    def account(self, *, log_dir: str | None = None, limit: int = 100) -> dict[str, Any]:
        resolved = self._resolve_log_dir(log_dir)
        return {
            "log_dir": str(resolved),
            "records": list(
                reversed(
                    self._read_jsonl_tail(
                        resolved / "account_equity.jsonl",
                        limit=max(1, min(int(limit), 1000)),
                    )
                )
            ),
        }

    def _resolve_log_dir(self, raw_log_dir: str | None) -> Path:
        candidate = self.paths.resolve_project_path(raw_log_dir or DEFAULT_LOG_DIR)
        logs_root = (self.paths.project_root / "logs").resolve()
        try:
            candidate.relative_to(logs_root)
        except ValueError as exc:
            raise ValueError("Execution log_dir must resolve under the project logs directory.") from exc
        return candidate

    def _files(self, log_dir: Path) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        for stream in STREAMS:
            path = log_dir / f"{stream}.jsonl"
            files.append(
                {
                    "stream": stream,
                    "path": str(path),
                    "exists": path.exists(),
                    "bytes": path.stat().st_size if path.exists() else 0,
                    "modified_at": _iso_from_timestamp(path.stat().st_mtime) if path.exists() else None,
                }
            )
        return files

    def _latest_by_asset(
        self,
        decisions: list[dict[str, Any]],
        *,
        fallback_signals: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        source = decisions if decisions else fallback_signals
        for record in source:
            asset = str(record.get("asset") or "")
            if not asset:
                continue
            latest[asset] = self._asset_summary(record, has_decision_trace=bool(decisions))
        return sorted(latest.values(), key=lambda item: str(item.get("asset") or ""))

    def _asset_summary(self, record: dict[str, Any], *, has_decision_trace: bool) -> dict[str, Any]:
        order = dict(record.get("order", {}) or {})
        market_data = dict(record.get("market_data", {}) or {})
        latest_ohlcv = dict(market_data.get("latest_ohlcv", {}) or {})
        latest_values = dict(record.get("latest_values", {}) or {})
        signal = dict(record.get("signal", {}) or {})
        signal_side = signal.get("signal_side", record.get("signal_side"))
        return {
            "asset": record.get("asset"),
            "mt5_symbol": record.get("mt5_symbol"),
            "bar_time": record.get("bar_time"),
            "logged_at": record.get("logged_at"),
            "close": latest_ohlcv.get("close", latest_values.get("close", record.get("close"))),
            "spread": latest_ohlcv.get("spread", latest_values.get("spread", record.get("spread"))),
            "signal_side": signal_side,
            "order_action": order.get("action"),
            "order_status": order.get("status"),
            "order_reason": order.get("reason"),
            "has_decision_trace": has_decision_trace,
        }

    def _health(
        self,
        *,
        latest_account: dict[str, Any] | None,
        lock: dict[str, Any],
        poll_seconds: int | None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        last_heartbeat = str(latest_account.get("logged_at")) if latest_account else None
        heartbeat_dt = _parse_time(last_heartbeat)
        stale_seconds = (now - heartbeat_dt).total_seconds() if heartbeat_dt is not None else None
        stale_after_seconds = max(90.0, float(poll_seconds or 30) * 4)
        state = "no_data"
        if stale_seconds is not None:
            state = "running" if stale_seconds <= stale_after_seconds else "stale"
        pid = _optional_int(lock.get("pid"))
        process_running = _pid_is_running(pid) if pid is not None else None
        return {
            "state": state,
            "last_heartbeat_at": last_heartbeat,
            "stale_seconds": stale_seconds,
            "stale_after_seconds": stale_after_seconds,
            "lock_present": bool(lock),
            "pid": pid,
            "process_running": process_running,
            "config_path": lock.get("config_path"),
            "execution_mode": lock.get("execution_mode"),
        }

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8").strip() or "{}")
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _read_text(path: Path) -> str | None:
        if not path.exists():
            return None
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return text or None

    @staticmethod
    def _read_jsonl_tail(path: Path, *, limit: int, asset: str | None = None) -> list[dict[str, Any]]:
        if not path.exists() or limit <= 0:
            return []
        target_asset = asset.upper() if asset else None
        records: deque[dict[str, Any]] = deque(maxlen=limit)
        try:
            lines: Iterable[str] = path.open("r", encoding="utf-8")
        except OSError:
            return []
        with lines as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    record = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                if target_asset and str(record.get("asset", "")).upper() != target_asset:
                    continue
                records.append(record)
        return list(records)


def _latest_poll_seconds(records: list[dict[str, Any]]) -> int | None:
    for record in reversed(records):
        execution = dict(record.get("execution", {}) or {})
        value = _optional_int(execution.get("poll_seconds"))
        if value is not None:
            return value
    return None


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _optional_int(value: Any) -> int | None:
    try:
        out = int(value)
    except (TypeError, ValueError):
        return None
    return out if out > 0 else None


def _pid_is_running(pid: int) -> bool:
    if os.name == "nt":
        return _windows_pid_is_running(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _windows_pid_is_running(pid: int) -> bool:
    process_query_limited_information = 0x1000
    synchronize = 0x00100000
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(process_query_limited_information | synchronize, False, int(pid))
    if not handle:
        return False
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return True
        return int(exit_code.value) == still_active
    finally:
        kernel32.CloseHandle(handle)


def _iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in str(value))


__all__ = ["ExecutionMonitorService"]
