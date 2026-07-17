from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import statistics
from typing import Any, Mapping

import yaml


UTC = timezone.utc
MARKOUT_HORIZONS_MS = (100, 500, 1_000, 5_000, 10_000, 30_000, 60_000)


TABLE_COLUMNS: dict[str, list[str]] = {
    "orders": [
        "event_time", "order_id", "order_link_id", "symbol", "side", "price", "quantity",
        "leaves_quantity", "status", "action", "reject_reason", "session_id",
    ],
    "executions": [
        "exec_id", "order_id", "order_link_id", "symbol", "side", "price", "quantity",
        "exec_time", "is_maker", "exec_fee", "fee_currency", "closed_size", "sequence",
        "receive_time", "execution_latency_ms", "quote_event_id", "strategy_name", "session_id",
        "inventory_before", "inventory_after", "realized_pnl_delta",
    ],
    "fills": [
        "exec_id", "order_id", "order_link_id", "symbol", "side", "price", "quantity",
        "exec_time", "is_maker", "exec_fee", "fee_currency", "session_id",
    ],
    "public_trades": [
        "trade_id", "symbol", "price", "quantity", "aggressor_side", "trade_time",
        "receive_time", "market_data_latency_ms",
    ],
    "quote_events": [
        "quote_event_id", "event_time", "symbol", "fair_price", "microprice", "mid_price",
        "bid_price", "ask_price", "bid_size", "ask_size", "spread_bps",
        "requested_quote_placement_mode", "applied_quote_placement_mode", "best_bid",
        "best_ask", "tick_size", "quoted_bid", "quoted_ask", "quoted_spread_ticks",
        "quoted_spread_bps", "fallback_to_join", "inventory",
        "recent_volatility_bps", "strategy_allowed", "strategy_reason", "risk_allowed",
        "risk_reason", "session_id",
    ],
    "order_intents": [
        "intent_time", "intent_id", "quote_event_id", "action", "side", "price", "quantity",
        "order_id", "order_link_id", "reason", "mode", "session_id",
    ],
    "orderbook_health": [
        "event_time", "healthy", "reason", "update_id", "cross_sequence",
        "matching_engine_timestamp_ms", "receive_timestamp_ms", "market_data_latency_ms",
        "best_bid", "best_ask", "spread_bps",
    ],
    "pnl_timeseries": [
        "event_time", "realized_pnl", "unrealized_pnl", "net_pnl", "fees", "inventory",
    ],
    "inventory_timeseries": ["event_time", "inventory", "source"],
    "markouts": [
        "exec_id", "side", "fill_price", "fill_time", "horizon_ms", "future_mid",
        "markout_bps", "markout_quote_currency",
    ],
    "fees": ["exec_id", "event_time", "fee", "currency", "is_maker"],
    "risk_events": [
        "event_time", "reason", "kill_switch", "cancel_all", "inventory", "realized_pnl",
        "unrealized_pnl", "open_orders",
    ],
    "api_errors": ["timestamp_ms", "path", "error_type", "ret_code", "message"],
}


@dataclass(frozen=True)
class ReportingWindow:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None or self.end <= self.start:
            raise ValueError("reporting windows require aware increasing timestamps.")


