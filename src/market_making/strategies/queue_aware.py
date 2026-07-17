from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import math
from typing import Literal

from src.market_data.order_book import LocalOrderBook
from src.market_making.fair_price import microprice
from src.market_making.quote_generator import QuoteDecision

from .common import StrategyDecision, normalized_inventory


PlacementMode = Literal["join", "improve"]
OrderSide = Literal["buy", "sell"]


@dataclass(frozen=True)
class QueueState:
    """
    Causal L2 queue estimates available at decision time.

    Aggressive quantities are expected near-horizon quantities inferred from past
    flow, not realized future trades. Cancellation fractions must likewise be
    estimated only from information available before the quote decision.
    """

    bid_queue_ahead: float
    ask_queue_ahead: float
    expected_aggressive_sell_qty: float
    expected_aggressive_buy_qty: float
    bid_cancel_fraction: float = 0.0
    ask_cancel_fraction: float = 0.0
    expected_buy_adverse_markout_bps: float = 0.0
    expected_sell_adverse_markout_bps: float = 0.0

    def __post_init__(self) -> None:
        for name, value in (
            ("bid_queue_ahead", self.bid_queue_ahead),
            ("ask_queue_ahead", self.ask_queue_ahead),
            ("expected_aggressive_sell_qty", self.expected_aggressive_sell_qty),
            ("expected_aggressive_buy_qty", self.expected_aggressive_buy_qty),
            ("expected_buy_adverse_markout_bps", self.expected_buy_adverse_markout_bps),
            ("expected_sell_adverse_markout_bps", self.expected_sell_adverse_markout_bps),
        ):
            if not math.isfinite(float(value)) or value < 0.0:
                raise ValueError(f"{name} must be finite and >= 0.")
        for name, value in (
            ("bid_cancel_fraction", self.bid_cancel_fraction),
            ("ask_cancel_fraction", self.ask_cancel_fraction),
        ):
            if not math.isfinite(float(value)) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and in [0, 1].")


@dataclass(frozen=True)
class QueueAwareStrategyConfig:
    order_size: float
    max_inventory: float
    tick_size: float
    lot_size: float
    maker_fee_bps: float = 0.0
    min_expected_edge_bps: float = 0.0
    replacement_cost_bps: float = 0.0
    inventory_penalty_bps_per_unit: float = 0.0
    min_notional: float = 0.0
    allow_improve: bool = True

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.maker_fee_bps)):
            raise ValueError("maker_fee_bps must be finite.")
        for name, value in (
            ("order_size", self.order_size),
            ("max_inventory", self.max_inventory),
            ("tick_size", self.tick_size),
            ("lot_size", self.lot_size),
        ):
            if not math.isfinite(float(value)) or value <= 0.0:
                raise ValueError(f"{name} must be finite and > 0.")
        for name, value in (
            ("min_expected_edge_bps", self.min_expected_edge_bps),
            ("replacement_cost_bps", self.replacement_cost_bps),
            ("inventory_penalty_bps_per_unit", self.inventory_penalty_bps_per_unit),
            ("min_notional", self.min_notional),
        ):
            if not math.isfinite(float(value)) or value < 0.0:
                raise ValueError(f"{name} must be finite and >= 0.")


@dataclass(frozen=True)
class ConservativeQueuePosition:
    """
    Standalone deterministic queue tracker with explicit partial fills.

    Only observed trade quantity and explicitly attributed cancellations reduce
    queue ahead. It intentionally makes no hidden inference about cancellations.
    """

    order_quantity: float
    queue_ahead: float
    remaining_quantity: float | None = None
    filled_quantity: float = 0.0

    def __post_init__(self) -> None:
        remaining = self.order_quantity if self.remaining_quantity is None else self.remaining_quantity
        for name, value in (
            ("order_quantity", self.order_quantity),
            ("queue_ahead", self.queue_ahead),
            ("remaining_quantity", remaining),
            ("filled_quantity", self.filled_quantity),
        ):
            if not math.isfinite(float(value)) or value < 0.0:
                raise ValueError(f"{name} must be finite and >= 0.")
        if self.order_quantity <= 0.0:
            raise ValueError("order_quantity must be > 0.")
        if remaining + self.filled_quantity > self.order_quantity + 1e-12:
            raise ValueError("remaining plus filled quantity cannot exceed order quantity.")
        object.__setattr__(self, "remaining_quantity", float(remaining))

    def advance(
        self,
        *,
        traded_quantity: float,
        cancelled_ahead: float = 0.0,
    ) -> tuple[ConservativeQueuePosition, float]:
        """Apply one causal queue event and return the next state plus incremental fill."""
        for name, value in (
            ("traded_quantity", traded_quantity),
            ("cancelled_ahead", cancelled_ahead),
        ):
            if not math.isfinite(float(value)) or value < 0.0:
                raise ValueError(f"{name} must be finite and >= 0.")
        queue_after_cancel = max(0.0, self.queue_ahead - float(cancelled_ahead))
        queue_consumed = min(queue_after_cancel, float(traded_quantity))
        queue_remaining = queue_after_cancel - queue_consumed
        residual_trade = max(0.0, float(traded_quantity) - queue_consumed)
        assert self.remaining_quantity is not None
        fill_delta = min(self.remaining_quantity, residual_trade)
        next_remaining = self.remaining_quantity - fill_delta
        return (
            ConservativeQueuePosition(
                order_quantity=self.order_quantity,
                queue_ahead=queue_remaining,
                remaining_quantity=next_remaining,
                filled_quantity=self.filled_quantity + fill_delta,
            ),
            fill_delta,
        )


