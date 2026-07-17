from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import math
from typing import Literal, Mapping

from src.market_data.order_book import LocalOrderBook
from src.market_making.quote_generator import QuoteDecision


OrderSide = Literal["buy", "sell"]
HedgeOrderType = Literal["ioc", "market", "passive"]


@dataclass(frozen=True)
class HedgeInstruction:
    """Concrete fill-contingent hedge request produced by a research strategy."""

    symbol: str
    side: OrderSide
    quantity: float
    reference_price: float
    order_type: HedgeOrderType = "ioc"
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("hedge symbol must be non-empty.")
        if self.side not in {"buy", "sell"}:
            raise ValueError("hedge side must be buy or sell.")
        if not math.isfinite(float(self.quantity)) or self.quantity <= 0.0:
            raise ValueError("hedge quantity must be finite and > 0.")
        if not math.isfinite(float(self.reference_price)) or self.reference_price <= 0.0:
            raise ValueError("hedge reference_price must be finite and > 0.")
        if self.order_type not in {"ioc", "market", "passive"}:
            raise ValueError("unsupported hedge order type.")


@dataclass(frozen=True)
class HedgeTemplate:
    """
    Template converted to a concrete hedge only after a quote fill.

    `quantity_per_fill_unit` scales with filled base quantity. The optional
    `quantity_per_fill_notional` scales with filled quantity times fill price,
    which is useful for ratio crosses such as ETH/BTC.
    """

    trigger_side: OrderSide
    symbol: str
    side: OrderSide
    reference_price: float
    quantity_per_fill_unit: float = 0.0
    quantity_per_fill_notional: float = 0.0
    order_type: HedgeOrderType = "ioc"
    reason: str = ""

    def __post_init__(self) -> None:
        if self.trigger_side not in {"buy", "sell"}:
            raise ValueError("trigger_side must be buy or sell.")
        if not self.symbol:
            raise ValueError("hedge template symbol must be non-empty.")
        if self.side not in {"buy", "sell"}:
            raise ValueError("hedge template side must be buy or sell.")
        for name, value in (
            ("reference_price", self.reference_price),
            ("quantity_per_fill_unit", self.quantity_per_fill_unit),
            ("quantity_per_fill_notional", self.quantity_per_fill_notional),
        ):
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite.")
        if self.reference_price <= 0.0:
            raise ValueError("reference_price must be > 0.")
        if self.quantity_per_fill_unit < 0.0 or self.quantity_per_fill_notional < 0.0:
            raise ValueError("hedge quantity multipliers must be >= 0.")
        if self.quantity_per_fill_unit == 0.0 and self.quantity_per_fill_notional == 0.0:
            raise ValueError("at least one hedge quantity multiplier must be > 0.")

    def instantiate(
        self,
        *,
        fill_side: OrderSide,
        fill_quantity: float,
        fill_price: float,
    ) -> HedgeInstruction | None:
        if fill_side != self.trigger_side:
            return None
        if not math.isfinite(float(fill_quantity)) or fill_quantity <= 0.0:
            raise ValueError("fill_quantity must be finite and > 0.")
        if not math.isfinite(float(fill_price)) or fill_price <= 0.0:
            raise ValueError("fill_price must be finite and > 0.")
        quantity = (
            float(fill_quantity) * self.quantity_per_fill_unit
            + float(fill_quantity) * float(fill_price) * self.quantity_per_fill_notional
        )
        if quantity <= 0.0:
            return None
        return HedgeInstruction(
            symbol=self.symbol,
            side=self.side,
            quantity=quantity,
            reference_price=self.reference_price,
            order_type=self.order_type,
            reason=self.reason,
        )


@dataclass(frozen=True)
class StrategyDecision:
    """Common output for all five research market-making strategies."""

    strategy_name: str
    quote: QuoteDecision
    expected_edge_bps: float
    hedge_templates: tuple[HedgeTemplate, ...] = ()
    diagnostics: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.strategy_name:
            raise ValueError("strategy_name must be non-empty.")
        if not math.isfinite(float(self.expected_edge_bps)):
            raise ValueError("expected_edge_bps must be finite.")

    def hedges_for_fill(
        self,
        *,
        fill_side: OrderSide,
        fill_quantity: float,
        fill_price: float,
    ) -> tuple[HedgeInstruction, ...]:
        """Materialize only the hedge legs associated with the filled quote side."""
        if fill_side not in {"buy", "sell"}:
            raise ValueError("fill_side must be buy or sell.")
        hedges = (
            template.instantiate(
                fill_side=fill_side,
                fill_quantity=fill_quantity,
                fill_price=fill_price,
            )
            for template in self.hedge_templates
        )
        return tuple(hedge for hedge in hedges if hedge is not None)


