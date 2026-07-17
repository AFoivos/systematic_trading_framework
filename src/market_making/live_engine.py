from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import math
import os
from pathlib import Path
import statistics
import time
from typing import Any, Literal, Mapping
import uuid

from src.market_data.order_book import LocalOrderBook
from src.market_data.trades import Trade
from src.market_making.fair_price import microprice
from src.market_making.quote_generator import QuoteDecision, QuoteGenerator, QuoteGeneratorConfig
from src.market_making.risk import RiskEngine, RiskLimits, RiskState
from src.market_making.session_reporting import SessionReporter
from src.market_making.spread_model import SpreadConfig
from src.market_making.strategies.adaptive_inventory import (
    AdaptiveInventoryMicropriceStrategy,
    AdaptiveInventoryStrategyConfig,
)
from src.venues.bybit.demo_private_stream import (
    BybitDemoPrivateStream,
    ExecutionUpdate,
    OrderUpdate,
    PositionUpdate,
    WalletUpdate,
    parse_execution_message,
)
from src.venues.bybit.demo_rest_client import (
    BybitCredentials,
    BybitDemoRestClient,
    UncertainOrderState,
    require_demo_execution_environment,
)
from src.venues.bybit.instrument import BybitInstrument
from src.venues.bybit.public_market_data import (
    BookHealth,
    BybitPublicMarketData,
    RotatingCompressedEventWriter,
)


UTC = timezone.utc
ExecutionMode = Literal["live_dry_run", "demo_submit"]


@dataclass
class InventoryLedger:
    inventory: float = 0.0
    average_entry_price: float = 0.0
    realized_pnl: float = 0.0
    fees: float = 0.0
    unrealized_pnl: float = 0.0

    def apply_fill(self, *, side: str, price: float, quantity: float, fee: float = 0.0) -> tuple[float, float, float]:
        if price <= 0 or quantity <= 0 or not all(map(math.isfinite, (price, quantity, fee))):
            raise ValueError("fill values must be finite with positive price and quantity.")
        before = self.inventory
        signed_quantity = quantity if side.lower() == "buy" else -quantity
        realized_delta = 0.0
        if before == 0 or before * signed_quantity > 0:
            new_inventory = before + signed_quantity
            self.average_entry_price = (
                (abs(before) * self.average_entry_price + abs(signed_quantity) * price)
                / abs(new_inventory)
            )
            self.inventory = new_inventory
        else:
            closing = min(abs(before), abs(signed_quantity))
            if before > 0:
                realized_delta = closing * (price - self.average_entry_price)
            else:
                realized_delta = closing * (self.average_entry_price - price)
            new_inventory = before + signed_quantity
            self.inventory = new_inventory
            if new_inventory == 0:
                self.average_entry_price = 0.0
            elif before * new_inventory < 0:
                self.average_entry_price = price
        self.realized_pnl += realized_delta
        self.fees += fee
        return before, self.inventory, realized_delta

    def mark(self, mid_price: float | None) -> float:
        if mid_price is None or mid_price <= 0 or self.inventory == 0:
            self.unrealized_pnl = 0.0
        elif self.inventory > 0:
            self.unrealized_pnl = self.inventory * (mid_price - self.average_entry_price)
        else:
            self.unrealized_pnl = abs(self.inventory) * (self.average_entry_price - mid_price)
        return self.unrealized_pnl

    def repair_from_position(self, *, inventory: float, average_price: float, unrealized_pnl: float) -> None:
        self.inventory = float(inventory)
        self.average_entry_price = float(average_price) if inventory else 0.0
        self.unrealized_pnl = float(unrealized_pnl)


@dataclass
class ActiveOrder:
    side: str
    order_id: str
    order_link_id: str
    price: Decimal
    quantity: Decimal
    leaves_quantity: Decimal
    created_monotonic: float
    quote_event_id: str


