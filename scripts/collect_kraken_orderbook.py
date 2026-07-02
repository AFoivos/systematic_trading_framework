from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.market_data.order_book import LocalOrderBook


KRAKEN_SPOT_WS_V2_URL = "wss://ws.kraken.com/v2"
CSV_FIELDS = [
    "timestamp",
    "symbol",
    "event_type",
    "best_bid",
    "best_ask",
    "mid_price",
    "spread",
    "spread_bps",
    "imbalance_1",
    "imbalance_5",
    "bid_depth_5",
    "ask_depth_5",
    "sequence",
    "update_id",
    "checksum",
]


@dataclass(frozen=True)
class CollectorConfig:
    """Runtime config for the Kraken public order book collector."""

    symbol: str
    depth: int
    reconnect: bool
    max_events: int | None
    output_path: Path
    log_level: str


def load_config(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def parse_collector_config(config: dict[str, Any], *, output_override: str | None = None) -> CollectorConfig:
    """Validate YAML config for public data-only collection."""
    execution = config.get("execution", {})
    if execution.get("mode") != "data_only":
        raise SystemExit("Kraken public collector requires execution.mode: data_only.")
    if execution.get("venue") != "kraken_spot_public":
        raise SystemExit("Kraken public collector requires execution.venue: kraken_spot_public.")

    symbol = str(execution.get("symbol") or "").strip()
    if not symbol:
        raise SystemExit("execution.symbol is required, e.g. BTC/USD.")
    depth = int(execution.get("depth", 100))
    if depth <= 0:
        raise SystemExit("execution.depth must be > 0.")
    max_events_raw = execution.get("max_events", 1_000)
    max_events = None if max_events_raw is None else int(max_events_raw)
    if max_events is not None and max_events <= 0:
        raise SystemExit("execution.max_events must be > 0 when provided.")

    output_dir = Path(config.get("logging", {}).get("output_dir", "reports/market_making"))
    output_path = Path(output_override) if output_override else output_dir / "orderbook_events.csv"
    return CollectorConfig(
        symbol=symbol,
        depth=depth,
        reconnect=bool(execution.get("reconnect", True)),
        max_events=max_events,
        output_path=output_path,
        log_level=str(config.get("logging", {}).get("level", "INFO")),
    )


def build_book_subscription(symbol: str, depth: int) -> dict[str, Any]:
    """Build Kraken Spot WebSocket v2 public book subscription."""
    return {
        "method": "subscribe",
        "params": {
            "channel": "book",
            "symbol": [symbol],
            "depth": int(depth),
        },
    }


def apply_kraken_book_message(message: dict[str, Any], book: LocalOrderBook) -> list[dict[str, Any]]:
    """
    Apply a Kraken Spot WebSocket v2 book snapshot/update message to LocalOrderBook.

    Returns one CSV-ready row per book payload. Non-book control/heartbeat messages return [].
    Checksum is captured when present, but checksum validation is intentionally not implemented yet.
    """
    if message.get("channel") != "book":
        return []
    event_type = str(message.get("type", ""))
    if event_type not in {"snapshot", "update"}:
        return []

    rows: list[dict[str, Any]] = []
    for payload in _payloads(message.get("data")):
        timestamp = _parse_timestamp(payload.get("timestamp")) or datetime.now(timezone.utc)
        bids = _levels(payload.get("bids", ()))
        asks = _levels(payload.get("asks", ()))
        sequence = _optional_int(payload.get("sequence"))
        update_id = _optional_int(payload.get("update_id"))
        checksum = _optional_int(payload.get("checksum"))

        if event_type == "snapshot":
            book.apply_snapshot(bids=bids, asks=asks, timestamp=timestamp, sequence=sequence or update_id)
        else:
            book.apply_update(bids=bids, asks=asks, timestamp=timestamp, sequence=sequence or update_id)
        rows.append(book_to_csv_row(book, event_type=event_type, update_id=update_id, checksum=checksum))
    return rows


def book_to_csv_row(
    book: LocalOrderBook,
    *,
    event_type: str,
    update_id: int | None = None,
    checksum: int | None = None,
) -> dict[str, Any]:
    """Convert current local book state into one normalized event row."""
    depth_5 = book.depth(5)
    bid_depth_5 = sum(level.quantity for level in depth_5["bids"])
    ask_depth_5 = sum(level.quantity for level in depth_5["asks"])
    timestamp = book.timestamp or datetime.now(timezone.utc)
    return {
        "timestamp": timestamp.isoformat(),
        "symbol": book.symbol,
        "event_type": event_type,
        "best_bid": book.best_bid,
        "best_ask": book.best_ask,
        "mid_price": book.mid_price,
        "spread": book.spread,
        "spread_bps": book.spread_bps,
        "imbalance_1": book.imbalance(1),
        "imbalance_5": book.imbalance(5),
        "bid_depth_5": bid_depth_5,
        "ask_depth_5": ask_depth_5,
        "sequence": book.sequence,
        "update_id": update_id,
        "checksum": checksum,
    }


async def collect_orderbook(config: CollectorConfig) -> int:
    """Collect public Kraken order book events and write normalized CSV rows."""
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError("Missing dependency: install websockets to run the Kraken public collector.") from exc

    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    book = LocalOrderBook(config.symbol)
    events_written = 0
    backoff_seconds = 1.0

    with config.output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()

        while config.max_events is None or events_written < config.max_events:
            try:
                async with websockets.connect(KRAKEN_SPOT_WS_V2_URL, ping_interval=20, ping_timeout=20) as websocket:
                    await websocket.send(json.dumps(build_book_subscription(config.symbol, config.depth)))
                    logging.info("Subscribed to Kraken Spot public book: symbol=%s depth=%s", config.symbol, config.depth)
                    backoff_seconds = 1.0
                    async for raw_message in websocket:
                        message = json.loads(raw_message)
                        for row in apply_kraken_book_message(message, book):
                            writer.writerow(row)
                            events_written += 1
                            if config.max_events is not None and events_written >= config.max_events:
                                logging.info("Reached max_events=%s; stopping collector.", config.max_events)
                                return events_written
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logging.exception("Kraken public websocket collector error: %s", exc)
                if not config.reconnect:
                    raise
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2.0, 30.0)
                logging.info("Reconnecting to Kraken public websocket after %.1fs backoff.", backoff_seconds)
    return events_written


def _payloads(data: Any) -> Iterable[dict[str, Any]]:
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item
    elif isinstance(data, dict):
        yield data


def _levels(levels: Any) -> list[tuple[float, float]]:
    parsed: list[tuple[float, float]] = []
    if not isinstance(levels, list):
        return parsed
    for level in levels:
        if not isinstance(level, dict):
            continue
        price = level.get("price")
        quantity = level.get("qty", level.get("quantity"))
        if price is None or quantity is None:
            continue
        parsed.append((float(price), float(quantity)))
    return parsed


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Kraken Spot public WebSocket v2 book data.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    config = parse_collector_config(load_config(args.config), output_override=args.output)
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))
    logging.info("Starting public data-only collector. No API keys are used and no orders will be sent.")
    events = asyncio.run(collect_orderbook(config))
    logging.info("Wrote %s order book events to %s", events, config.output_path)


if __name__ == "__main__":
    main()