class WindowClock:
    def __init__(self, interval_seconds: int = 7_200, *, aligned: bool = True) -> None:
        if interval_seconds <= 0:
            raise ValueError("reporting interval must be > 0.")
        self.interval_seconds = int(interval_seconds)
        self.aligned = bool(aligned)
        self._rolling_anchor: datetime | None = None

    def window_at(self, now: datetime) -> ReportingWindow:
        current = now.astimezone(UTC)
        if self.aligned:
            epoch = int(current.timestamp())
            start_epoch = epoch - (epoch % self.interval_seconds)
            start = datetime.fromtimestamp(start_epoch, tz=UTC)
        else:
            if self._rolling_anchor is None:
                self._rolling_anchor = current
            elapsed = max(0, int((current - self._rolling_anchor).total_seconds()))
            start = self._rolling_anchor + timedelta(
                seconds=(elapsed // self.interval_seconds) * self.interval_seconds
            )
        return ReportingWindow(start=start, end=start + timedelta(seconds=self.interval_seconds))


def redact_secrets(value: Any, *, key_name: str = "") -> Any:
    sensitive = any(token in key_name.lower() for token in ("secret", "api_key", "password", "token"))
    if sensitive:
        return "***REDACTED***"
    if isinstance(value, Mapping):
        return {str(key): redact_secrets(item, key_name=str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_secrets(item, key_name=key_name) for item in value]
    if isinstance(value, tuple):
        return [redact_secrets(item, key_name=key_name) for item in value]
    return value


class SessionReporter:
    """Immutable UTC-window artifacts and market-making metrics."""

    def __init__(
        self,
        *,
        root: str | Path,
        strategy_name: str,
        symbol: str,
        session_id: str,
        config: Mapping[str, Any],
        interval_seconds: int = 7_200,
        aligned_windows: bool = True,
        started_at: datetime | None = None,
    ) -> None:
        self.root = Path(root)
        self.strategy_name = strategy_name
        self.symbol = symbol
        self.session_id = session_id
        self.config = dict(config)
        self.clock = WindowClock(interval_seconds, aligned=aligned_windows)
        self.window = self.clock.window_at(started_at or datetime.now(UTC))
        self.rows: dict[str, list[dict[str, Any]]] = {name: [] for name in TABLE_COLUMNS}
        self.midpoints: list[tuple[int, float]] = []
        self.open_orders_at_start: list[Mapping[str, Any]] = []
        self.position_at_start: list[Mapping[str, Any]] = []
        self.inventory_carried_in = 0.0
        self.realized_pnl_baseline = 0.0
        self.fees_baseline = 0.0
        self.api_latencies_ms: list[float] = []
        self._written_directories: list[Path] = []

    @property
    def written_directories(self) -> tuple[Path, ...]:
        return tuple(self._written_directories)

    @property
    def current_window_directory(self) -> Path:
        return self._window_directory()

    def prepare_window_directory(self) -> Path:
        directory = self._window_directory()
        if directory in self._written_directories:
            raise FileExistsError(f"immutable report directory already finalized: {directory}")
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def boundary_due(self, now: datetime | None = None) -> bool:
        return (now or datetime.now(UTC)).astimezone(UTC) >= self.window.end

    def record(self, table: str, row: Mapping[str, Any]) -> None:
        if table not in self.rows:
            raise KeyError(f"unsupported session report table: {table}")
        self.rows[table].append({key: _jsonable(value) for key, value in row.items()})

    def record_midpoint(self, *, timestamp_ms: int, mid_price: float) -> None:
        if math.isfinite(mid_price) and mid_price > 0:
            self.midpoints.append((int(timestamp_ms), float(mid_price)))

    def record_api_latency(self, latency_ms: float) -> None:
        if math.isfinite(float(latency_ms)) and latency_ms >= 0:
            self.api_latencies_ms.append(float(latency_ms))

    def set_start_state(
        self,
        *,
        open_orders: list[Mapping[str, Any]],
        positions: list[Mapping[str, Any]],
        inventory: float,
    ) -> None:
        self.open_orders_at_start = [dict(row) for row in open_orders]
        self.position_at_start = [dict(row) for row in positions]
        self.inventory_carried_in = float(inventory)

    def rotate(
        self,
        *,
        now: datetime,
        reconciliation: Mapping[str, Any],
        open_orders_at_end: list[Mapping[str, Any]],
        position_at_end: list[Mapping[str, Any]],
        inventory_carried_out: float,
        partial: bool = False,
    ) -> Path:
        output = self.finalize(
            reconciliation=reconciliation,
            open_orders_at_end=open_orders_at_end,
            position_at_end=position_at_end,
            inventory_carried_out=inventory_carried_out,
            partial=partial,
        )
        next_realized_baseline = _last_numeric(self.rows["pnl_timeseries"], "realized_pnl")
        next_fees_baseline = _last_numeric(self.rows["pnl_timeseries"], "fees")
        next_window = self.clock.window_at(now)
        if next_window.start <= self.window.start:
            next_window = ReportingWindow(
                start=self.window.end,
                end=self.window.end + timedelta(seconds=self.clock.interval_seconds),
            )
        self.window = next_window
        self.rows = {name: [] for name in TABLE_COLUMNS}
        self.midpoints = []
        self.realized_pnl_baseline = next_realized_baseline
        self.fees_baseline = next_fees_baseline
        self.api_latencies_ms = []
        self.open_orders_at_start = [dict(row) for row in open_orders_at_end]
        self.position_at_start = [dict(row) for row in position_at_end]
        self.inventory_carried_in = float(inventory_carried_out)
        return output

    def finalize(
        self,
        *,
        reconciliation: Mapping[str, Any],
        open_orders_at_end: list[Mapping[str, Any]],
        position_at_end: list[Mapping[str, Any]],
        inventory_carried_out: float,
        partial: bool = False,
    ) -> Path:
        self._compute_markouts()
        directory = self._window_directory()
        if directory in self._written_directories:
            raise FileExistsError(f"immutable report directory already finalized: {directory}")
        if directory.exists():
            unexpected = [
                path
                for path in directory.iterdir()
                if not path.name.startswith("orderbook_events_")
                or not path.name.endswith(".jsonl.gz")
            ]
            if unexpected:
                raise FileExistsError(
                    f"report directory already contains non-raw artifacts: {directory}"
                )
        else:
            directory.mkdir(parents=True, exist_ok=False)
        for table, columns in TABLE_COLUMNS.items():
            self._write_csv(directory / f"{table}.csv", columns, self.rows[table])

        summary = self._build_summary(
            inventory_carried_out=inventory_carried_out,
            partial=partial,
        )
        self._write_json(directory / "summary.json", summary)
        self._write_json(directory / "reconciliation.json", dict(reconciliation))
        self._write_json(directory / "open_orders_at_start.json", self.open_orders_at_start)
        self._write_json(directory / "open_orders_at_end.json", open_orders_at_end)
        self._write_json(directory / "position_at_start.json", self.position_at_start)
        self._write_json(directory / "position_at_end.json", position_at_end)
        self._write_json(
            directory / "run_metadata.json",
            {
                "venue": "bybit",
                "execution_environment": "demo",
                "symbol": self.symbol,
                "strategy_name": self.strategy_name,
                "session_id": self.session_id,
                "window_start": self.window.start.isoformat(),
                "window_end": self.window.end.isoformat(),
                "partial": partial,
                "quote_placement_mode": _runtime_applied(self.config).get(
                    "quote_placement_mode"
                ),
                "runtime_applied": _runtime_applied(self.config),
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )
        (directory / "config_used_redacted.yaml").write_text(
            yaml.safe_dump(redact_secrets(self.config), sort_keys=False), encoding="utf-8"
        )
        (directory / "report.md").write_text(self._markdown_report(summary), encoding="utf-8")
        self._written_directories.append(directory)
        return directory

    def _window_directory(self) -> Path:
        date = self.window.start.strftime("%Y%m%d")
        label = (
            f"{self.window.start:%H%M}_{self.window.end:%H%M}_"
            f"{self.strategy_name}_{self.symbol}_{self.session_id}"
        )
        return self.root / date / label

    def _compute_markouts(self) -> None:
        if not self.midpoints:
            return
        mids = sorted(self.midpoints)
        existing = {(row.get("exec_id"), row.get("horizon_ms")) for row in self.rows["markouts"]}
        for fill in self.rows["executions"]:
            exec_id = str(fill.get("exec_id", ""))
            side = str(fill.get("side", "")).lower()
            price = float(fill.get("price", 0) or 0)
            fill_time = _to_epoch_ms(fill.get("exec_time"))
            if not exec_id or price <= 0 or fill_time is None:
                continue
            for horizon in MARKOUT_HORIZONS_MS:
                if (exec_id, horizon) in existing:
                    continue
                future = next((mid for timestamp, mid in mids if timestamp >= fill_time + horizon), None)
                if future is None:
                    continue
                direction = 1.0 if side == "buy" else -1.0
                quote_currency = direction * (future - price) * float(fill.get("quantity", 0) or 0)
                bps = direction * (future - price) / price * 10_000.0
                self.rows["markouts"].append(
                    {
                        "exec_id": exec_id,
                        "side": side,
                        "fill_price": price,
                        "fill_time": fill.get("exec_time"),
                        "horizon_ms": horizon,
                        "future_mid": future,
                        "markout_bps": bps,
                        "markout_quote_currency": quote_currency,
                    }
                )

    def _build_summary(self, *, inventory_carried_out: float, partial: bool) -> dict[str, Any]:
        orders = self.rows["orders"]
        executions = self.rows["executions"]
        quotes = self.rows["quote_events"]
        risks = self.rows["risk_events"]
        intents = self.rows["order_intents"]
        health = self.rows["orderbook_health"]
        markouts = self.rows["markouts"]
        quote_by_id = {
            str(row.get("quote_event_id")): row
            for row in quotes
            if row.get("quote_event_id")
        }
        fees = sum(float(row.get("exec_fee", 0) or 0) for row in executions)
        buy_volume = sum(float(row.get("quantity", 0) or 0) for row in executions if str(row.get("side", "")).lower() == "buy")
        sell_volume = sum(float(row.get("quantity", 0) or 0) for row in executions if str(row.get("side", "")).lower() == "sell")
        turnover = sum(float(row.get("price", 0) or 0) * float(row.get("quantity", 0) or 0) for row in executions)
        inventory_values = [float(row.get("inventory", 0) or 0) for row in self.rows["inventory_timeseries"]]
        realized_cumulative = _last_numeric(self.rows["pnl_timeseries"], "realized_pnl")
        realized = realized_cumulative - self.realized_pnl_baseline
        unrealized = _last_numeric(self.rows["pnl_timeseries"], "unrealized_pnl")
        execution_latencies = [float(row["execution_latency_ms"]) for row in executions if _finite(row.get("execution_latency_ms"))]
        market_latencies = [float(row["market_data_latency_ms"]) for row in health if _finite(row.get("market_data_latency_ms"))]
        spreads = [float(row["spread_bps"]) for row in health if _finite(row.get("spread_bps"))]
        quoted_spreads = [float(row["spread_bps"]) for row in quotes if _finite(row.get("spread_bps"))]
        order_lifetimes = _order_lifetimes_ms(orders)
        time_to_fill = _time_to_fill_ms(orders, executions)
        placed = sum(str(row.get("action", "")).lower() == "place" for row in intents)
        amended = sum(str(row.get("action", "")).lower() == "amend" for row in intents)
        cancelled = sum(str(row.get("action", "")).lower() == "cancel" for row in intents)
        maker_fills = sum(bool(row.get("is_maker")) for row in executions)
        taker_fills = len(executions) - maker_fills
        risk_reasons: dict[str, int] = {}
        for row in risks:
            reason = str(row.get("reason", "unknown"))
            risk_reasons[reason] = risk_reasons.get(reason, 0) + 1
        markout_by_horizon: dict[str, Any] = {}
        for horizon in MARKOUT_HORIZONS_MS:
            values = [float(row["markout_bps"]) for row in markouts if int(row.get("horizon_ms", -1)) == horizon]
            markout_by_horizon[str(horizon)] = {
                "mean_bps": statistics.fmean(values) if values else None,
                "median_bps": statistics.median(values) if values else None,
                "adverse_selection_rate": sum(value < 0 for value in values) / len(values) if values else None,
            }
        maximum_inventory = _runtime_maximum_inventory(self.config)
        runtime_applied = _runtime_applied(self.config)
        maximum_absolute_inventory = max(
            map(abs, inventory_values), default=abs(self.inventory_carried_in)
        )
        microprice_offsets = [
            (float(row["microprice"]) - float(row["mid_price"]))
            / float(row["mid_price"])
            * 10_000.0
            for row in quotes
            if _finite(row.get("microprice"))
            and _finite(row.get("mid_price"))
            and float(row["mid_price"]) > 0
        ]
        stale_orders = sum(
            "maximum quote age" in str(row.get("reason", "")).lower()
            or "stale" in str(row.get("reason", "")).lower()
            for row in intents
        )
        gross_spread_capture = _gross_spread_capture(executions, quote_by_id)
        one_second_markouts = [
            float(row["markout_bps"])
            for row in markouts
            if int(row.get("horizon_ms", -1)) == 1_000
        ]
        requested_mode_counts = _value_counts(
            quotes, "requested_quote_placement_mode"
        )
        applied_mode_counts = _value_counts(quotes, "applied_quote_placement_mode")
        fallback_to_join_count = sum(
            str(row.get("fallback_to_join", "")).strip().lower() == "true"
            for row in quotes
        )
        return {
            "window_start": self.window.start.isoformat(),
            "window_end": self.window.end.isoformat(),
            "partial": partial,
            "quote_placement_mode": runtime_applied.get("quote_placement_mode"),
            "runtime_applied": runtime_applied,
            "requested_quote_placement_mode_counts": requested_mode_counts,
            "applied_quote_placement_mode_counts": applied_mode_counts,
            "fallback_to_join_count": fallback_to_join_count,
            "fallback_to_join_rate": (
                fallback_to_join_count / len(quotes) if quotes else None
            ),
            "quote_decisions": len(quotes),
            "placed_orders": placed,
            "amended_orders": amended,
            "cancelled_orders": cancelled,
            "rejected_orders": sum(str(row.get("status", "")).lower() == "rejected" for row in orders),
            "expired_or_stale_orders": stale_orders,
            "partial_fills": sum(str(row.get("status", "")) == "PartiallyFilled" for row in orders),
            "full_fills": len(executions),
            "maker_fills": maker_fills,
            "taker_fills": taker_fills,
            "buy_volume": buy_volume,
            "sell_volume": sell_volume,
            "gross_turnover": turnover,
            "gross_spread_capture": gross_spread_capture,
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "net_pnl": realized + unrealized - fees,
            "execution_fees": fees,
            "fee_currencies": sorted({str(row.get("fee_currency", "")) for row in executions if row.get("fee_currency")}),
            "average_inventory": statistics.fmean(inventory_values) if inventory_values else self.inventory_carried_in,
            "maximum_absolute_inventory": maximum_absolute_inventory,
            "inventory_utilization": (
                maximum_absolute_inventory / maximum_inventory
                if maximum_inventory and maximum_inventory > 0
                else None
            ),
            "time_weighted_inventory": _time_weighted_inventory(
                self.rows["inventory_timeseries"],
                start=self.window.start,
                end=min(datetime.now(UTC), self.window.end),
                initial=self.inventory_carried_in,
            ),
            "inventory_carried_in": self.inventory_carried_in,
            "inventory_carried_out": float(inventory_carried_out),
            "average_order_lifetime_ms": statistics.fmean(order_lifetimes) if order_lifetimes else None,
            "average_time_to_fill_ms": statistics.fmean(time_to_fill) if time_to_fill else None,
            "fill_ratio": len(executions) / placed if placed else None,
            "fills_per_placed_order": len(executions) / placed if placed else None,
            "fills_per_quote_attempt": len(executions) / len(quotes) if quotes else None,
            "cancel_to_fill_ratio": cancelled / len(executions) if executions else None,
            "amend_to_fill_ratio": amended / len(executions) if executions else None,
            "post_only_rejection_count": sum("post" in str(row.get("reject_reason", "")).lower() for row in orders),
            "api_latency_ms": _latency_summary(self.api_latencies_ms),
            "market_data_latency_ms": _latency_summary(market_latencies),
            "private_execution_latency_ms": _latency_summary(execution_latencies),
            "spread_bps": _distribution(spreads),
            "quoted_spread_bps": _distribution(quoted_spreads),
            "microprice_minus_mid_bps": _distribution(microprice_offsets),
            "adverse_selection_rate": (
                sum(value < 0 for value in one_second_markouts) / len(one_second_markouts)
                if one_second_markouts
                else None
            ),
            "pnl_by_side": _pnl_by_side(executions),
            "pnl_by_volatility_bucket": _bucketed_pnl(
                executions, quote_by_id, "recent_volatility_bps"
            ),
            "pnl_by_spread_bucket": _bucketed_pnl(
                executions, quote_by_id, "spread_bps"
            ),
            "risk_rejections_by_reason": risk_reasons,
            "disconnect_count": sum("disconnect" in str(row.get("reason", "")).lower() for row in health),
            "reconnect_count": sum("reconnect" in str(row.get("reason", "")).lower() for row in health),
            "sequence_gaps": sum("gap" in str(row.get("reason", "")).lower() for row in health),
            "stale_book_duration_ms": _unhealthy_duration_ms(
                health,
                window_end=min(datetime.now(UTC), self.window.end),
            ),
            "unknown_or_reconciled_orders": sum("reconcil" in str(row.get("reason", "")).lower() for row in risks),
            "markouts": markout_by_horizon,
        }

    def _markdown_report(self, summary: Mapping[str, Any]) -> str:
        return "\n".join(
            [
                f"# Bybit Demo Market-Making Report — {self.symbol}",
                "",
                f"- Window: {summary['window_start']} to {summary['window_end']}",
                f"- Strategy: {self.strategy_name}",
                f"- Session: {self.session_id}",
                f"- Partial report: {summary['partial']}",
                "",
                "## Execution",
                "",
                f"- Quote decisions: {summary['quote_decisions']}",
                f"- Requested / applied placement: {summary['requested_quote_placement_mode_counts']} / {summary['applied_quote_placement_mode_counts']}",
                f"- Improve fallback-to-join rate: {summary['fallback_to_join_rate']}",
                f"- Placed / amended / cancelled: {summary['placed_orders']} / {summary['amended_orders']} / {summary['cancelled_orders']}",
                f"- Maker / taker fills: {summary['maker_fills']} / {summary['taker_fills']}",
                f"- Gross turnover: {summary['gross_turnover']}",
                "",
                "## PnL and Inventory",
                "",
                f"- Realized PnL in window: {summary['realized_pnl']}",
                f"- Unrealized PnL at window end: {summary['unrealized_pnl']}",
                f"- Execution fees: {summary['execution_fees']}",
                f"- Net PnL: {summary['net_pnl']}",
                f"- Inventory carried in: {summary['inventory_carried_in']}",
                f"- Inventory carried out: {summary['inventory_carried_out']}",
                "",
                "## Risk",
                "",
                f"- Risk events: {summary['risk_rejections_by_reason']}",
                f"- Sequence gaps: {summary['sequence_gaps']}",
                "",
            ]
        )

    @staticmethod
    def _write_csv(path: Path, columns: list[str], rows: list[Mapping[str, Any]]) -> None:
        extras = sorted({str(key) for row in rows for key in row if key not in columns})
        fieldnames = columns + extras
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True), encoding="utf-8")


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _last_numeric(rows: list[Mapping[str, Any]], key: str) -> float:
    values = [float(row[key]) for row in rows if _finite(row.get(key))]
    return values[-1] if values else 0.0


def _value_counts(rows: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, "")).strip()
        if value:
            counts[value] = counts.get(value, 0) + 1
    return counts