class OrderCoordinator:
    """One bid/one ask diff engine with REST-only Demo mutation paths."""

    def __init__(
        self,
        *,
        mode: ExecutionMode,
        rest_client: BybitDemoRestClient,
        instrument: BybitInstrument,
        reporter: SessionReporter,
        session_id: str,
        minimum_quote_lifetime_ms: int,
        minimum_reprice_ticks: int,
        maximum_quote_age_ms: int,
        maximum_cancel_rate_per_minute: int,
    ) -> None:
        self.mode = mode
        self.rest = rest_client
        self.instrument = instrument
        self.reporter = reporter
        self.session_id = session_id
        self.minimum_quote_lifetime_ms = int(minimum_quote_lifetime_ms)
        self.minimum_reprice_ticks = int(minimum_reprice_ticks)
        self.maximum_quote_age_ms = int(maximum_quote_age_ms)
        self.maximum_cancel_rate = int(maximum_cancel_rate_per_minute)
        if min(self.minimum_quote_lifetime_ms, self.minimum_reprice_ticks, self.maximum_quote_age_ms, self.maximum_cancel_rate) <= 0:
            raise ValueError("quote lifecycle and cancel-rate limits must be > 0.")
        self.active: dict[str, ActiveOrder] = {}
        self.known_orders: dict[str, ActiveOrder] = {}
        self._sequence = 0
        self._cancel_times: deque[float] = deque()

    async def synchronize(self, quote: QuoteDecision, *, quote_event_id: str) -> None:
        desired: dict[str, tuple[Decimal, Decimal]] = {}
        if quote.should_quote and quote.bid_price is not None and quote.bid_size > 0:
            desired["buy"] = (
                self.instrument.round_price(quote.bid_price, side="buy"),
                self.instrument.round_quantity(quote.bid_size),
            )
        if quote.should_quote and quote.ask_price is not None and quote.ask_size > 0:
            desired["sell"] = (
                self.instrument.round_price(quote.ask_price, side="sell"),
                self.instrument.round_quantity(quote.ask_size),
            )
        for side in list(self.active):
            if side not in desired:
                await self.cancel(side, reason="quote side no longer desired", force=False)
        for side, (price, quantity) in desired.items():
            self.instrument.validate_order(price=price, quantity=quantity)
            existing = self.active.get(side)
            if existing is None:
                await self.place(side, price, quantity, quote_event_id=quote_event_id)
                continue
            age_ms = (time.monotonic() - existing.created_monotonic) * 1_000.0
            tick_distance = abs(price - existing.price) / self.instrument.tick_size
            changed_quantity = quantity != existing.quantity
            if age_ms >= self.maximum_quote_age_ms:
                await self.cancel(side, reason="maximum quote age exceeded", force=True)
                await self.place(side, price, quantity, quote_event_id=quote_event_id)
            elif age_ms >= self.minimum_quote_lifetime_ms and (
                tick_distance >= self.minimum_reprice_ticks or changed_quantity
            ):
                await self.amend(side, price, quantity, quote_event_id=quote_event_id)

    async def place(self, side: str, price: Decimal, quantity: Decimal, *, quote_event_id: str) -> ActiveOrder:
        if side in self.active:
            raise RuntimeError(f"duplicate active {side} order protection triggered.")
        self._sequence += 1
        short_side = "b" if side == "buy" else "s"
        order_link_id = f"mm_{self.session_id}_{short_side}_{self._sequence}"
        if len(order_link_id) > 36:
            raise RuntimeError("generated orderLinkId exceeds Bybit's 36-character limit.")
        order_id = f"dry_{order_link_id}"
        if self.mode == "demo_submit":
            payload = await asyncio.to_thread(
                self.rest.place_order,
                category=self.instrument.category,
                symbol=self.instrument.symbol,
                side=side,
                price=self.instrument.format_decimal(price),
                quantity=self.instrument.format_decimal(quantity),
                order_link_id=order_link_id,
            )
            result = payload.get("result", {})
            order_id = str(result.get("orderId", "")) or order_id
        active = ActiveOrder(
            side=side,
            order_id=order_id,
            order_link_id=order_link_id,
            price=price,
            quantity=quantity,
            leaves_quantity=quantity,
            created_monotonic=time.monotonic(),
            quote_event_id=quote_event_id,
        )
        self.active[side] = active
        self.known_orders[active.order_id] = active
        self.known_orders[active.order_link_id] = active
        self._record_intent("place", active, quote_event_id, "new desired quote")
        self._record_order("place", active, "New")
        return active

    async def amend(self, side: str, price: Decimal, quantity: Decimal, *, quote_event_id: str) -> None:
        active = self.active[side]
        if self.mode == "demo_submit":
            await asyncio.to_thread(
                self.rest.amend_order,
                category=self.instrument.category,
                symbol=self.instrument.symbol,
                order_id=active.order_id,
                price=self.instrument.format_decimal(price),
                quantity=self.instrument.format_decimal(quantity),
            )
        active.price = price
        active.quantity = quantity
        active.leaves_quantity = quantity
        active.quote_event_id = quote_event_id
        self._record_intent("amend", active, quote_event_id, "reprice threshold exceeded")
        self._record_order("amend", active, "New")

    async def cancel(self, side: str, *, reason: str, force: bool = False) -> None:
        active = self.active.get(side)
        if active is None:
            return
        now = time.monotonic()
        while self._cancel_times and now - self._cancel_times[0] >= 60.0:
            self._cancel_times.popleft()
        if not force and len(self._cancel_times) >= self.maximum_cancel_rate:
            raise RuntimeError("maximum cancel rate exceeded")
        if self.mode == "demo_submit":
            await asyncio.to_thread(
                self.rest.cancel_order,
                category=self.instrument.category,
                symbol=self.instrument.symbol,
                order_id=active.order_id,
            )
        self._cancel_times.append(now)
        self.active.pop(side, None)
        self._record_intent("cancel", active, active.quote_event_id, reason)
        self._record_order("cancel", active, "Cancelled")

    async def cancel_all(self, *, reason: str) -> None:
        if self.mode == "demo_submit":
            await asyncio.to_thread(
                self.rest.cancel_all_orders,
                category=self.instrument.category,
                symbol=self.instrument.symbol,
            )
        for side in list(self.active):
            active = self.active.pop(side)
            self._record_intent("cancel", active, active.quote_event_id, reason)
            self._record_order("cancel", active, "Cancelled")

    def apply_order_update(self, update: OrderUpdate) -> None:
        match = next(
            (order for order in self.active.values() if order.order_id == update.order_id or order.order_link_id == update.order_link_id),
            None,
        )
        if match is not None:
            match.leaves_quantity = Decimal(str(update.leaves_quantity))
            if update.status in {"Cancelled", "Filled", "Rejected", "Deactivated"}:
                self.active.pop(match.side, None)
        self.reporter.record(
            "orders",
            {
                "event_time": _iso_ms(update.updated_time_ms),
                "order_id": update.order_id,
                "order_link_id": update.order_link_id,
                "symbol": update.symbol,
                "side": update.side,
                "price": update.price,
                "quantity": update.quantity,
                "leaves_quantity": update.leaves_quantity,
                "status": update.status,
                "action": "exchange_update",
                "reject_reason": update.reject_reason,
                "session_id": self.session_id,
            },
        )

    def find_order(self, *, order_id: str, order_link_id: str) -> ActiveOrder | None:
        return self.known_orders.get(order_id) or self.known_orders.get(order_link_id)

    def conservative_dry_fills(self, trade: Trade, *, receive_time_ms: int) -> list[ExecutionUpdate]:
        if self.mode != "live_dry_run":
            return []
        side = "buy" if trade.aggressor_side == "sell" else "sell"
        active = self.active.get(side)
        if active is None:
            return []
        # Equal-price prints may have consumed queue ahead, so only strict trade-through fills.
        crossed = trade.price < float(active.price) if side == "buy" else trade.price > float(active.price)
        if not crossed:
            return []
        quantity = min(float(active.leaves_quantity), trade.quantity)
        active.leaves_quantity -= Decimal(str(quantity))
        self._sequence += 1
        execution = ExecutionUpdate(
            exec_id=f"dry_exec_{self._sequence}",
            order_id=active.order_id,
            order_link_id=active.order_link_id,
            symbol=self.instrument.symbol,
            side="Buy" if side == "buy" else "Sell",
            price=float(active.price),
            quantity=quantity,
            exec_time_ms=int(trade.timestamp.timestamp() * 1_000),
            is_maker=True,
            exec_fee=0.0,
            fee_currency=self.instrument.settle_coin,
            closed_size=0.0,
            sequence=None,
            receive_time_ms=receive_time_ms,
            execution_latency_ms=float(receive_time_ms - int(trade.timestamp.timestamp() * 1_000)),
        )
        if active.leaves_quantity <= 0:
            self.active.pop(side, None)
            self._record_order("filled", active, "Filled")
        else:
            self._record_order("partial_fill", active, "PartiallyFilled")
        return [execution]

    def _record_intent(self, action: str, active: ActiveOrder, quote_event_id: str, reason: str) -> None:
        self.reporter.record(
            "order_intents",
            {
                "intent_time": datetime.now(UTC),
                "intent_id": uuid.uuid4().hex[:16],
                "quote_event_id": quote_event_id,
                "action": action,
                "side": active.side,
                "price": str(active.price),
                "quantity": str(active.quantity),
                "order_id": active.order_id,
                "order_link_id": active.order_link_id,
                "reason": reason,
                "mode": self.mode,
                "session_id": self.session_id,
            },
        )

    def _record_order(self, action: str, active: ActiveOrder, status: str) -> None:
        self.reporter.record(
            "orders",
            {
                "event_time": datetime.now(UTC),
                "order_id": active.order_id,
                "order_link_id": active.order_link_id,
                "symbol": self.instrument.symbol,
                "side": active.side,
                "price": str(active.price),
                "quantity": str(active.quantity),
                "leaves_quantity": str(active.leaves_quantity),
                "status": status,
                "action": action,
                "session_id": self.session_id,
            },
        )