@dataclass(frozen=True)
class _QueueCandidate:
    side: OrderSide
    mode: PlacementMode
    price: float
    fill_probability: float
    per_fill_edge_bps: float
    expected_edge_bps: float


class QueueAwareJoinImproveStrategy:
    """Select join or one-tick improve using queue-adjusted expected edge."""

    name = "queue_aware_join_improve"

    def __init__(self, config: QueueAwareStrategyConfig) -> None:
        self.config = config

    def decide(
        self,
        *,
        book: LocalOrderBook,
        inventory: float,
        queue_state: QueueState,
    ) -> StrategyDecision:
        if book.best_bid is None or book.best_ask is None:
            raise ValueError("queue-aware quoting requires a complete top of book.")
        fair_price = microprice(book)
        size = self._round_down(self.config.order_size, self.config.lot_size)
        inventory_ratio = normalized_inventory(inventory, self.config.max_inventory)
        buy_candidate = self._best_candidate(
            side="buy",
            book=book,
            fair_price=fair_price,
            inventory=inventory,
            queue_state=queue_state,
            size=size,
        )
        sell_candidate = self._best_candidate(
            side="sell",
            book=book,
            fair_price=fair_price,
            inventory=inventory,
            queue_state=queue_state,
            size=size,
        )
        allow_buy = (
            buy_candidate is not None
            and buy_candidate.expected_edge_bps >= self.config.min_expected_edge_bps
            and buy_candidate.price * size >= self.config.min_notional
        )
        allow_sell = (
            sell_candidate is not None
            and sell_candidate.expected_edge_bps >= self.config.min_expected_edge_bps
            and sell_candidate.price * size >= self.config.min_notional
        )
        bid_price = buy_candidate.price if allow_buy and buy_candidate is not None else None
        ask_price = sell_candidate.price if allow_sell and sell_candidate is not None else None
        if bid_price is not None and ask_price is not None and bid_price >= ask_price:
            if buy_candidate is not None and sell_candidate is not None:
                if buy_candidate.expected_edge_bps >= sell_candidate.expected_edge_bps:
                    ask_price = None
                    allow_sell = False
                else:
                    bid_price = None
                    allow_buy = False
        quoted_spread_bps = self._spread_bps(bid_price, ask_price, fair_price)
        should_quote = allow_buy or allow_sell
        quote = QuoteDecision(
            symbol=book.symbol,
            bid_price=bid_price,
            ask_price=ask_price,
            bid_size=size if allow_buy else 0.0,
            ask_size=size if allow_sell else 0.0,
            fair_price=fair_price,
            spread_bps=quoted_spread_bps,
            inventory_ratio=inventory_ratio,
            should_quote=should_quote,
            reason="ok" if should_quote else "no queue candidate has positive expected edge",
            timestamp=self._book_timestamp(book),
        )
        active_edges = [
            candidate.expected_edge_bps
            for candidate, allowed in (
                (buy_candidate, allow_buy),
                (sell_candidate, allow_sell),
            )
            if allowed and candidate is not None
        ]
        expected_edge = sum(active_edges) / len(active_edges) if active_edges else min(
            buy_candidate.expected_edge_bps if buy_candidate is not None else 0.0,
            sell_candidate.expected_edge_bps if sell_candidate is not None else 0.0,
        )
        return StrategyDecision(
            strategy_name=self.name,
            quote=quote,
            expected_edge_bps=expected_edge,
            diagnostics={
                "buy_mode": buy_candidate.mode if buy_candidate is not None else None,
                "sell_mode": sell_candidate.mode if sell_candidate is not None else None,
                "buy_fill_probability": (
                    buy_candidate.fill_probability if buy_candidate is not None else 0.0
                ),
                "sell_fill_probability": (
                    sell_candidate.fill_probability if sell_candidate is not None else 0.0
                ),
                "buy_expected_edge_bps": (
                    buy_candidate.expected_edge_bps if buy_candidate is not None else None
                ),
                "sell_expected_edge_bps": (
                    sell_candidate.expected_edge_bps if sell_candidate is not None else None
                ),
                "inventory_ratio": inventory_ratio,
            },
        )

    def _best_candidate(
        self,
        *,
        side: OrderSide,
        book: LocalOrderBook,
        fair_price: float,
        inventory: float,
        queue_state: QueueState,
        size: float,
    ) -> _QueueCandidate | None:
        candidates = [
            self._candidate(
                side=side,
                mode="join",
                book=book,
                fair_price=fair_price,
                inventory=inventory,
                queue_state=queue_state,
                size=size,
            )
        ]
        if self.config.allow_improve and self._can_improve(book):
            candidates.append(
                self._candidate(
                    side=side,
                    mode="improve",
                    book=book,
                    fair_price=fair_price,
                    inventory=inventory,
                    queue_state=queue_state,
                    size=size,
                )
            )
        valid = [candidate for candidate in candidates if candidate is not None]
        return max(valid, key=lambda candidate: candidate.expected_edge_bps) if valid else None

    def _candidate(
        self,
        *,
        side: OrderSide,
        mode: PlacementMode,
        book: LocalOrderBook,
        fair_price: float,
        inventory: float,
        queue_state: QueueState,
        size: float,
    ) -> _QueueCandidate | None:
        assert book.best_bid is not None and book.best_ask is not None
        if side == "buy":
            price = (
                float(book.best_bid)
                if mode == "join"
                else self._round_down(float(book.best_bid) + self.config.tick_size, self.config.tick_size)
            )
            if price >= float(book.best_ask):
                return None
            queue_ahead = queue_state.bid_queue_ahead if mode == "join" else 0.0
            aggressive_qty = queue_state.expected_aggressive_sell_qty
            cancel_fraction = queue_state.bid_cancel_fraction if mode == "join" else 0.0
            adverse_markout = queue_state.expected_buy_adverse_markout_bps
            post_inventory = inventory + size
            gross_edge = (fair_price - price) / fair_price * 10_000.0
        else:
            price = (
                float(book.best_ask)
                if mode == "join"
                else self._round_up(float(book.best_ask) - self.config.tick_size, self.config.tick_size)
            )
            if price <= float(book.best_bid):
                return None
            queue_ahead = queue_state.ask_queue_ahead if mode == "join" else 0.0
            aggressive_qty = queue_state.expected_aggressive_buy_qty
            cancel_fraction = queue_state.ask_cancel_fraction if mode == "join" else 0.0
            adverse_markout = queue_state.expected_sell_adverse_markout_bps
            post_inventory = inventory - size
            gross_edge = (price - fair_price) / fair_price * 10_000.0
        fill_probability = self._fill_probability(
            queue_ahead=queue_ahead,
            expected_aggressive_qty=aggressive_qty,
            cancel_fraction=cancel_fraction,
            order_size=size,
        )
        inventory_penalty = self._incremental_inventory_penalty(
            inventory=inventory,
            post_inventory=post_inventory,
        )
        per_fill_edge = (
            gross_edge
            - self.config.maker_fee_bps
            - adverse_markout
            - inventory_penalty
        )
        expected_edge = (
            fill_probability * per_fill_edge
            - self.config.replacement_cost_bps
        )
        return _QueueCandidate(
            side=side,
            mode=mode,
            price=price,
            fill_probability=fill_probability,
            per_fill_edge_bps=per_fill_edge,
            expected_edge_bps=expected_edge,
        )

    def _incremental_inventory_penalty(
        self,
        *,
        inventory: float,
        post_inventory: float,
    ) -> float:
        before = abs(normalized_inventory(inventory, self.config.max_inventory))
        after = abs(normalized_inventory(post_inventory, self.config.max_inventory))
        return max(0.0, after - before) * self.config.inventory_penalty_bps_per_unit

    @staticmethod
    def _fill_probability(
        *,
        queue_ahead: float,
        expected_aggressive_qty: float,
        cancel_fraction: float,
        order_size: float,
    ) -> float:
        progress = expected_aggressive_qty + cancel_fraction * queue_ahead
        required_progress = queue_ahead + order_size
        if required_progress <= 0.0:
            return 0.0
        return min(max(progress / required_progress, 0.0), 1.0)

    def _can_improve(self, book: LocalOrderBook) -> bool:
        assert book.best_bid is not None and book.best_ask is not None
        return float(book.best_bid) + self.config.tick_size < float(book.best_ask)

    @staticmethod
    def _spread_bps(
        bid_price: float | None,
        ask_price: float | None,
        fair_price: float,
    ) -> float:
        if bid_price is not None and ask_price is not None:
            quote_mid = (bid_price + ask_price) / 2.0
            return (ask_price - bid_price) / quote_mid * 10_000.0
        if bid_price is not None:
            return max(0.0, (fair_price - bid_price) / fair_price * 20_000.0)
        if ask_price is not None:
            return max(0.0, (ask_price - fair_price) / fair_price * 20_000.0)
        return 0.0

    @staticmethod
    def _round_down(value: float, step: float) -> float:
        units = (Decimal(str(value)) / Decimal(str(step))).to_integral_value(
            rounding=ROUND_FLOOR
        )
        return float(units * Decimal(str(step)))

    @staticmethod
    def _round_up(value: float, step: float) -> float:
        units = (Decimal(str(value)) / Decimal(str(step))).to_integral_value(
            rounding=ROUND_CEILING
        )
        return float(units * Decimal(str(step)))

    @staticmethod
    def _book_timestamp(book: LocalOrderBook) -> datetime:
        timestamp = book.timestamp
        if timestamp is None:
            return datetime.now(timezone.utc)
        return timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)


__all__ = [
    "ConservativeQueuePosition",
    "QueueAwareJoinImproveStrategy",
    "QueueAwareStrategyConfig",
    "QueueState",
]