@dataclass(frozen=True)
class ExternalFairQuoteConfig:
    """Constraints for post-only quotes centered on an externally computed fair value."""

    spread_bps: float
    order_size: float
    max_inventory: float
    tick_size: float
    lot_size: float
    inventory_skew_strength: float = 0.5
    min_order_size: float = 0.0
    min_notional: float = 0.0

    def __post_init__(self) -> None:
        for name, value in (
            ("spread_bps", self.spread_bps),
            ("order_size", self.order_size),
            ("max_inventory", self.max_inventory),
            ("tick_size", self.tick_size),
            ("lot_size", self.lot_size),
        ):
            if not math.isfinite(float(value)) or value <= 0.0:
                raise ValueError(f"{name} must be finite and > 0.")
        for name, value in (
            ("inventory_skew_strength", self.inventory_skew_strength),
            ("min_order_size", self.min_order_size),
            ("min_notional", self.min_notional),
        ):
            if not math.isfinite(float(value)) or value < 0.0:
                raise ValueError(f"{name} must be finite and >= 0.")


def quote_around_external_fair(
    *,
    book: LocalOrderBook,
    fair_price: float,
    inventory: float,
    config: ExternalFairQuoteConfig,
) -> QuoteDecision:
    """Create a passive quote around a synchronized external fair value."""
    if not math.isfinite(float(fair_price)) or fair_price <= 0.0:
        raise ValueError("fair_price must be finite and > 0.")
    if not math.isfinite(float(inventory)):
        raise ValueError("inventory must be finite.")
    if book.best_bid is None or book.best_ask is None:
        return rejected_quote(
            book=book,
            fair_price=fair_price,
            spread_bps=config.spread_bps,
            inventory_ratio=normalized_inventory(inventory, config.max_inventory),
            reason="incomplete order book",
        )

    inventory_ratio = normalized_inventory(inventory, config.max_inventory)
    half_spread = fair_price * config.spread_bps / 20_000.0
    reservation_shift = (
        -inventory_ratio
        * half_spread
        * config.inventory_skew_strength
    )
    reservation_price = fair_price + reservation_shift
    desired_bid = _round_down(reservation_price - half_spread, config.tick_size)
    desired_ask = _round_up(reservation_price + half_spread, config.tick_size)

    passive_bid_ceiling = _round_down(float(book.best_ask) - config.tick_size, config.tick_size)
    passive_ask_floor = _round_up(float(book.best_bid) + config.tick_size, config.tick_size)
    bid_price = min(desired_bid, passive_bid_ceiling)
    ask_price = max(desired_ask, passive_ask_floor)
    size = _round_down(config.order_size, config.lot_size)
    quoted_spread_bps = _spread_bps(bid_price, ask_price)

    if (
        bid_price <= 0.0
        or ask_price <= 0.0
        or bid_price >= ask_price
        or size < max(config.min_order_size, config.lot_size)
    ):
        return rejected_quote(
            book=book,
            fair_price=fair_price,
            spread_bps=quoted_spread_bps,
            inventory_ratio=inventory_ratio,
            reason="invalid external-fair quote",
        )

    bid_valid = bid_price * size >= config.min_notional
    ask_valid = ask_price * size >= config.min_notional
    if not bid_valid and not ask_valid:
        return rejected_quote(
            book=book,
            fair_price=fair_price,
            spread_bps=quoted_spread_bps,
            inventory_ratio=inventory_ratio,
            reason="quote notional below minimum",
        )
    return QuoteDecision(
        symbol=book.symbol,
        bid_price=bid_price if bid_valid else None,
        ask_price=ask_price if ask_valid else None,
        bid_size=size if bid_valid else 0.0,
        ask_size=size if ask_valid else 0.0,
        fair_price=fair_price,
        spread_bps=quoted_spread_bps,
        inventory_ratio=inventory_ratio,
        should_quote=True,
        reason="ok",
        timestamp=_book_timestamp(book),
    )


