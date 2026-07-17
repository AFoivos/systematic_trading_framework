from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math

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
        for name, value in (
            ("max_inventory", limits.max_inventory),
            ("max_position_value", limits.max_position_value),
            ("max_daily_loss", limits.max_daily_loss),
            ("max_order_size", limits.max_order_size),
            ("max_allowed_spread_bps", limits.max_allowed_spread_bps),
        ):
            if not math.isfinite(float(value)) or float(value) <= 0.0:
                raise ValueError(f"{name} must be finite and > 0.")
        if limits.max_open_orders < 0:
            raise ValueError("max_open_orders must be >= 0.")
        if limits.stale_order_book_ms < 0:
            raise ValueError("stale_order_book_ms must be >= 0.")
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
        if quote.symbol != book.symbol:
            return RiskDecision(False, reason="quote symbol does not match order book", cancel_all=False)
        if not self._state_is_finite(state):
            return self.trigger_kill_switch("invalid non-finite risk state")
        if self.limits.kill_on_websocket_disconnect and not state.websocket_connected:
            return self.trigger_kill_switch("websocket disconnected")
        if self.limits.kill_on_stale_order_book and self._is_stale(book, state.now):
            return self.trigger_kill_switch("stale order book")
        if abs(state.inventory) > self.limits.max_inventory:
            return self.trigger_kill_switch("max inventory exceeded")
        book_mid = book.mid_price
        if book_mid is not None and abs(state.inventory) * book_mid > self.limits.max_position_value:
            return self.trigger_kill_switch("max position value exceeded")
        total_pnl = state.realized_pnl + state.unrealized_pnl
        if total_pnl <= -abs(self.limits.max_daily_loss):
            return self.trigger_kill_switch("max daily loss exceeded")
        book_spread_bps = book.spread_bps
        if (
            self.limits.kill_on_spread_widening
            and book_spread_bps is not None
            and book_spread_bps > self.limits.max_allowed_spread_bps
        ):
            return self.trigger_kill_switch("extreme order book spread")
        if not quote.should_quote:
            return RiskDecision(False, reason=quote.reason)
        if not self._quote_is_valid(quote):
            return RiskDecision(False, reason="invalid quote values", cancel_all=False)
        worst_inventory = self._worst_case_inventory(quote=quote, inventory=state.inventory)
        if abs(worst_inventory) > self.limits.max_inventory:
            return RiskDecision(False, reason="worst-case inventory would exceed limit", cancel_all=False)
        if state.open_orders > self.limits.max_open_orders:
            return RiskDecision(False, reason="max open orders exceeded", cancel_all=False)
        if quote.bid_size > self.limits.max_order_size or quote.ask_size > self.limits.max_order_size:
            return RiskDecision(False, reason="max order size exceeded")
        worst_notional = max(abs(worst_inventory) * quote.fair_price, 0.0)
        if worst_notional > self.limits.max_position_value:
            return RiskDecision(False, reason="worst-case position value would exceed limit", cancel_all=False)
        return RiskDecision(True)

    def _is_stale(self, book: LocalOrderBook, now: datetime) -> bool:
        if book.timestamp is None:
            return True
        try:
            age_ms = (now - book.timestamp).total_seconds() * 1000.0
        except (TypeError, ValueError):
            return True
        return not math.isfinite(age_ms) or age_ms < 0.0 or age_ms > self.limits.stale_order_book_ms

    @staticmethod
    def _state_is_finite(state: RiskState) -> bool:
        return (
            all(
                math.isfinite(float(value))
                for value in (state.inventory, state.realized_pnl, state.unrealized_pnl)
            )
            and isinstance(state.open_orders, int)
            and not isinstance(state.open_orders, bool)
            and state.open_orders >= 0
        )

    @staticmethod
    def _quote_is_valid(quote: QuoteDecision) -> bool:
        if not math.isfinite(float(quote.fair_price)) or quote.fair_price <= 0.0:
            return False
        if not math.isfinite(float(quote.spread_bps)) or quote.spread_bps < 0.0:
            return False
        for price, size in (
            (quote.bid_price, quote.bid_size),
            (quote.ask_price, quote.ask_size),
        ):
            if not math.isfinite(float(size)) or size < 0.0:
                return False
            if price is None:
                if size != 0.0:
                    return False
            elif not math.isfinite(float(price)) or price <= 0.0 or size <= 0.0:
                return False
        if quote.bid_price is not None and quote.ask_price is not None:
            if quote.bid_price >= quote.ask_price:
                return False
        return quote.bid_price is not None or quote.ask_price is not None

    @staticmethod
    def _worst_case_inventory(*, quote: QuoteDecision, inventory: float) -> float:
        candidates = [float(inventory)]
        if quote.bid_price is not None and quote.bid_size > 0:
            candidates.append(float(inventory) + quote.bid_size)
        if quote.ask_price is not None and quote.ask_size > 0:
            candidates.append(float(inventory) - quote.ask_size)
        return max(candidates, key=abs)


__all__ = ["RiskDecision", "RiskEngine", "RiskLimits", "RiskState"]