def _latency_summary(values: list[float]) -> dict[str, float | None]:
    ordered = sorted(value for value in values if math.isfinite(value))
    return {"p50": _percentile(ordered, 0.50), "p95": _percentile(ordered, 0.95), "p99": _percentile(ordered, 0.99)}


def _distribution(values: list[float]) -> dict[str, float | None]:
    ordered = sorted(value for value in values if math.isfinite(value))
    return {
        "mean": statistics.fmean(ordered) if ordered else None,
        "median": statistics.median(ordered) if ordered else None,
        "p95": _percentile(ordered, 0.95),
    }


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    index = (len(values) - 1) * quantile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return values[lower]
    weight = index - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def _order_lifetimes_ms(rows: list[Mapping[str, Any]]) -> list[float]:
    starts: dict[str, int] = {}
    lifetimes: list[float] = []
    for row in rows:
        key = str(row.get("order_id") or row.get("order_link_id") or "")
        timestamp = _to_epoch_ms(row.get("event_time"))
        if not key or timestamp is None:
            continue
        action = str(row.get("action", "")).lower()
        if action == "place":
            starts.setdefault(key, timestamp)
        elif action in {"cancel", "filled", "rejected"} and key in starts:
            lifetimes.append(float(timestamp - starts.pop(key)))
    return lifetimes