def select_quote_sides(
    quote: QuoteDecision,
    *,
    allow_buy: bool,
    allow_sell: bool,
    reason: str,
) -> QuoteDecision:
    """Return a quote with only the explicitly allowed passive sides."""
    bid_enabled = bool(allow_buy and quote.bid_price is not None and quote.bid_size > 0.0)
    ask_enabled = bool(allow_sell and quote.ask_price is not None and quote.ask_size > 0.0)
    if not bid_enabled and not ask_enabled:
        return QuoteDecision(
            symbol=quote.symbol,
            bid_price=None,
            ask_price=None,
            bid_size=0.0,
            ask_size=0.0,
            fair_price=quote.fair_price,
            spread_bps=quote.spread_bps,
            inventory_ratio=quote.inventory_ratio,
            should_quote=False,
            reason=reason,
            timestamp=quote.timestamp,
        )
    return QuoteDecision(
        symbol=quote.symbol,
        bid_price=quote.bid_price if bid_enabled else None,
        ask_price=quote.ask_price if ask_enabled else None,
        bid_size=quote.bid_size if bid_enabled else 0.0,
        ask_size=quote.ask_size if ask_enabled else 0.0,
        fair_price=quote.fair_price,
        spread_bps=quote.spread_bps,
        inventory_ratio=quote.inventory_ratio,
        should_quote=True,
        reason="ok",
        timestamp=quote.timestamp,
    )


def rejected_quote(
    *,
    book: LocalOrderBook,
    fair_price: float,
    spread_bps: float,
    inventory_ratio: float,
    reason: str,
) -> QuoteDecision:
    return QuoteDecision(
        symbol=book.symbol,
        bid_price=None,
        ask_price=None,
        bid_size=0.0,
        ask_size=0.0,
        fair_price=float(fair_price),
        spread_bps=max(0.0, float(spread_bps)),
        inventory_ratio=float(inventory_ratio),
        should_quote=False,
        reason=reason,
        timestamp=_book_timestamp(book),
    )


def books_are_synchronized(
    books: tuple[LocalOrderBook, ...],
    *,
    max_time_skew_ms: int,
) -> bool:
    """Fail closed when any required book timestamp is missing or too far apart."""
    if max_time_skew_ms < 0:
        raise ValueError("max_time_skew_ms must be >= 0.")
    timestamps = [book.timestamp for book in books]
    if any(timestamp is None for timestamp in timestamps):
        return False
    aware_timestamps = []
    for timestamp in timestamps:
        assert timestamp is not None
        aware_timestamps.append(
            timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)
        )
    skew_ms = (max(aware_timestamps) - min(aware_timestamps)).total_seconds() * 1000.0
    return math.isfinite(skew_ms) and 0.0 <= skew_ms <= max_time_skew_ms


def normalized_inventory(inventory: float, max_inventory: float) -> float:
    if not math.isfinite(float(inventory)):
        raise ValueError("inventory must be finite.")
    if not math.isfinite(float(max_inventory)) or max_inventory <= 0.0:
        raise ValueError("max_inventory must be finite and > 0.")
    return min(max(float(inventory) / float(max_inventory), -1.0), 1.0)


def side_edge_bps(
    *,
    side: OrderSide,
    price: float | None,
    fair_price: float,
    cost_bps: float,
) -> float:
    if price is None:
        return float("-inf")
    gross = (
        (fair_price - float(price)) / fair_price * 10_000.0
        if side == "buy"
        else (float(price) - fair_price) / fair_price * 10_000.0
    )
    return gross - float(cost_bps)


def active_side_count(quote: QuoteDecision) -> int:
    return int(quote.bid_price is not None and quote.bid_size > 0.0) + int(
        quote.ask_price is not None and quote.ask_size > 0.0
    )


def _spread_bps(bid_price: float, ask_price: float) -> float:
    mid = (bid_price + ask_price) / 2.0
    if mid <= 0.0:
        return 0.0
    return max(0.0, (ask_price - bid_price) / mid * 10_000.0)


def _round_down(value: float, step: float) -> float:
    units = (Decimal(str(value)) / Decimal(str(step))).to_integral_value(rounding=ROUND_FLOOR)
    return float(units * Decimal(str(step)))


def _round_up(value: float, step: float) -> float:
    units = (Decimal(str(value)) / Decimal(str(step))).to_integral_value(rounding=ROUND_CEILING)
    return float(units * Decimal(str(step)))


def _book_timestamp(book: LocalOrderBook) -> datetime:
    timestamp = book.timestamp
    if timestamp is None:
        return datetime.now(timezone.utc)
    return timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)


__all__ = [
    "ExternalFairQuoteConfig",
    "HedgeInstruction",
    "HedgeTemplate",
    "OrderSide",
    "StrategyDecision",
    "active_side_count",
    "books_are_synchronized",
    "normalized_inventory",
    "quote_around_external_fair",
    "rejected_quote",
    "select_quote_sides",
    "side_edge_bps",
]