class BybitLiveMarketMakingEngine:
    """Safety-first live market-data loop with dry-run or Bybit Demo execution."""

    def __init__(
        self,
        *,
        config: Mapping[str, Any],
        strategy_config: Mapping[str, Any],
        mode: ExecutionMode,
        duration_seconds: int | None = None,
        max_windows: int | None = None,
        aligned_windows: bool | None = None,
        flatten_at_boundary: bool | None = None,
        cancel_all_on_exit: bool = True,
        rest_client: BybitDemoRestClient | None = None,
    ) -> None:
        if mode not in {"live_dry_run", "demo_submit"}:
            raise ValueError("mode must be live_dry_run or demo_submit.")
        self.config = dict(config)
        self.strategy_config = dict(strategy_config)
        self.mode = mode
        self.duration_seconds = duration_seconds
        self.max_windows = max_windows
        self.cancel_all_on_exit = bool(cancel_all_on_exit)
        execution = _section(config, "execution")
        market_data = _section(config, "market_data")
        session = _section(config, "session")
        self.symbol = str(execution.get("symbol", "BTCUSDT"))
        self.category = str(execution.get("category", "linear"))
        self.session_id = uuid.uuid4().hex[:6]
        self.aligned_windows = bool(session.get("aligned_windows", True) if aligned_windows is None else aligned_windows)
        self.flatten_at_boundary = bool(session.get("flatten_at_boundary", False) if flatten_at_boundary is None else flatten_at_boundary)
        self.reporting_interval_seconds = int(session.get("reporting_interval_seconds", 7_200))
        self.reconciliation_interval_seconds = int(session.get("reconciliation_interval_seconds", 60))
        self.quote_refresh_ms = int(execution.get("quote_refresh_interval_ms", 500))
        self.maximum_volatility_bps = float(_section(config, "risk").get("maximum_recent_volatility_bps", 50.0))
        self.rest = rest_client or BybitDemoRestClient(
            base_url=os.environ.get(
                "BYBIT_DEMO_REST_URL",
                str(execution.get("rest_url") or "https://api-demo.bybit.com"),
            ),
            max_requests_per_second=int(_section(config, "rate_limits").get("maximum_requests_per_second", 8)),
        )
        output_root = _section(config, "logging").get(
            "output_dir", "logs/experiments/market_making/bybit_demo"
        )
        merged_config = {"execution_config": self.config, "strategy_config": self.strategy_config}
        self.reporter = SessionReporter(
            root=Path(str(output_root)),
            strategy_name="adaptive_inventory_microprice",
            symbol=self.symbol,
            session_id=self.session_id,
            config=merged_config,
            interval_seconds=self.reporting_interval_seconds,
            aligned_windows=self.aligned_windows,
        )
        self.maximum_consecutive_api_errors = int(
            _section(config, "risk").get("maximum_consecutive_api_errors", 3)
        )
        self._consecutive_api_errors = 0
        self._fatal_async_reason: str | None = None
        self.rest._latency_callback = self._record_api_latency
        self.rest._error_callback = self._record_api_error
        self.rest._success_callback = self._record_api_success
        self.ledger = InventoryLedger()
        self.instrument: BybitInstrument | None = None
        self.strategy: AdaptiveInventoryMicropriceStrategy | None = None
        self.risk_engine: RiskEngine | None = None
        self.order_coordinator: OrderCoordinator | None = None
        self.public: BybitPublicMarketData | None = None
        self.private: BybitDemoPrivateStream | None = None
        self._public_task: asyncio.Task[None] | None = None
        self._private_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._book_ready = asyncio.Event()
        self._latest_health: BookHealth | None = None
        self._mids: deque[float] = deque(maxlen=int(execution.get("volatility_lookback_events", 120)))
        self._returns: deque[float] = deque(maxlen=int(execution.get("volatility_lookback_events", 120)))
        self._seen_exec_ids: set[tuple[str, str, str]] = set()
        self._latest_position_update_ms = 0
        self._pending_position_mismatch: tuple[PositionUpdate, float] | None = None
        self._kill_lock = asyncio.Lock()
        self._shutting_down = False
        self._windows_written = 0
        self._last_reconcile = time.monotonic()
        self._clock_offset_ms = 0
        self._raw_writer: RotatingCompressedEventWriter | None = None

    async def run(self) -> tuple[Path, ...]:
        self._validate_static_safety()
        started = time.monotonic()
        unhandled: BaseException | None = None
        try:
            await self._startup()
            next_quote = 0.0
            while not self._stop.is_set():
                now_monotonic = time.monotonic()
                if self._fatal_async_reason:
                    await self._kill_switch(self._fatal_async_reason)
                    continue
                await self._check_pending_position_mismatch()
                if self.duration_seconds is not None and now_monotonic - started >= self.duration_seconds:
                    break
                if self.max_windows is not None and self._windows_written >= self.max_windows:
                    break
                if self.reporter.boundary_due():
                    await self._rotate_window()
                if now_monotonic - self._last_reconcile >= self.reconciliation_interval_seconds:
                    await self._reconcile(reason="periodic")
                    self._last_reconcile = now_monotonic
                if now_monotonic >= next_quote:
                    await self._quote_cycle()
                    next_quote = now_monotonic + self.quote_refresh_ms / 1_000.0
                await asyncio.sleep(0.05)
        except (KeyboardInterrupt, asyncio.CancelledError) as exc:
            unhandled = exc
        except BaseException as exc:
            unhandled = exc
            await self._kill_switch(f"unhandled exception: {type(exc).__name__}")
        finally:
            await self.shutdown(partial=True)
        if unhandled is not None and not isinstance(unhandled, (KeyboardInterrupt, asyncio.CancelledError)):
            raise unhandled
        return self.reporter.written_directories

    async def request_stop(self) -> None:
        self._stop.set()

    async def shutdown(self, *, partial: bool = True) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        self._stop.set()
        reconciliation: Mapping[str, Any] = {"status": "not_started"}
        open_orders: list[Mapping[str, Any]] = []
        positions: list[Mapping[str, Any]] = []
        try:
            if self.order_coordinator and (self.cancel_all_on_exit or self.mode == "demo_submit"):
                await self.order_coordinator.cancel_all(reason="graceful shutdown")
                await self._verify_no_open_orders()
            reconciliation = await self._reconcile(reason="shutdown", kill_on_mismatch=False)
            open_orders = list(reconciliation.get("open_orders", []))
            positions = list(reconciliation.get("positions", []))
        finally:
            if not self.reporter.written_directories or any(self.reporter.rows.values()):
                try:
                    self.reporter.finalize(
                        reconciliation=reconciliation,
                        open_orders_at_end=open_orders,
                        position_at_end=positions,
                        inventory_carried_out=self.ledger.inventory,
                        partial=partial,
                    )
                except FileExistsError:
                    pass
            if self.public:
                await self.public.stop()
            if self.private:
                await self.private.stop()
            for task in (self._public_task, self._private_task):
                if task:
                    task.cancel()
            await asyncio.gather(
                *(task for task in (self._public_task, self._private_task) if task),
                return_exceptions=True,
            )
            self.rest.close()

    async def _startup(self) -> None:
        self._clock_offset_ms = await asyncio.to_thread(
            self.rest.require_clock_synchronized
        )
        self.instrument = await asyncio.to_thread(
            self.rest.load_instrument, category=self.category, symbol=self.symbol
        )
        raw_writer = RotatingCompressedEventWriter(
            self.reporter.prepare_window_directory(),
            prefix=f"orderbook_events_{self.symbol}_{self.session_id}",
            max_bytes=int(_section(self.config, "logging").get("raw_orderbook_rotation_bytes", 64 * 1024 * 1024)),
        )
        self._raw_writer = raw_writer
        self.public = BybitPublicMarketData(
            symbol=self.symbol,
            stale_book_ms=int(_section(self.config, "market_data").get("stale_book_ms", 2_000)),
            clock_offset_ms=self._clock_offset_ms,
            url=os.environ.get(
                "BYBIT_PUBLIC_WS_URL",
                str(_section(self.config, "market_data").get("public_websocket_url", "wss://stream.bybit.com/v5/public/linear")),
            ),
            on_book=self._on_book,
            on_trade=self._on_public_trade,
            on_health=self._on_health,
            raw_writer=raw_writer,
        )
        self._public_task = asyncio.create_task(self.public.run(), name="bybit-public-market-data")
        await asyncio.wait_for(self._book_ready.wait(), timeout=30.0)
        assert self.public.processor.book.mid_price is not None
        self._build_strategy_and_risk(self.public.processor.book.mid_price)
        assert self.instrument is not None
        rate_limits = _section(self.config, "rate_limits")
        self.order_coordinator = OrderCoordinator(
            mode=self.mode,
            rest_client=self.rest,
            instrument=self.instrument,
            reporter=self.reporter,
            session_id=self.session_id,
            minimum_quote_lifetime_ms=int(rate_limits.get("minimum_quote_lifetime_ms", 750)),
            minimum_reprice_ticks=int(rate_limits.get("minimum_reprice_ticks", 2)),
            maximum_quote_age_ms=int(rate_limits.get("maximum_quote_age_ms", 5_000)),
            maximum_cancel_rate_per_minute=int(rate_limits.get("maximum_cancel_rate_per_minute", 30)),
        )
        open_orders: list[Mapping[str, Any]] = []
        positions: list[Mapping[str, Any]] = []
        if self.mode == "demo_submit":
            credentials = BybitCredentials.from_env()
            self.rest.credentials = credentials
            self.private = BybitDemoPrivateStream(
                credentials=credentials,
                url=os.environ.get(
                    "BYBIT_DEMO_PRIVATE_WS_URL",
                    str(_section(self.config, "execution").get("private_websocket_url", "wss://stream-demo.bybit.com/v5/private")),
                ),
                maximum_silence_seconds=float(_section(self.config, "risk").get("maximum_private_stream_silence_seconds", 30)),
                clock_offset_ms=self._clock_offset_ms,
                on_execution=self._on_execution,
                on_order=self._on_order,
                on_position=self._on_position,
                on_wallet=self._on_wallet,
                on_disconnect=self._on_private_disconnect,
            )
            self._private_task = asyncio.create_task(self.private.run(), name="bybit-demo-private-stream")
            await self.private.wait_until_authenticated()
            await asyncio.to_thread(
                self.rest.get_wallet_balance,
                account_type=str(_section(self.config, "execution").get("account_type", "UNIFIED")),
            )
            open_orders = await asyncio.to_thread(
                self.rest.get_open_orders, category=self.category, symbol=self.symbol
            )
            if open_orders:
                raise RuntimeError("Demo submission refused: unknown open orders exist at startup.")
            positions = await asyncio.to_thread(
                self.rest.get_positions, category=self.category, symbol=self.symbol
            )
            self._repair_position(positions)
        self.reporter.set_start_state(
            open_orders=open_orders,
            positions=positions,
            inventory=self.ledger.inventory,
        )

    def _build_strategy_and_risk(self, reference_price: float) -> None:
        assert self.instrument is not None
        quote_cfg = _section(self.strategy_config, "quote")
        fees_cfg = _section(self.strategy_config, "fees")
        params = _section(_section(self.strategy_config, "strategy"), "parameters")
        risk_cfg = _section(self.config, "risk")
        # Strategy YAML exchange constraints are validator-only placeholders. Live
        # sizing and final validation are derived exclusively from instruments-info.
        order_size = self.instrument.minimum_valid_quantity(reference_price)
        inventory_multiple = float(risk_cfg.get("maximum_inventory_order_multiple", 4))
        if not 3 <= inventory_multiple <= 5:
            raise ValueError("maximum_inventory_order_multiple must be between 3 and 5.")
        max_inventory = float(order_size) * inventory_multiple
        generator = QuoteGenerator(
            QuoteGeneratorConfig(
                fair_price_model=str(quote_cfg.get("fair_price_model", "microprice")),
                quote_placement_mode=str(quote_cfg.get("quote_placement_mode", "fair_price_bps")),
                spread=SpreadConfig(
                    model=str(quote_cfg.get("spread_model", "volatility_adjusted")),
                    base_spread_bps=float(quote_cfg.get("base_spread_bps", 8.0)),
                    min_spread_bps=float(quote_cfg.get("min_spread_bps", 6.0)),
                    max_spread_bps=float(quote_cfg.get("max_spread_bps", 30.0)),
                    maker_fee_bps=float(fees_cfg.get("maker_fee_bps", 0.0)),
                    taker_fee_bps=float(fees_cfg.get("taker_fee_bps", 0.0)),
                    volatility_multiplier=float(quote_cfg.get("volatility_multiplier", 1.0)),
                ),
                inventory_skew_strength=float(quote_cfg.get("inventory_skew_strength", 1.5)),
                order_size=float(order_size),
                max_inventory=max_inventory,
                tick_size=float(self.instrument.tick_size),
                lot_size=float(self.instrument.quantity_step),
                min_order_size=float(self.instrument.minimum_order_quantity),
                min_notional=float(self.instrument.minimum_notional),
            )
        )
        self.strategy = AdaptiveInventoryMicropriceStrategy(
            quote_generator=generator,
            config=AdaptiveInventoryStrategyConfig(
                maker_fee_bps=float(fees_cfg.get("maker_fee_bps", 0.0)),
                min_expected_edge_bps=float(params.get("min_expected_edge_bps", 0.0)),
                adverse_selection_buffer_bps=float(params.get("adverse_selection_buffer_bps", 0.0)),
                inventory_penalty_bps_per_unit=float(params.get("inventory_penalty_bps_per_unit", 0.0)),
            ),
        )
        self.risk_engine = RiskEngine(
            RiskLimits(
                max_inventory=max_inventory,
                max_position_value=float(risk_cfg.get("maximum_position_value", 50.0)),
                max_daily_loss=float(risk_cfg.get("maximum_session_loss", 5.0)),
                max_open_orders=2,
                max_order_size=float(order_size),
                max_allowed_spread_bps=float(risk_cfg.get("maximum_allowed_spread_bps", 25.0)),
                stale_order_book_ms=int(_section(self.config, "market_data").get("stale_book_ms", 2_000)),
            )
        )
        self.reporter.config["runtime_applied"] = {
            "quote_placement_mode": generator.config.quote_placement_mode,
            "instrument_tick_size": str(self.instrument.tick_size),
            "instrument_quantity_step": str(self.instrument.quantity_step),
            "instrument_minimum_order_quantity": str(
                self.instrument.minimum_order_quantity
            ),
            "instrument_minimum_notional": str(self.instrument.minimum_notional),
            "runtime_order_size": float(order_size),
            "runtime_maximum_inventory": max_inventory,
        }

    async def _quote_cycle(self) -> None:
        if not self.public or not self.strategy or not self.risk_engine or not self.order_coordinator:
            return
        health = self.public.processor.health()
        book = self.public.processor.book
        if not health.healthy:
            await self._kill_switch(health.reason)
            return
        volatility_bps = statistics.pstdev(self._returns) * 10_000.0 if len(self._returns) >= 2 else 0.0
        if volatility_bps > self.maximum_volatility_bps:
            await self._kill_switch("excessive recent volatility")
            return
        decision = self.strategy.decide(
            book=book,
            inventory=self.ledger.inventory,
            recent_returns=list(self._returns),
        )
        quote = decision.quote
        risk = self.risk_engine.check_quote(
            quote=quote,
            book=book,
            state=RiskState(
                inventory=self.ledger.inventory,
                realized_pnl=self.ledger.realized_pnl - self.ledger.fees,
                unrealized_pnl=self.ledger.mark(book.mid_price),
                open_orders=len(self.order_coordinator.active),
                websocket_connected=self.public.connected and (
                    self.mode == "live_dry_run" or bool(self.private and self.private.connected and self.private.authenticated)
                ),
            ),
        )
        quote_event_id = uuid.uuid4().hex[:16]
        placement = quote.diagnostics
        self.reporter.record(
            "quote_events",
            {
                "quote_event_id": quote_event_id,
                "event_time": datetime.now(UTC),
                "symbol": self.symbol,
                "fair_price": quote.fair_price,
                "microprice": microprice(book),
                "mid_price": book.mid_price,
                "bid_price": quote.bid_price,
                "ask_price": quote.ask_price,
                "bid_size": quote.bid_size,
                "ask_size": quote.ask_size,
                "spread_bps": quote.spread_bps,
                "requested_quote_placement_mode": placement.get(
                    "requested_quote_placement_mode"
                ),
                "applied_quote_placement_mode": placement.get(
                    "applied_quote_placement_mode"
                ),
                "best_bid": placement.get("best_bid"),
                "best_ask": placement.get("best_ask"),
                "tick_size": placement.get("tick_size"),
                "quoted_bid": placement.get("quoted_bid"),
                "quoted_ask": placement.get("quoted_ask"),
                "quoted_spread_ticks": placement.get("quoted_spread_ticks"),
                "quoted_spread_bps": placement.get("quoted_spread_bps"),
                "fallback_to_join": placement.get("fallback_to_join"),
                "inventory": self.ledger.inventory,
                "recent_volatility_bps": volatility_bps,
                "strategy_allowed": quote.should_quote,
                "strategy_reason": quote.reason,
                "risk_allowed": risk.allowed,
                "risk_reason": risk.reason,
                "session_id": self.session_id,
            },
        )
        if risk.kill_switch:
            await self._kill_switch(risk.reason)
        elif risk.allowed:
            try:
                await self.order_coordinator.synchronize(quote, quote_event_id=quote_event_id)
            except (UncertainOrderState, RuntimeError) as exc:
                await self._kill_switch(str(exc))
        else:
            rejected = QuoteDecision(
                symbol=quote.symbol,
                bid_price=None,
                ask_price=None,
                bid_size=0.0,
                ask_size=0.0,
                fair_price=quote.fair_price,
                spread_bps=quote.spread_bps,
                inventory_ratio=quote.inventory_ratio,
                should_quote=False,
                reason=risk.reason,
                timestamp=quote.timestamp,
                diagnostics=quote.diagnostics,
            )
            await self.order_coordinator.synchronize(rejected, quote_event_id=quote_event_id)

    async def _on_book(self, book: LocalOrderBook, health: BookHealth) -> None:
        mid = book.mid_price
        if mid is None:
            return
        if self._mids and self._mids[-1] > 0:
            self._returns.append(mid / self._mids[-1] - 1.0)
        self._mids.append(mid)
        self.reporter.record_midpoint(
            timestamp_ms=health.matching_engine_timestamp_ms or int(datetime.now(UTC).timestamp() * 1_000),
            mid_price=mid,
        )
        if health.healthy:
            self._book_ready.set()

    async def _on_health(self, health: BookHealth) -> None:
        self._latest_health = health
        book = self.public.processor.book if self.public else None
        self.reporter.record(
            "orderbook_health",
            {
                "event_time": datetime.now(UTC),
                **health.__dict__,
                "best_bid": book.best_bid if book else None,
                "best_ask": book.best_ask if book else None,
                "spread_bps": book.spread_bps if book else None,
            },
        )
        if not health.healthy and self.order_coordinator:
            await self._kill_switch(health.reason)

    async def _on_public_trade(self, trade: Trade, receive_time_ms: int) -> None:
        trade_ms = int(trade.timestamp.timestamp() * 1_000)
        self.reporter.record(
            "public_trades",
            {
                "trade_id": trade.trade_id,
                "symbol": trade.symbol,
                "price": trade.price,
                "quantity": trade.quantity,
                "aggressor_side": trade.aggressor_side,
                "trade_time": trade.timestamp,
                "receive_time": _iso_ms(receive_time_ms),
                "market_data_latency_ms": max(
                    0, receive_time_ms + self._clock_offset_ms - trade_ms
                ),
            },
        )
        if self.order_coordinator:
            for execution in self.order_coordinator.conservative_dry_fills(trade, receive_time_ms=receive_time_ms):
                await self._on_execution(execution)

    async def _on_execution(self, execution: ExecutionUpdate) -> None:
        if execution.deduplication_key in self._seen_exec_ids:
            return
        self._seen_exec_ids.add(execution.deduplication_key)
        before, after, realized_delta = self.ledger.apply_fill(
            side=execution.side,
            price=execution.price,
            quantity=execution.quantity,
            fee=execution.exec_fee,
        )
        quote_event_id = ""
        if self.order_coordinator:
            active = self.order_coordinator.find_order(
                order_id=execution.order_id,
                order_link_id=execution.order_link_id,
            )
            if active:
                quote_event_id = active.quote_event_id
        row = {
            "exec_id": execution.exec_id,
            "order_id": execution.order_id,
            "order_link_id": execution.order_link_id,
            "symbol": execution.symbol,
            "side": execution.side.lower(),
            "price": execution.price,
            "quantity": execution.quantity,
            "exec_time": _iso_ms(execution.exec_time_ms),
            "is_maker": execution.is_maker,
            "exec_fee": execution.exec_fee,
            "fee_currency": execution.fee_currency,
            "closed_size": execution.closed_size,
            "sequence": execution.sequence,
            "receive_time": _iso_ms(execution.receive_time_ms),
            "execution_latency_ms": execution.execution_latency_ms,
            "quote_event_id": quote_event_id,
            "strategy_name": "adaptive_inventory_microprice",
            "session_id": self.session_id,
            "inventory_before": before,
            "inventory_after": after,
            "realized_pnl_delta": realized_delta,
        }
        self.reporter.record("executions", row)
        self.reporter.record("fills", row)
        self.reporter.record(
            "fees",
            {
                "exec_id": execution.exec_id,
                "event_time": _iso_ms(execution.exec_time_ms),
                "fee": execution.exec_fee,
                "currency": execution.fee_currency,
                "is_maker": execution.is_maker,
            },
        )
        self._record_account_timeseries(source="execution")
        if self._pending_position_mismatch and self.instrument:
            pending, _ = self._pending_position_mismatch
            tolerance = float(self.instrument.quantity_step) / 2
            if abs(pending.signed_size - self.ledger.inventory) <= tolerance:
                self._pending_position_mismatch = None

    async def _on_order(self, update: OrderUpdate) -> None:
        if self.order_coordinator:
            self.order_coordinator.apply_order_update(update)
        if update.status == "Rejected" and "post" in update.reject_reason.lower():
            self.reporter.record(
                "risk_events",
                {"event_time": datetime.now(UTC), "reason": "post-only rejection", "kill_switch": False},
            )

    async def _on_position(self, update: PositionUpdate) -> None:
        if update.symbol != self.symbol:
            return
        if update.updated_time_ms < self._latest_position_update_ms:
            return
        self._latest_position_update_ms = update.updated_time_ms
        if self.instrument and abs(update.signed_size - self.ledger.inventory) > float(self.instrument.quantity_step) / 2:
            # Position and execution topics can arrive out of order. Give the canonical
            # execution stream a short grace period, then reconcile through REST.
            self._pending_position_mismatch = (update, time.monotonic())
        else:
            self.ledger.unrealized_pnl = update.unrealized_pnl
            self._pending_position_mismatch = None
        self._record_account_timeseries(source="position")

    async def _on_wallet(self, update: WalletUpdate) -> None:
        # Wallet data is retained in reconciliation; no secret or credential fields are logged.
        if not math.isfinite(update.total_equity):
            await self._kill_switch("invalid wallet state")

    async def _on_private_disconnect(self, reason: str) -> None:
        if not self._shutting_down:
            await self._kill_switch(reason)

    async def _kill_switch(self, reason: str) -> None:
        async with self._kill_lock:
            if self.risk_engine:
                decision = self.risk_engine.trigger_kill_switch(reason)
            else:
                decision = None
            self.reporter.record(
                "risk_events",
                {
                    "event_time": datetime.now(UTC),
                    "reason": reason,
                    "kill_switch": True,
                    "cancel_all": True,
                    "inventory": self.ledger.inventory,
                    "realized_pnl": self.ledger.realized_pnl,
                    "unrealized_pnl": self.ledger.unrealized_pnl,
                    "open_orders": len(self.order_coordinator.active) if self.order_coordinator else 0,
                },
            )
            if self.order_coordinator and (
                self.order_coordinator.active or self.mode == "demo_submit"
            ):
                try:
                    await self.order_coordinator.cancel_all(reason=f"kill switch: {reason}")
                    remaining = await self._verify_no_open_orders()
                    if remaining:
                        self.reporter.record(
                            "risk_events",
                            {
                                "event_time": datetime.now(UTC),
                                "reason": "open orders remain after kill-switch cancel-all",
                                "kill_switch": True,
                                "cancel_all": True,
                                "open_orders": len(remaining),
                            },
                        )
                except Exception:
                    pass
            if decision and decision.kill_switch:
                self._stop.set()

    async def _reconcile(self, *, reason: str, kill_on_mismatch: bool = True) -> dict[str, Any]:
        if self.mode == "live_dry_run" or not self.instrument:
            return {
                "status": "dry_run_local",
                "reason": reason,
                "open_orders": [order.__dict__ for order in self.order_coordinator.active.values()] if self.order_coordinator else [],
                "positions": [{"symbol": self.symbol, "size": self.ledger.inventory}],
            }
        open_orders, order_history, executions, positions, wallet = await asyncio.gather(
            asyncio.to_thread(self.rest.get_open_orders, category=self.category, symbol=self.symbol),
            asyncio.to_thread(self.rest.get_order_history, category=self.category, symbol=self.symbol),
            asyncio.to_thread(self.rest.get_recent_executions, category=self.category, symbol=self.symbol),
            asyncio.to_thread(self.rest.get_positions, category=self.category, symbol=self.symbol),
            asyncio.to_thread(
                self.rest.get_wallet_balance,
                account_type=str(_section(self.config, "execution").get("account_type", "UNIFIED")),
            ),
        )
        local_links = {order.order_link_id for order in self.order_coordinator.active.values()} if self.order_coordinator else set()
        unknown = [row for row in open_orders if row.get("orderLinkId") not in local_links]
        remote_links = {str(row.get("orderLinkId", "")) for row in open_orders}
        missing = sorted(local_links - remote_links)
        for row in executions:
            message = {"topic": "execution.linear", "creationTime": int(time.time() * 1_000), "data": [row]}
            for execution in parse_execution_message(
                message,
                receive_time_ms=int(time.time() * 1_000),
                clock_offset_ms=self._clock_offset_ms,
            ):
                await self._on_execution(execution)
        position_mismatch = self._position_mismatch(positions)
        mismatch = bool(unknown or missing or position_mismatch)
        incident = {
            "status": "mismatch" if mismatch else "ok",
            "reason": reason,
            "unknown_open_orders": unknown,
            "missing_local_orders": missing,
            "position_mismatch": position_mismatch,
            "open_orders": open_orders,
            "order_history": order_history,
            "positions": positions,
            "wallet": wallet.get("result", {}),
            "recent_execution_count": len(executions),
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if mismatch:
            self._repair_position(positions)
            if kill_on_mismatch:
                await self._kill_switch("order or position reconciliation mismatch")
        return incident

    async def _verify_no_open_orders(
        self, *, timeout_seconds: float = 5.0
    ) -> list[Mapping[str, Any]]:
        if self.mode == "live_dry_run":
            return (
                [order.__dict__ for order in self.order_coordinator.active.values()]
                if self.order_coordinator
                else []
            )
        deadline = time.monotonic() + timeout_seconds
        rows: list[Mapping[str, Any]] = []
        while True:
            rows = await asyncio.to_thread(
                self.rest.get_open_orders,
                category=self.category,
                symbol=self.symbol,
            )
            if not rows or time.monotonic() >= deadline:
                return rows
            await asyncio.sleep(0.25)

    async def _rotate_window(self) -> None:
        self._record_account_timeseries(source="reporting_boundary")
        if self.order_coordinator:
            # Pause new submissions by completing reconciliation before the next quote cycle.
            for side, order in list(self.order_coordinator.active.items()):
                age_ms = (time.monotonic() - order.created_monotonic) * 1_000.0
                if age_ms >= self.order_coordinator.maximum_quote_age_ms:
                    await self.order_coordinator.cancel(side, reason="stale at reporting boundary", force=True)
        if self.flatten_at_boundary and self.ledger.inventory != 0:
            await self._flatten_inventory_at_boundary()
        reconciliation = await self._reconcile(reason="reporting_boundary")
        open_orders = list(reconciliation.get("open_orders", []))
        positions = list(reconciliation.get("positions", []))
        if self._raw_writer:
            self._raw_writer.close()
        self.reporter.rotate(
            now=datetime.now(UTC),
            reconciliation=reconciliation,
            open_orders_at_end=open_orders,
            position_at_end=positions,
            inventory_carried_out=self.ledger.inventory,
        )
        if self._raw_writer:
            self._raw_writer.retarget(self.reporter.current_window_directory)
        self._windows_written += 1

    async def _flatten_inventory_at_boundary(self) -> None:
        if not self.order_coordinator or not self.instrument or not self.public:
            raise RuntimeError("cannot flatten before live components are initialized.")
        await self.order_coordinator.cancel_all(reason="flatten at reporting boundary")
        inventory = self.ledger.inventory
        if inventory == 0:
            return
        side = "Sell" if inventory > 0 else "Buy"
        quantity = self.instrument.round_quantity(abs(Decimal(str(inventory))))
        if self.mode == "live_dry_run":
            price = (
                self.public.processor.book.best_bid
                if side == "Sell"
                else self.public.processor.book.best_ask
            )
            if price is None:
                raise RuntimeError("cannot simulate boundary flatten without a valid top of book.")
            now_ms = int(time.time() * 1_000)
            await self._on_execution(
                ExecutionUpdate(
                    exec_id=f"dry_flatten_{uuid.uuid4().hex[:10]}",
                    order_id=f"dry_flatten_{self.session_id}",
                    order_link_id=f"mm_{self.session_id}_u_1",
                    symbol=self.symbol,
                    side=side,
                    price=float(price),
                    quantity=float(quantity),
                    exec_time_ms=now_ms,
                    is_maker=False,
                    exec_fee=0.0,
                    fee_currency=self.instrument.settle_coin,
                    closed_size=float(quantity),
                    sequence=None,
                    receive_time_ms=now_ms,
                    execution_latency_ms=0.0,
                )
            )
            return
        order_link_id = f"mm_{self.session_id}_u_{int(time.time()) % 100000}"
        await asyncio.to_thread(
            self.rest.place_reduce_only_market_order,
            category=self.category,
            symbol=self.symbol,
            side=side,
            quantity=self.instrument.format_decimal(quantity),
            order_link_id=order_link_id,
        )
        deadline = time.monotonic() + 10.0
        tolerance = float(self.instrument.quantity_step) / 2
        while time.monotonic() < deadline and abs(self.ledger.inventory) > tolerance:
            await asyncio.sleep(0.1)
        if abs(self.ledger.inventory) > tolerance:
            reconciliation = await self._reconcile(
                reason="boundary_flatten_timeout", kill_on_mismatch=False
            )
            if abs(_signed_position(list(reconciliation.get("positions", [])), self.symbol)) > tolerance:
                await self._kill_switch("boundary emergency unwind did not flatten inventory")
                raise RuntimeError("boundary emergency unwind did not flatten inventory.")

    def _record_api_latency(self, path: str, latency_ms: float) -> None:
        del path
        self.reporter.record_api_latency(latency_ms)

    def _record_api_error(self, error: Mapping[str, Any]) -> None:
        self.reporter.record("api_errors", error)
        self._consecutive_api_errors += 1
        if self._consecutive_api_errors >= self.maximum_consecutive_api_errors:
            self._fatal_async_reason = "too many consecutive Bybit API failures"

    def _record_api_success(self, path: str) -> None:
        del path
        self._consecutive_api_errors = 0

    def _position_mismatch(self, positions: list[Mapping[str, Any]]) -> bool:
        remote = _signed_position(positions, self.symbol)
        tolerance = float(self.instrument.quantity_step) / 2 if self.instrument else 1e-12
        return abs(remote - self.ledger.inventory) > tolerance

    def _repair_position(self, positions: list[Mapping[str, Any]]) -> None:
        row = next((row for row in positions if row.get("symbol") == self.symbol), None)
        if row is None:
            self.ledger.repair_from_position(inventory=0.0, average_price=0.0, unrealized_pnl=0.0)
            self._pending_position_mismatch = None
            return
        inventory = _signed_position([row], self.symbol)
        self.ledger.repair_from_position(
            inventory=inventory,
            average_price=float(row.get("avgPrice", row.get("entryPrice", 0)) or 0),
            unrealized_pnl=float(row.get("unrealisedPnl", 0) or 0),
        )
        self._pending_position_mismatch = None

    async def _check_pending_position_mismatch(self) -> None:
        if self._pending_position_mismatch is None:
            return
        update, detected_at = self._pending_position_mismatch
        if time.monotonic() - detected_at < 2.0:
            return
        self._pending_position_mismatch = None
        incident = await self._reconcile(
            reason="position_stream_mismatch", kill_on_mismatch=False
        )
        if incident.get("position_mismatch"):
            await self._kill_switch(
                f"position mismatch persisted after reconciliation at {update.updated_time_ms}"
            )

    def _record_account_timeseries(self, *, source: str) -> None:
        now = datetime.now(UTC)
        self.reporter.record(
            "inventory_timeseries", {"event_time": now, "inventory": self.ledger.inventory, "source": source}
        )
        self.reporter.record(
            "pnl_timeseries",
            {
                "event_time": now,
                "realized_pnl": self.ledger.realized_pnl,
                "unrealized_pnl": self.ledger.unrealized_pnl,
                "net_pnl": self.ledger.realized_pnl + self.ledger.unrealized_pnl - self.ledger.fees,
                "fees": self.ledger.fees,
                "inventory": self.ledger.inventory,
            },
        )

    def _validate_static_safety(self) -> None:
        execution = _section(self.config, "execution")
        if execution.get("environment") != "demo" or execution.get("venue") != "bybit":
            raise RuntimeError("execution environment/venue must be demo/bybit.")
        if self.category != "linear":
            raise RuntimeError("only Bybit category=linear is supported.")
        require_demo_execution_environment()
        configured_mode = str(execution.get("mode", "live_dry_run"))
        if configured_mode != self.mode:
            raise RuntimeError("CLI mode must exactly match execution.mode in config.")
        allow = execution.get("allow_order_submission") is True
        if self.mode == "demo_submit" and not allow:
            raise RuntimeError("demo_submit requires execution.allow_order_submission: true.")
        if self.mode == "live_dry_run" and allow:
            raise RuntimeError("live_dry_run requires execution.allow_order_submission: false.")


def _section(mapping: Mapping[str, Any], name: str) -> dict[str, Any]:
    value = mapping.get(name, {})
    if not isinstance(value, Mapping):
        raise ValueError(f"config section {name!r} must be a mapping.")
    return dict(value)


def _iso_ms(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1_000, tz=UTC).isoformat()


def _signed_position(positions: list[Mapping[str, Any]], symbol: str) -> float:
    total = 0.0
    for row in positions:
        if row.get("symbol") != symbol:
            continue
        size = float(row.get("size", 0) or 0)
        side = str(row.get("side", "")).lower()
        total += size if side == "buy" else -size if side == "sell" else 0.0
    return total


__all__ = [
    "ActiveOrder",
    "BybitLiveMarketMakingEngine",
    "ExecutionMode",
    "InventoryLedger",
    "OrderCoordinator",
]