def _time_to_fill_ms(
    orders: list[Mapping[str, Any]], executions: list[Mapping[str, Any]]
) -> list[float]:
    placed: dict[str, int] = {}
    for row in orders:
        if str(row.get("action", "")).lower() != "place":
            continue
        key = str(row.get("order_id") or row.get("order_link_id") or "")
        timestamp = _to_epoch_ms(row.get("event_time"))
        if key and timestamp is not None:
            placed.setdefault(key, timestamp)
    values: list[float] = []
    for fill in executions:
        key = str(fill.get("order_id") or fill.get("order_link_id") or "")
        fill_time = _to_epoch_ms(fill.get("exec_time"))
        if key in placed and fill_time is not None and fill_time >= placed[key]:
            values.append(float(fill_time - placed[key]))
    return values


def _runtime_maximum_inventory(config: Mapping[str, Any]) -> float | None:
    runtime = config.get("runtime_applied")
    if not isinstance(runtime, Mapping):
        return None
    raw_value = runtime.get("runtime_maximum_inventory", runtime.get("maximum_inventory"))
    if not _finite(raw_value):
        return None
    value = float(raw_value)
    return value if value > 0 else None


def _runtime_applied(config: Mapping[str, Any]) -> dict[str, Any]:
    runtime = config.get("runtime_applied")
    if not isinstance(runtime, Mapping):
        return {}
    return {str(key): _jsonable(value) for key, value in runtime.items()}


