from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import inspect
import json
import os
from pathlib import Path
import time
from typing import Any, Awaitable, Callable, Mapping

import websockets

from src.market_data.order_book import LocalOrderBook
from src.market_data.trades import Trade

from .demo_rest_client import PUBLIC_WS_URL, validate_public_ws_url


Callback = Callable[..., Awaitable[None] | None]


@dataclass(frozen=True)
class BookHealth:
    healthy: bool
    reason: str
    update_id: int | None
    cross_sequence: int | None
    matching_engine_timestamp_ms: int | None
    receive_timestamp_ms: int | None
    market_data_latency_ms: float | None


class SequenceGapError(RuntimeError):
    pass


class RotatingCompressedEventWriter:
    """Append-only gzip JSONL writer with UTC-day and size rotation."""

    def __init__(self, directory: str | Path, *, prefix: str, max_bytes: int = 64 * 1024 * 1024) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.prefix = prefix
        self.max_bytes = max(1, int(max_bytes))
        self._date = ""
        self._index = 0
        self._path: Path | None = None
        self._handle: Any = None

    @property
    def path(self) -> Path | None:
        return self._path

    def write(self, payload: Mapping[str, Any]) -> None:
        now = datetime.now(timezone.utc)
        date = now.strftime("%Y%m%d")
        if self._handle is None or date != self._date or self._should_rotate():
            self._rotate(date)
        assert self._handle is not None
        self._handle.write(json.dumps(dict(payload), separators=(",", ":"), default=str) + "\n")
        self._handle.flush()

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def retarget(self, directory: str | Path) -> None:
        self.close()
        self.directory = Path(directory)
        self._date = ""
        self._index = 0
        self._path = None

    def _should_rotate(self) -> bool:
        return bool(self._path and self._path.exists() and self._path.stat().st_size >= self.max_bytes)

    def _rotate(self, date: str) -> None:
        self.close()
        self.directory.mkdir(parents=True, exist_ok=True)
        if date != self._date:
            self._index = 0
        else:
            self._index += 1
        self._date = date
        self._path = self.directory / f"{self.prefix}_{date}_{self._index:04d}.jsonl.gz"
        self._handle = gzip.open(self._path, mode="at", encoding="utf-8", newline="\n")


