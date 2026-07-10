from __future__ import annotations

from collections import deque
import csv
from datetime import datetime, timezone
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
from typing import Any, Iterable

import yaml

from app.core.paths import DashboardPaths, get_paths
from app.services.market_making_runs import latest_market_making_run, market_making_root


DEFAULT_LOG_DIR = "logs/mt5_demo"
DEFAULT_MARKET_MAKING_DIR = "logs/experiments/market_making"
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

    def bot_options(self) -> dict[str, Any]:
        logs_root = (self.paths.project_root / "logs").resolve()
        config_entries = self._execution_config_entries()
        candidates: dict[Path, list[dict[str, Any]]] = {}

        for entry in config_entries:
            log_dir = self._resolve_log_dir(str(entry["log_dir"]))
            candidates.setdefault(log_dir, []).append(entry)

        for log_dir in self._execution_log_dirs(logs_root):
            candidates.setdefault(log_dir, [])

        options = [self._bot_option(log_dir, entries) for log_dir, entries in candidates.items()]
        options.sort(key=_bot_option_sort_key)
        return {"options": options}

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

    def market_making_snapshot(
        self,
        *,
        run_dir: str | None = None,
        symbol: str | None = None,
        max_points: int = 1200,
    ) -> dict[str, Any]:
        resolved = self._resolve_market_making_dir(run_dir)
        orderbook_rows = self._read_csv_records(resolved / "orderbook_events.csv")
        if not orderbook_rows:
            orderbook_rows = self._read_csv_records(resolved / "quote_events.csv")
        trades = self._read_csv_records(resolved / "trades.csv")
        inventory_rows = self._read_csv_records(resolved / "inventory_timeseries.csv")
        pnl_rows = self._read_csv_records(resolved / "pnl_timeseries.csv")
        summary = self._read_json(resolved / "summary.json")

        asset = self._market_making_symbol(symbol, orderbook_rows, trades)
        if asset:
            orderbook_rows = [row for row in orderbook_rows if str(row.get("symbol") or "") == asset]
            trades = [row for row in trades if str(row.get("symbol") or "") == asset]

        inventory_by_time = {
            str(row.get("timestamp") or ""): row
            for row in inventory_rows
            if str(row.get("timestamp") or "")
        }
        pnl_by_time = {
            str(row.get("timestamp") or ""): row
            for row in pnl_rows
            if str(row.get("timestamp") or "")
        }

        records: list[dict[str, Any]] = []
        for row in orderbook_rows:
            timestamp = str(row.get("timestamp") or "").strip()
            mid_price = _optional_float(row.get("mid_price", row.get("book_mid_price", row.get("fair_price"))))
            if not timestamp or mid_price is None:
                continue
            inventory = inventory_by_time.get(timestamp, {})
            pnl = pnl_by_time.get(timestamp, {})
            records.append(
                {
                    "time": timestamp,
                    "open": mid_price,
                    "high": mid_price,
                    "low": mid_price,
                    "close": mid_price,
                    "mid_price": mid_price,
                    "spread": _optional_float(row.get("spread", row.get("book_spread"))),
                    "spread_bps": _optional_float(row.get("spread_bps", row.get("book_spread_bps"))),
                    "imbalance_1": _optional_float(row.get("imbalance_1", row.get("book_imbalance_1"))),
                    "imbalance_5": _optional_float(row.get("imbalance_5", row.get("book_imbalance_5"))),
                    "bid_depth_5": _optional_float(row.get("bid_depth_5")),
                    "ask_depth_5": _optional_float(row.get("ask_depth_5")),
                    "inventory": _optional_float(inventory.get("inventory")),
                    "mark_price": _optional_float(inventory.get("mark_price")),
                    "realized_pnl": _optional_float(pnl.get("realized_pnl")),
                    "unrealized_pnl": _optional_float(pnl.get("unrealized_pnl")),
                    "total_pnl": _optional_float(pnl.get("total_pnl")),
                    "fees": _optional_float(pnl.get("fees")),
                }
            )

        trade_markers = [
            {
                "entry_time": str(trade.get("timestamp") or "") or None,
                "exit_time": None,
                "side": "short" if str(trade.get("side") or "").strip().lower() == "sell" else "long",
                "entry_price": _optional_float(trade.get("price")),
                "exit_price": None,
                "pnl": None,
                "return": None,
                "size": _optional_float(trade.get("quantity")),
                "exit_reason": None,
            }
            for trade in trades
            if str(trade.get("timestamp") or "").strip()
        ]

        sampled_records = self._sample_market_making_records(
            records,
            trade_times={str(trade.get("timestamp") or "").strip() for trade in trades},
            max_points=max_points,
        )
        columns = list(sampled_records[0].keys()) if sampled_records else []
        market_columns = ["open", "high", "low", "close"]
        feature_columns = [
            column
            for column in columns
            if column not in {"time", *market_columns}
        ]
        numeric_columns = [column for column in columns if column != "time"]
        return {
            "run_dir": str(resolved),
            "asset": asset,
            "row_count": len(sampled_records),
            "columns": columns,
            "numeric_columns": numeric_columns,
            "feature_columns": feature_columns,
            "market_columns": market_columns,
            "records": sampled_records,
            "trades": trade_markers,
            "summary": summary,
        }

    def _resolve_log_dir(self, raw_log_dir: str | None) -> Path:
        candidate = self.paths.resolve_project_path(raw_log_dir or DEFAULT_LOG_DIR)
        logs_root = (self.paths.project_root / "logs").resolve()
        try:
            candidate.relative_to(logs_root)
        except ValueError as exc:
            raise ValueError("Execution log_dir must resolve under the project logs directory.") from exc
        return candidate

    def _execution_config_entries(self) -> list[dict[str, Any]]:
        config_root = self.paths.project_root / "config" / "execution"
        if not config_root.exists():
            return []

        entries: list[dict[str, Any]] = []
        for path in sorted(config_root.glob("*.y*ml")):
            payload = self._read_yaml_mapping(path)
            if not payload:
                continue
            logging_cfg = dict(payload.get("logging", {}) or {})
            log_dir = logging_cfg.get("output_dir")
            if not log_dir:
                continue
            try:
                resolved_log_dir = self._resolve_log_dir(str(log_dir))
            except ValueError:
                continue
            if not _is_bot_config(payload, resolved_log_dir):
                continue
            entries.append(
                {
                    "config_path": _relative_path(path, self.paths.project_root),
                    "config_name": path.stem,
                    "log_dir": _relative_path(resolved_log_dir, self.paths.project_root),
                    "mode": str(dict(payload.get("execution", {}) or {}).get("mode") or ""),
                    "symbols": _enabled_symbols(payload.get("symbols")),
                }
            )
        return entries

    def _execution_log_dirs(self, logs_root: Path) -> set[Path]:
        if not logs_root.exists():
            return set()

        candidates: set[Path] = set()
        marker_names = {
            "account_equity.jsonl",
            "decision_trace.jsonl",
            "signals.jsonl",
            "orders.jsonl",
            "fills.jsonl",
            "rejected_orders.jsonl",
            "errors.jsonl",
            "mt5_demo_bot.lock",
            "bot.log",
            "command.txt",
        }
        for child in logs_root.iterdir():
            if child.is_dir() and any((child / marker).exists() for marker in marker_names):
                candidates.add(child.resolve())
        return candidates

    def _bot_option(self, log_dir: Path, config_entries: list[dict[str, Any]]) -> dict[str, Any]:
        account_tail = self._read_jsonl_tail(log_dir / "account_equity.jsonl", limit=3)
        decision_tail = self._read_jsonl_tail(log_dir / "decision_trace.jsonl", limit=50)
        lock = self._read_json(log_dir / "mt5_demo_bot.lock")
        latest_account = account_tail[-1] if account_tail else None
        health = self._health(
            latest_account=latest_account,
            lock=lock,
            poll_seconds=_latest_poll_seconds(decision_tail),
        )
        primary_config = self._primary_config_entry(config_entries, lock)
        relative_log_dir = _relative_path(log_dir, self.paths.project_root)
        mode = str(health.get("execution_mode") or primary_config.get("mode") or "") or None
        symbols = sorted(
            {
                symbol
                for entry in config_entries
                for symbol in entry.get("symbols", [])
            }
        )
        if not symbols:
            symbols = sorted(
                {
                    str(record.get("asset") or "").strip()
                    for record in decision_tail
                    if str(record.get("asset") or "").strip()
                }
            )
        modified_at = self._latest_modified_at(log_dir)
        raw_config_path = str(health.get("config_path") or primary_config.get("config_path") or "")
        config_path = _project_relative_display_path(raw_config_path, self.paths.project_root) if raw_config_path else None
        return {
            "id": relative_log_dir,
            "label": _bot_label(
                config_name=str(primary_config.get("config_name") or Path(relative_log_dir).name),
                log_dir=relative_log_dir,
                mode=mode,
                state=str(health.get("state") or "no_data"),
            ),
            "log_dir": relative_log_dir,
            "resolved_log_dir": str(log_dir),
            "config_path": config_path,
            "mode": mode,
            "state": str(health.get("state") or "no_data"),
            "pid": health.get("pid"),
            "process_running": health.get("process_running"),
            "last_heartbeat_at": health.get("last_heartbeat_at"),
            "modified_at": modified_at,
            "symbols": symbols,
            "has_logs": any(file_info["exists"] for file_info in self._files(log_dir)),
            "is_default": relative_log_dir.replace("\\", "/") == DEFAULT_LOG_DIR,
        }

    def _primary_config_entry(self, entries: list[dict[str, Any]], lock: dict[str, Any]) -> dict[str, Any]:
        locked_path = str(lock.get("config_path") or "")
        if locked_path:
            for entry in entries:
                config_path = str(entry.get("config_path") or "")
                if config_path and (
                    locked_path.endswith(config_path.replace("/", "\\"))
                    or locked_path.endswith(config_path.replace("\\", "/"))
                    or locked_path.endswith(config_path)
                ):
                    return entry
        return entries[0] if entries else {}

    def _latest_modified_at(self, log_dir: Path) -> str | None:
        timestamps: list[float] = []
        if log_dir.exists():
            timestamps.append(log_dir.stat().st_mtime)
        for stream in (*STREAMS, "mt5_demo_bot.lock", "bot.log", "command.txt"):
            path = log_dir / (stream if "." in stream else f"{stream}.jsonl")
            if path.exists():
                timestamps.append(path.stat().st_mtime)
        return _iso_from_timestamp(max(timestamps)) if timestamps else None

    def _resolve_market_making_dir(self, raw_run_dir: str | None) -> Path:
        if raw_run_dir is None:
            latest = latest_market_making_run(self.paths)
            return latest if latest is not None else market_making_root(self.paths).resolve()
        candidate = self.paths.resolve_project_path(raw_run_dir or DEFAULT_MARKET_MAKING_DIR)
        reports_root = market_making_root(self.paths).resolve()
        try:
            candidate.relative_to(reports_root)
        except ValueError as exc:
            raise ValueError("Market making run_dir must resolve under logs/experiments/market_making.") from exc
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
    def _read_yaml_mapping(path: Path) -> dict[str, Any]:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _read_csv_records(path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []
        try:
            with path.open("r", encoding="utf-8", newline="") as handle:
                return [dict(row) for row in csv.DictReader(handle)]
        except OSError:
            return []

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

    @staticmethod
    def _market_making_symbol(
        requested_symbol: str | None,
        orderbook_rows: list[dict[str, str]],
        trades: list[dict[str, str]],
    ) -> str:
        normalized = str(requested_symbol or "").strip()
        if normalized:
            return normalized
        for row in orderbook_rows:
            symbol = str(row.get("symbol") or "").strip()
            if symbol:
                return symbol
        for trade in trades:
            symbol = str(trade.get("symbol") or "").strip()
            if symbol:
                return symbol
        return ""

    @staticmethod
    def _sample_market_making_records(
        records: list[dict[str, Any]],
        *,
        trade_times: set[str],
        max_points: int,
    ) -> list[dict[str, Any]]:
        if max_points <= 0 or len(records) <= max_points:
            return records

        required_indices = sorted(
            index for index, record in enumerate(records) if str(record.get("time") or "") in trade_times
        )
        required_indices = [index for index in required_indices if 0 <= index < len(records)]

        if required_indices:
            first_trade_index = required_indices[0]
            last_trade_index = required_indices[-1]
            trade_span = last_trade_index - first_trade_index + 1
            context_budget = max(max_points - trade_span, 0)
            left_context = context_budget // 2
            right_context = context_budget - left_context
            start = max(first_trade_index - left_context, 0)
            end = min(last_trade_index + right_context + 1, len(records))
            window = records[start:end]
            if len(window) >= max_points:
                return window[:max_points]
            if start == 0:
                return records[: min(max_points, len(records))]
            if end == len(records):
                return records[max(0, len(records) - max_points) :]
            return window

        required_index_set = set(required_indices)
        remaining_budget = max(max_points - len(required_indices), 0)

        sampled_indices: set[int] = set(required_index_set)
        if remaining_budget > 0:
            evenly_spaced = _evenly_spaced_indices(len(records), remaining_budget)
            for index in evenly_spaced:
                if len(sampled_indices) >= max_points:
                    break
                sampled_indices.add(index)

        if len(sampled_indices) < max_points:
            for index in range(len(records)):
                sampled_indices.add(index)
                if len(sampled_indices) >= max_points:
                    break

        ordered_indices = sorted(sampled_indices)[:max_points]
        return [records[index] for index in ordered_indices]


def _latest_poll_seconds(records: list[dict[str, Any]]) -> int | None:
    for record in reversed(records):
        execution = dict(record.get("execution", {}) or {})
        value = _optional_int(execution.get("poll_seconds"))
        if value is not None:
            return value
    return None


def _enabled_symbols(raw_symbols: Any) -> list[str]:
    if not isinstance(raw_symbols, dict):
        return []
    symbols: list[str] = []
    for symbol, payload in raw_symbols.items():
        if isinstance(payload, dict) and payload.get("enabled") is False:
            continue
        normalized = str(symbol).strip()
        if normalized:
            symbols.append(normalized)
    return sorted(symbols)


def _is_bot_config(payload: dict[str, Any], resolved_log_dir: Path) -> bool:
    mode = str(dict(payload.get("execution", {}) or {}).get("mode") or "").lower()
    log_dir = str(resolved_log_dir).replace("\\", "/").lower()
    if "mt5" in mode or "mt5" in log_dir:
        return True
    marker_names = {"account_equity.jsonl", "decision_trace.jsonl", "signals.jsonl", "mt5_demo_bot.lock"}
    return any((resolved_log_dir / marker).exists() for marker in marker_names)


def _project_relative_display_path(raw_path: str, root: Path) -> str:
    normalized = raw_path.replace("\\", "/").strip()
    path = Path(raw_path)
    if path.is_absolute():
        try:
            return _relative_path(path, root)
        except (OSError, ValueError):
            pass
    for marker in ("/workspace/", "systematic_trading_framework/"):
        if marker in normalized:
            return normalized.split(marker, 1)[1]
    if normalized.startswith("./"):
        return normalized[2:]
    return normalized


def _relative_path(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _bot_label(*, config_name: str, log_dir: str, mode: str | None, state: str) -> str:
    suffix = " / ".join(part for part in (mode, state) if part)
    return f"{config_name} ({suffix})" if suffix else f"{config_name} ({log_dir})"


def _bot_option_sort_key(option: dict[str, Any]) -> tuple[int, int, str, str]:
    process_rank = 0 if option.get("process_running") is True else 1
    state_order = {"running": 0, "stale": 1, "no_data": 2}
    state_rank = state_order.get(str(option.get("state") or ""), 3)
    latest = str(option.get("last_heartbeat_at") or option.get("modified_at") or "")
    return (process_rank, state_rank, _reverse_iso_key(latest), str(option.get("label") or ""))


def _reverse_iso_key(value: str) -> str:
    return "".join(chr(255 - ord(char)) for char in value)


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


def _optional_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out and out not in {float("inf"), float("-inf")} else None


def _evenly_spaced_indices(length: int, count: int) -> list[int]:
    if length <= 0 or count <= 0:
        return []
    if count >= length:
        return list(range(length))
    if count == 1:
        return [length - 1]
    positions = []
    last_index = length - 1
    for step in range(count):
        ratio = step / (count - 1)
        positions.append(round(ratio * last_index))
    return sorted(set(positions))


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