def _gross_spread_capture(
    executions: list[Mapping[str, Any]],
    quote_by_id: Mapping[str, Mapping[str, Any]],
) -> float:
    total = 0.0
    for fill in executions:
        quote = quote_by_id.get(str(fill.get("quote_event_id", "")))
        if quote is None or not _finite(quote.get("fair_price")):
            continue
        price = float(fill.get("price", 0) or 0)
        quantity = float(fill.get("quantity", 0) or 0)
        fair = float(quote["fair_price"])
        direction = 1.0 if str(fill.get("side", "")).lower() == "sell" else -1.0
        total += direction * (price - fair) * quantity
    return total


def _pnl_by_side(executions: list[Mapping[str, Any]]) -> dict[str, float]:
    result = {"buy": 0.0, "sell": 0.0}
    for fill in executions:
        side = str(fill.get("side", "")).lower()
        if side in result:
            result[side] += float(fill.get("realized_pnl_delta", 0) or 0)
    return result


def _bucketed_pnl(
    executions: list[Mapping[str, Any]],
    quote_by_id: Mapping[str, Mapping[str, Any]],
    metric: str,
) -> dict[str, float]:
    observations: list[tuple[float, float]] = []
    for fill in executions:
        quote = quote_by_id.get(str(fill.get("quote_event_id", "")))
        if quote is None or not _finite(quote.get(metric)):
            continue
        observations.append(
            (float(quote[metric]), float(fill.get("realized_pnl_delta", 0) or 0))
        )
    result = {"low": 0.0, "medium": 0.0, "high": 0.0}
    if not observations:
        return result
    ordered = sorted(value for value, _ in observations)
    low_cut = _percentile(ordered, 1 / 3)
    high_cut = _percentile(ordered, 2 / 3)
    assert low_cut is not None and high_cut is not None
    for value, pnl in observations:
        bucket = "low" if value <= low_cut else "medium" if value <= high_cut else "high"
        result[bucket] += pnl
    return result