class BybitOrderBookProcessor:
    """Causal reconstruction for Bybit V5 snapshot/delta order-book events."""

    def __init__(
        self,
        symbol: str,
        *,
        stale_book_ms: int = 2_000,
        clock_offset_ms: int = 0,
    ) -> None:
        if stale_book_ms <= 0:
            raise ValueError("stale_book_ms must be > 0.")
        self.symbol = symbol
        self.book = LocalOrderBook(symbol)
        self.stale_book_ms = int(stale_book_ms)
        self.clock_offset_ms = int(clock_offset_ms)
        self.snapshot_received = False
        self.healthy = False
        self.reason = "awaiting initial snapshot"
        self.update_id: int | None = None
        self.cross_sequence: int | None = None
        self.matching_engine_timestamp_ms: int | None = None
        self.receive_timestamp_ms: int | None = None
        self.sequence_gaps = 0
        self.crossed_books = 0
        self.ignored_noncausal_events = 0

    def process(self, message: Mapping[str, Any], *, receive_timestamp_ms: int | None = None) -> bool:
        topic = str(message.get("topic", ""))
        if topic != f"orderbook.50.{self.symbol}":
            return False
        data = message.get("data")
        if not isinstance(data, Mapping) or data.get("s") != self.symbol:
            return False
        event_type = str(message.get("type", ""))
        update_id = int(data.get("u", -1))
        cross_sequence = int(data.get("seq", -1))
        cts = int(data.get("cts", message.get("ts", 0)))
        received = int(receive_timestamp_ms or time.time_ns() // 1_000_000)
        # Staleness must use the local receive clock. The matching-engine timestamp is
        # retained separately for latency/audit and may be slightly ahead of a host clock.
        timestamp = datetime.fromtimestamp(received / 1_000, tz=timezone.utc)
        bids = self._levels(data.get("b", []))
        asks = self._levels(data.get("a", []))

        if event_type == "snapshot":
            try:
                self.book.apply_snapshot(
                    bids=bids,
                    asks=asks,
                    timestamp=timestamp,
                    sequence=cross_sequence,
                )
            except ValueError as exc:
                self.crossed_books += int("crossed book" in str(exc))
                self._invalidate(f"invalid order book snapshot: {exc}")
                return False
            self.snapshot_received = True
            self.healthy = True
            self.reason = "ok"
            self._advance(update_id, cross_sequence, cts, received)
            return True

        if event_type != "delta":
            return False
        if not self.snapshot_received or not self.healthy:
            self._invalidate("delta received before a valid snapshot")
            return False
        if self.update_id is not None and update_id <= self.update_id:
            self.ignored_noncausal_events += 1
            return False
        if self.update_id is not None and update_id != self.update_id + 1:
            self.sequence_gaps += 1
            self._invalidate(f"order book update-id gap: expected {self.update_id + 1}, received {update_id}")
            raise SequenceGapError(self.reason)
        if self.cross_sequence is not None and cross_sequence <= self.cross_sequence:
            self.ignored_noncausal_events += 1
            return False
        try:
            self.book.apply_update(
                bids=bids,
                asks=asks,
                timestamp=timestamp,
                sequence=cross_sequence,
            )
        except ValueError as exc:
            self.crossed_books += int("crossed book" in str(exc))
            self._invalidate(f"invalid order book delta: {exc}")
            return False
        self._advance(update_id, cross_sequence, cts, received)
        return True

    def is_stale(self, *, now_ms: int | None = None) -> bool:
        now = int(now_ms or time.time_ns() // 1_000_000)
        if self.receive_timestamp_ms is None:
            return True
        return now - self.receive_timestamp_ms > self.stale_book_ms

    def health(self, *, now_ms: int | None = None) -> BookHealth:
        stale = self.is_stale(now_ms=now_ms)
        healthy = self.healthy and not stale
        reason = "stale order book" if stale and self.snapshot_received else self.reason
        latency = None
        if self.matching_engine_timestamp_ms is not None and self.receive_timestamp_ms is not None:
            latency = max(
                0.0,
                float(
                    self.receive_timestamp_ms
                    + self.clock_offset_ms
                    - self.matching_engine_timestamp_ms
                ),
            )
        return BookHealth(
            healthy=healthy,
            reason=reason,
            update_id=self.update_id,
            cross_sequence=self.cross_sequence,
            matching_engine_timestamp_ms=self.matching_engine_timestamp_ms,
            receive_timestamp_ms=self.receive_timestamp_ms,
            market_data_latency_ms=latency,
        )

    def reset_for_resynchronization(self, reason: str) -> None:
        self.snapshot_received = False
        self.healthy = False
        self.reason = reason
        self.update_id = None
        self.cross_sequence = None
        self.matching_engine_timestamp_ms = None
        self.receive_timestamp_ms = None
        self.book = LocalOrderBook(self.symbol)

    def _advance(self, update_id: int, cross_sequence: int, cts: int, received: int) -> None:
        self.update_id = update_id
        self.cross_sequence = cross_sequence
        self.matching_engine_timestamp_ms = cts
        self.receive_timestamp_ms = received

    def _invalidate(self, reason: str) -> None:
        self.healthy = False
        self.reason = reason
        self.snapshot_received = False

    @staticmethod
    def _levels(raw: object) -> list[tuple[float, float]]:
        if not isinstance(raw, list):
            raise ValueError("Bybit order book levels must be an array.")
        levels: list[tuple[float, float]] = []
        for level in raw:
            if not isinstance(level, (list, tuple)) or len(level) != 2:
                raise ValueError("invalid Bybit order book level.")
            levels.append((float(level[0]), float(level[1])))
        return levels


def parse_public_trades(message: Mapping[str, Any]) -> list[Trade]:
    topic = str(message.get("topic", ""))
    if not topic.startswith("publicTrade."):
        return []
    raw = message.get("data")
    if not isinstance(raw, list):
        return []
    trades: list[Trade] = []
    for row in raw:
        if not isinstance(row, Mapping):
            continue
        side = str(row.get("S", "")).lower()
        trades.append(
            Trade(
                symbol=str(row.get("s", "")),
                price=float(row.get("p", 0)),
                quantity=float(row.get("v", 0)),
                timestamp=datetime.fromtimestamp(int(row.get("T", 0)) / 1_000, tz=timezone.utc),
                aggressor_side=side if side in {"buy", "sell"} else "unknown",
                trade_id=str(row.get("i", "")) or None,
            )
        )
    return trades


class BybitPublicMarketData:
    """Reconnectable public linear WebSocket client for one market-making symbol."""

    def __init__(
        self,
        *,
        symbol: str,
        stale_book_ms: int = 2_000,
        clock_offset_ms: int = 0,
        url: str | None = None,
        on_book: Callback | None = None,
        on_trade: Callback | None = None,
        on_health: Callback | None = None,
        raw_writer: RotatingCompressedEventWriter | None = None,
    ) -> None:
        self.symbol = symbol
        self.url = validate_public_ws_url(url or os.environ.get("BYBIT_PUBLIC_WS_URL", PUBLIC_WS_URL))
        self.processor = BybitOrderBookProcessor(
            symbol,
            stale_book_ms=stale_book_ms,
            clock_offset_ms=clock_offset_ms,
        )
        self.on_book = on_book
        self.on_trade = on_trade
        self.on_health = on_health
        self.raw_writer = raw_writer
        self.connected = False
        self.reconnects = 0
        self.disconnects = 0
        self._stop = asyncio.Event()
        self._websocket: Any = None

    async def run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                async with websockets.connect(
                    self.url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                    max_queue=4_096,
                ) as websocket:
                    self._websocket = websocket
                    self.connected = True
                    await websocket.send(
                        json.dumps(
                            {
                                "op": "subscribe",
                                "args": [
                                    f"orderbook.50.{self.symbol}",
                                    f"publicTrade.{self.symbol}",
                                ],
                            }
                        )
                    )
                    backoff = 1.0
                    await self._consume(websocket)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.connected = False
                self.disconnects += 1
                self.processor.reset_for_resynchronization(f"public websocket disconnected: {type(exc).__name__}")
                await self._emit(self.on_health, self.processor.health())
                if self._stop.is_set():
                    break
                self.reconnects += 1
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)
        self.connected = False

    async def stop(self) -> None:
        self._stop.set()
        if self._websocket is not None:
            await self._websocket.close()
        if self.raw_writer:
            self.raw_writer.close()

    async def _consume(self, websocket: Any) -> None:
        while not self._stop.is_set():
            try:
                raw = await asyncio.wait_for(websocket.recv(), timeout=0.5)
            except asyncio.TimeoutError:
                if self.processor.is_stale():
                    self.processor.healthy = False
                    self.processor.reason = "stale order book"
                    await self._emit(self.on_health, self.processor.health())
                    raise RuntimeError("stale order book")
                continue
            received_ms = time.time_ns() // 1_000_000
            message = json.loads(raw)
            if not isinstance(message, dict):
                continue
            if self.raw_writer and str(message.get("topic", "")).startswith("orderbook."):
                self.raw_writer.write({"receive_timestamp_ms": received_ms, "message": message})
            topic = str(message.get("topic", ""))
            if topic.startswith("orderbook."):
                try:
                    changed = self.processor.process(message, receive_timestamp_ms=received_ms)
                except SequenceGapError:
                    await self._emit(self.on_health, self.processor.health())
                    raise
                health = self.processor.health()
                await self._emit(self.on_health, health)
                if changed and health.healthy:
                    await self._emit(self.on_book, self.processor.book, health)
            elif topic.startswith("publicTrade."):
                for trade in parse_public_trades(message):
                    await self._emit(self.on_trade, trade, received_ms)

    @staticmethod
    async def _emit(callback: Callback | None, *args: Any) -> None:
        if callback is None:
            return
        result = callback(*args)
        if inspect.isawaitable(result):
            await result


__all__ = [
    "BookHealth",
    "BybitOrderBookProcessor",
    "BybitPublicMarketData",
    "RotatingCompressedEventWriter",
    "SequenceGapError",
    "parse_public_trades",
]
