from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .quote_generator import QuoteDecision
from src.market_data.order_book import LocalOrderBook


@dataclass(frozen=True)
class RiskLimits:
    """Central market-making risk limits."""

    max_inventory: float
    max_position_value: float
    max_daily_loss: float
    max_open_orders: int
    max_order_size: float
    max_allowed_spread_bps: float
    stale_order_book_ms: int
    kill_on_websocket_disconnect: bool = True
    kill_on_stale_order_book: bool = True
    kill_on_spread_widening: bool = True


@dataclass(frozen=True)
class RiskState:
    """Current state required by risk checks."""

    inventory: float
    realized_pnl: float
    unrealized_pnl: float
    open_orders: int
    websocket_connected: bool = True
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class RiskDecision:
    """Risk-gate output for a candidate quote."""

    allowed: bool
    reason: str = "ok"
    cancel_all: bool = False
    kill_switch: bool = False


class RiskEngine:
    """Central risk gate; all order placement must pass through this object."""

    def __init__(self, limits: RiskLimits) -> None:
        if limits.max_inventory <= 0:
            raise ValueError("max_inventory must be > 0.")
        if limits.max_open_orders < 0:
            raise ValueError("max_open_orders must be >= 0.")
        self.limits = limits
        self.kill_switch_enabled = False
        self.kill_events: list[str] = []

    def trigger_kill_switch(self, reason: str) -> RiskDecision:
        """Permanently stop quoting until a new RiskEngine is created."""
        self.kill_switch_enabled = True
        self.kill_events.append(reason)
        return RiskDecision(False, reason=reason, cancel_all=True, kill_switch=True)

    def check_quote(self, *, quote: QuoteDecision, book: LocalOrderBook, state: RiskState) -> RiskDecision:
        """Validate a quote decision against hard limits."""
        if self.kill_switch_enabled:
            return RiskDecision(False, reason="kill switch active", cancel_all=True, kill_switch=True)
        if not quote.should_quote:
            return RiskDecision(False, reason=quote.reason)
        if self.limits.kill_on_websocket_disconnect and not state.websocket_connected:
            return self.trigger_kill_switch("websocket disconnected")
        if self.limits.kill_on_stale_order_book and self._is_stale(book, state.now):
            return self.trigger_kill_switch("stale order book")
        if abs(state.inventory) > self.limits.max_inventory:
            return self.trigger_kill_switch("max inventory exceeded")
        worst_inventory = self._worst_case_inventory(quote=quote, inventory=state.inventory)
        if abs(worst_inventory) > self.limits.max_inventory:
            return RiskDecision(False, reason="worst-case inventory would exceed limit", cancel_all=False)
        total_pnl = state.realized_pnl + state.unrealized_pnl
        if total_pnl <= -abs(self.limits.max_daily_loss):
            return self.trigger_kill_switch("max daily loss exceeded")
        if state.open_orders > self.limits.max_open_orders:
            return RiskDecision(False, reason="max open orders exceeded", cancel_all=False)
        if quote.bid_size > self.limits.max_order_size or quote.ask_size > self.limits.max_order_size:
            return RiskDecision(False, reason="max order size exceeded")
        notional = max(abs(state.inventory) * quote.fair_price, 0.0)
        if notional > self.limits.max_position_value:
            return self.trigger_kill_switch("max position value exceeded")
        worst_notional = max(abs(worst_inventory) * quote.fair_price, 0.0)
        if worst_notional > self.limits.max_position_value:
            return RiskDecision(False, reason="worst-case position value would exceed limit", cancel_all=False)
        book_spread_bps = book.spread_bps
        if (
            self.limits.kill_on_spread_widening
            and book_spread_bps is not None
            and book_spread_bps > self.limits.max_allowed_spread_bps
        ):
            return self.trigger_kill_switch("extreme order book spread")
        return RiskDecision(True)

    def _is_stale(self, book: LocalOrderBook, now: datetime) -> bool:
        if book.timestamp is None:
            return True
        age_ms = (now - book.timestamp).total_seconds() * 1000.0
        return age_ms > self.limits.stale_order_book_ms

    @staticmethod
    def _worst_case_inventory(*, quote: QuoteDecision, inventory: float) -> float:
        candidates = [float(inventory)]
        if quote.bid_price is not None and quote.bid_size > 0:
            candidates.append(float(inventory) + quote.bid_size)
        if quote.ask_price is not None and quote.ask_size > 0:
            candidates.append(float(inventory) - quote.ask_size)
        return max(candidates, key=abs)


__all__ = ["RiskDecision", "RiskEngine", "RiskLimits", "RiskState"]
