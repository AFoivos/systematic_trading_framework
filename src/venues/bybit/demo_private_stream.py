from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import inspect
import json
import os
import time
from typing import Any, Awaitable, Callable, Mapping

import websockets

from .demo_rest_client import (
    BybitCredentials,
    DEMO_PRIVATE_WS_URL,
    validate_demo_private_ws_url,
)


Callback = Callable[..., Awaitable[None] | None]


def private_auth_message(credentials: BybitCredentials, *, expires_ms: int) -> dict[str, Any]:
    signature = hmac.new(
        credentials.api_secret.encode(),
        f"GET/realtime{expires_ms}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return {"op": "auth", "args": [credentials.api_key, expires_ms, signature]}


@dataclass(frozen=True)
class ExecutionUpdate:
    exec_id: str
    order_id: str
    order_link_id: str
    symbol: str
    side: str
    price: float
    quantity: float
    exec_time_ms: int
    is_maker: bool
    exec_fee: float
    fee_currency: str
    closed_size: float
    sequence: int | None
    receive_time_ms: int
    execution_latency_ms: float
    exec_pnl: float = 0.0

    @property
    def deduplication_key(self) -> tuple[str, str, str]:
        return (self.exec_id, self.order_id, self.symbol)


@dataclass(frozen=True)
class OrderUpdate:
    order_id: str
    order_link_id: str
    symbol: str
    side: str
    price: float
    quantity: float
    leaves_quantity: float
    cumulative_exec_quantity: float
    status: str
    reject_reason: str
    cancel_type: str
    updated_time_ms: int
    sequence: int | None


@dataclass(frozen=True)
class PositionUpdate:
    symbol: str
    side: str
    size: float
    average_price: float
    unrealized_pnl: float
    cumulative_realized_pnl: float
    updated_time_ms: int
    sequence: int | None

    @property
    def signed_size(self) -> float:
        if self.side.lower() == "buy":
            return self.size
        if self.side.lower() == "sell":
            return -self.size
        return 0.0


@dataclass(frozen=True)
class WalletUpdate:
    account_type: str
    total_equity: float
    total_wallet_balance: float
    total_available_balance: float
    coins: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)


class ExecutionDeduplicator:
    def __init__(self, *, maximum_keys: int = 100_000) -> None:
        self.maximum_keys = maximum_keys
        self._keys: set[tuple[str, str, str]] = set()
        self._insertion_order: list[tuple[str, str, str]] = []
        self.duplicate_count = 0

    def accept(self, execution: ExecutionUpdate) -> bool:
        key = execution.deduplication_key
        if key in self._keys:
            self.duplicate_count += 1
            return False
        self._keys.add(key)
        self._insertion_order.append(key)
        overflow = len(self._insertion_order) - self.maximum_keys
        if overflow > 0:
            for old in self._insertion_order[:overflow]:
                self._keys.discard(old)
            del self._insertion_order[:overflow]
        return True