def _time_weighted_inventory(
    rows: list[Mapping[str, Any]],
    *,
    start: datetime,
    end: datetime,
    initial: float,
) -> float:
    if end <= start:
        return float(initial)
    events: list[tuple[datetime, float]] = []
    for row in rows:
        timestamp_ms = _to_epoch_ms(row.get("event_time"))
        if timestamp_ms is None:
            continue
        timestamp = datetime.fromtimestamp(timestamp_ms / 1_000, tz=UTC)
        if timestamp < start:
            initial = float(row.get("inventory", initial) or 0)
        elif timestamp <= end:
            events.append((timestamp, float(row.get("inventory", 0) or 0)))
    inventory = float(initial)
    cursor = start
    weighted = 0.0
    for timestamp, next_inventory in sorted(events):
        weighted += inventory * (timestamp - cursor).total_seconds()
        cursor = timestamp
        inventory = next_inventory
    weighted += inventory * (end - cursor).total_seconds()
    return weighted / (end - start).total_seconds()


def _unhealthy_duration_ms(
    rows: list[Mapping[str, Any]], *, window_end: datetime
) -> float:
    unhealthy_since: datetime | None = None
    total = 0.0
    for row in rows:
        timestamp_ms = _to_epoch_ms(row.get("event_time"))
        if timestamp_ms is None:
            continue
        timestamp = datetime.fromtimestamp(timestamp_ms / 1_000, tz=UTC)
        healthy = str(row.get("healthy", "")).lower() in {"true", "1", "yes"}
        if not healthy and unhealthy_since is None:
            unhealthy_since = timestamp
        elif healthy and unhealthy_since is not None:
            total += max(0.0, (timestamp - unhealthy_since).total_seconds() * 1_000.0)
            unhealthy_since = None
    if unhealthy_since is not None:
        total += max(0.0, (window_end - unhealthy_since).total_seconds() * 1_000.0)
    return total


def _to_epoch_ms(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        numeric = int(value)
        return numeric if numeric > 10_000_000_000 else numeric * 1_000
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp() * 1_000)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


__all__ = [
    "MARKOUT_HORIZONS_MS",
    "ReportingWindow",
    "SessionReporter",
    "TABLE_COLUMNS",
    "WindowClock",
    "redact_secrets",
]