class PrivateAccountState:
    """Confirmed inventory/account state with executions retained as the fill source."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.inventory = 0.0
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        self.wallet: WalletUpdate | None = None
        self.latest_position_time_ms = 0
        self.executions: list[ExecutionUpdate] = []

    def apply_execution(self, execution: ExecutionUpdate) -> tuple[float, float]:
        if execution.symbol != self.symbol:
            return self.inventory, self.inventory
        before = self.inventory
        if execution.exec_time_ms > self.latest_position_time_ms:
            signed = execution.quantity if execution.side.lower() == "buy" else -execution.quantity
            self.inventory += signed
        self.realized_pnl += execution.exec_pnl
        self.executions.append(execution)
        return before, self.inventory

    def apply_position(self, position: PositionUpdate) -> None:
        if position.symbol != self.symbol or position.updated_time_ms < self.latest_position_time_ms:
            return
        self.inventory = position.signed_size
        self.unrealized_pnl = position.unrealized_pnl
        self.realized_pnl = position.cumulative_realized_pnl
        self.latest_position_time_ms = position.updated_time_ms


def parse_execution_message(
    message: Mapping[str, Any],
    *,
    receive_time_ms: int,
    default_fee_currency: str = "USDT",
    clock_offset_ms: int = 0,
) -> list[ExecutionUpdate]:
    if message.get("topic") != "execution.linear":
        return []
    rows = message.get("data")
    if not isinstance(rows, list):
        return []
    parsed: list[ExecutionUpdate] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        exec_time = int(row.get("execTime", message.get("creationTime", 0)))
        sequence_value = row.get("seq", message.get("sequence"))
        parsed.append(
            ExecutionUpdate(
                exec_id=str(row.get("execId", "")),
                order_id=str(row.get("orderId", "")),
                order_link_id=str(row.get("orderLinkId", "")),
                symbol=str(row.get("symbol", "")),
                side=str(row.get("side", "")),
                price=float(row.get("execPrice", 0) or 0),
                quantity=float(row.get("execQty", 0) or 0),
                exec_time_ms=exec_time,
                is_maker=bool(row.get("isMaker", False)),
                exec_fee=float(row.get("execFee", 0) or 0),
                fee_currency=str(row.get("feeCurrency", default_fee_currency)),
                closed_size=float(row.get("closedSize", 0) or 0),
                sequence=int(sequence_value) if sequence_value not in {None, ""} else None,
                receive_time_ms=receive_time_ms,
                execution_latency_ms=max(
                    0.0, float(receive_time_ms + clock_offset_ms - exec_time)
                ),
                exec_pnl=float(row.get("execPnl", 0) or 0),
            )
        )
    return parsed


def parse_order_message(message: Mapping[str, Any]) -> list[OrderUpdate]:
    if message.get("topic") != "order.linear":
        return []
    rows = message.get("data")
    if not isinstance(rows, list):
        return []
    updates: list[OrderUpdate] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        sequence_value = row.get("seq", message.get("sequence"))
        updates.append(
            OrderUpdate(
                order_id=str(row.get("orderId", "")),
                order_link_id=str(row.get("orderLinkId", "")),
                symbol=str(row.get("symbol", "")),
                side=str(row.get("side", "")),
                price=float(row.get("price", 0) or 0),
                quantity=float(row.get("qty", 0) or 0),
                leaves_quantity=float(row.get("leavesQty", 0) or 0),
                cumulative_exec_quantity=float(row.get("cumExecQty", 0) or 0),
                status=str(row.get("orderStatus", "")),
                reject_reason=str(row.get("rejectReason", "")),
                cancel_type=str(row.get("cancelType", "")),
                updated_time_ms=int(row.get("updatedTime", message.get("creationTime", 0)) or 0),
                sequence=int(sequence_value) if sequence_value not in {None, ""} else None,
            )
        )
    return updates


def parse_position_message(message: Mapping[str, Any]) -> list[PositionUpdate]:
    if message.get("topic") != "position.linear":
        return []
    rows = message.get("data")
    if not isinstance(rows, list):
        return []
    updates: list[PositionUpdate] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        sequence_value = row.get("seq", message.get("sequence"))
        updates.append(
            PositionUpdate(
                symbol=str(row.get("symbol", "")),
                side=str(row.get("side", "")),
                size=float(row.get("size", 0) or 0),
                average_price=float(row.get("entryPrice", row.get("avgPrice", 0)) or 0),
                unrealized_pnl=float(row.get("unrealisedPnl", 0) or 0),
                cumulative_realized_pnl=float(row.get("curRealisedPnl", row.get("cumRealisedPnl", 0)) or 0),
                updated_time_ms=int(row.get("updatedTime", message.get("creationTime", 0)) or 0),
                sequence=int(sequence_value) if sequence_value not in {None, ""} else None,
            )
        )
    return updates


def parse_wallet_message(message: Mapping[str, Any]) -> list[WalletUpdate]:
    if message.get("topic") != "wallet":
        return []
    rows = message.get("data")
    if not isinstance(rows, list):
        return []
    updates: list[WalletUpdate] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        coins = row.get("coin") if isinstance(row.get("coin"), list) else []
        updates.append(
            WalletUpdate(
                account_type=str(row.get("accountType", "")),
                total_equity=float(row.get("totalEquity", 0) or 0),
                total_wallet_balance=float(row.get("totalWalletBalance", 0) or 0),
                total_available_balance=float(row.get("totalAvailableBalance", 0) or 0),
                coins=tuple(dict(coin) for coin in coins if isinstance(coin, Mapping)),
            )
        )
    return updates


class BybitDemoPrivateStream:
    """Authenticated Demo private stream; never provides WebSocket order entry."""

    TOPICS = ("order.linear", "execution.linear", "position.linear", "wallet")

    def __init__(
        self,
        *,
        credentials: BybitCredentials,
        url: str | None = None,
        maximum_silence_seconds: float = 30.0,
        clock_offset_ms: int = 0,
        on_execution: Callback | None = None,
        on_order: Callback | None = None,
        on_position: Callback | None = None,
        on_wallet: Callback | None = None,
        on_disconnect: Callback | None = None,
    ) -> None:
        self.credentials = credentials
        self.url = validate_demo_private_ws_url(
            url or os.environ.get("BYBIT_DEMO_PRIVATE_WS_URL", DEMO_PRIVATE_WS_URL)
        )
        self.maximum_silence_seconds = float(maximum_silence_seconds)
        self.clock_offset_ms = int(clock_offset_ms)
        if self.maximum_silence_seconds <= 0:
            raise ValueError("maximum_silence_seconds must be > 0.")
        self.on_execution = on_execution
        self.on_order = on_order
        self.on_position = on_position
        self.on_wallet = on_wallet
        self.on_disconnect = on_disconnect
        self.deduplicator = ExecutionDeduplicator()
        self.connected = False
        self.authenticated = False
        self.reconnects = 0
        self.last_message_monotonic = 0.0
        self.authenticated_event = asyncio.Event()
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
                    self.authenticated = False
                    self.authenticated_event.clear()
                    await self._authenticate(websocket)
                    await websocket.send(json.dumps({"op": "subscribe", "args": list(self.TOPICS)}))
                    backoff = 1.0
                    await self._consume(websocket)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.connected = False
                self.authenticated = False
                self.authenticated_event.clear()
                await self._emit(self.on_disconnect, f"private websocket disconnected: {type(exc).__name__}")
                if self._stop.is_set():
                    break
                self.reconnects += 1
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)
        self.connected = False
        self.authenticated = False

    async def wait_until_authenticated(self, timeout_seconds: float = 10.0) -> None:
        await asyncio.wait_for(self.authenticated_event.wait(), timeout=timeout_seconds)

    async def stop(self) -> None:
        self._stop.set()
        if self._websocket is not None:
            await self._websocket.close()

    async def _authenticate(self, websocket: Any) -> None:
        expires = time.time_ns() // 1_000_000 + 10_000
        await websocket.send(json.dumps(private_auth_message(self.credentials, expires_ms=expires)))
        raw = await asyncio.wait_for(websocket.recv(), timeout=10.0)
        message = json.loads(raw)
        if not isinstance(message, Mapping) or message.get("op") != "auth" or message.get("success") is not True:
            raise PermissionError("Bybit Demo private WebSocket authentication failed.")
        self.authenticated = True
        self.last_message_monotonic = time.monotonic()
        self.authenticated_event.set()

    async def _consume(self, websocket: Any) -> None:
        last_application_ping = time.monotonic()
        while not self._stop.is_set():
            try:
                raw = await asyncio.wait_for(websocket.recv(), timeout=1.0)
            except asyncio.TimeoutError:
                if time.monotonic() - last_application_ping >= 10.0:
                    await websocket.send(json.dumps({"op": "ping"}))
                    last_application_ping = time.monotonic()
                if time.monotonic() - self.last_message_monotonic > self.maximum_silence_seconds:
                    raise RuntimeError("private stream silence limit exceeded")
                continue
            receive_ms = time.time_ns() // 1_000_000
            self.last_message_monotonic = time.monotonic()
            message = json.loads(raw)
            if not isinstance(message, Mapping):
                continue
            topic = message.get("topic")
            if topic == "execution.linear":
                for execution in parse_execution_message(
                    message,
                    receive_time_ms=receive_ms,
                    clock_offset_ms=self.clock_offset_ms,
                ):
                    if self.deduplicator.accept(execution):
                        await self._emit(self.on_execution, execution)
            elif topic == "order.linear":
                for order in parse_order_message(message):
                    await self._emit(self.on_order, order)
            elif topic == "position.linear":
                for position in parse_position_message(message):
                    await self._emit(self.on_position, position)
            elif topic == "wallet":
                for wallet in parse_wallet_message(message):
                    await self._emit(self.on_wallet, wallet)

    @staticmethod
    async def _emit(callback: Callback | None, *args: Any) -> None:
        if callback is None:
            return
        result = callback(*args)
        if inspect.isawaitable(result):
            await result


__all__ = [
    "BybitDemoPrivateStream",
    "ExecutionDeduplicator",
    "ExecutionUpdate",
    "OrderUpdate",
    "PositionUpdate",
    "PrivateAccountState",
    "WalletUpdate",
    "parse_execution_message",
    "parse_order_message",
    "parse_position_message",
    "parse_wallet_message",
    "private_auth_message",
]
