from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Literal


BookSide = Literal["bid", "ask"]


@dataclass(frozen=True)
class OrderBookLevel:
    """A single price level in the local order book."""

    price: float
    quantity: float


@dataclass(frozen=True)
class OrderBookSnapshot:
    """Serializable top-level view of a local order book."""

    symbol: str
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    timestamp: datetime
    sequence: int | None = None


class LocalOrderBook:
    """In-memory level-2 order book with deterministic validation semantics."""

    def __init__(self, symbol: str) -> None:
        if not symbol:
            raise ValueError("symbol must be non-empty.")
        self.symbol = symbol
        self._bids: dict[float, float] = {}
        self._asks: dict[float, float] = {}
        self.timestamp: datetime | None = None
        self.sequence: int | None = None

    @property
    def bids(self) -> list[OrderBookLevel]:
        """Return bids sorted from best to worst."""
        return [OrderBookLevel(price, qty) for price, qty in sorted(self._bids.items(), reverse=True)]

    @property
    def asks(self) -> list[OrderBookLevel]:
        """Return asks sorted from best to worst."""
        return [OrderBookLevel(price, qty) for price, qty in sorted(self._asks.items())]

    @property
    def best_bid(self) -> float | None:
        return max(self._bids) if self._bids else None

    @property
    def best_ask(self) -> float | None:
        return min(self._asks) if self._asks else None

    @property
    def mid_price(self) -> float | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / 2.0

    @property
    def spread(self) -> float | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid

    @property
    def spread_bps(self) -> float | None:
        mid = self.mid_price
        spread = self.spread
        if mid is None or spread is None or mid <= 0:
            return None
        return spread / mid * 10_000.0

    def apply_snapshot(
        self,
        *,
        bids: Iterable[tuple[float, float]],
        asks: Iterable[tuple[float, float]],
        timestamp: datetime | None = None,
        sequence: int | None = None,
    ) -> None:
        """Replace local state with a full depth snapshot."""
        self._bids = self._normalize_side(bids)
        self._asks = self._normalize_side(asks)
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.sequence = sequence
        self._validate_crossed_book()

    def apply_update(
        self,
        *,
        bids: Iterable[tuple[float, float]] = (),
        asks: Iterable[tuple[float, float]] = (),
        timestamp: datetime | None = None,
        sequence: int | None = None,
    ) -> None:
        """Apply incremental price-level updates; non-positive quantities remove levels."""
        if sequence is not None and self.sequence is not None and sequence < self.sequence:
            raise ValueError("sequence must be monotonic when provided.")
        self._apply_side_updates("bid", bids)
        self._apply_side_updates("ask", asks)
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.sequence = sequence if sequence is not None else self.sequence
        self._validate_crossed_book()

    def depth(self, levels: int) -> dict[str, list[OrderBookLevel]]:
        """Return top N levels on each side."""
        if levels <= 0:
            raise ValueError("levels must be > 0.")
        return {"bids": self.bids[:levels], "asks": self.asks[:levels]}

    def imbalance(self, levels: int = 1) -> float | None:
        """Return bid depth share in [0, 1] over the top N levels."""
        depth = self.depth(levels)
        bid_qty = sum(level.quantity for level in depth["bids"])
        ask_qty = sum(level.quantity for level in depth["asks"])
        total = bid_qty + ask_qty
        if total <= 0:
            return None
        return bid_qty / total

    def snapshot(self, levels: int | None = None) -> OrderBookSnapshot:
        """Return a serializable snapshot of current local state."""
        bids = self.bids if levels is None else self.bids[:levels]
        asks = self.asks if levels is None else self.asks[:levels]
        return OrderBookSnapshot(
            symbol=self.symbol,
            bids=bids,
            asks=asks,
            timestamp=self.timestamp or datetime.now(timezone.utc),
            sequence=self.sequence,
        )

    @staticmethod
    def _normalize_side(levels: Iterable[tuple[float, float]]) -> dict[float, float]:
        normalized: dict[float, float] = {}
        for price, quantity in levels:
            price_f = float(price)
            quantity_f = float(quantity)
            if price_f <= 0:
                raise ValueError("order book prices must be positive.")
            if quantity_f > 0:
                normalized[price_f] = quantity_f
        return normalized

    def _apply_side_updates(self, side: BookSide, levels: Iterable[tuple[float, float]]) -> None:
        target = self._bids if side == "bid" else self._asks
        for price, quantity in levels:
            price_f = float(price)
            quantity_f = float(quantity)
            if price_f <= 0:
                raise ValueError("order book prices must be positive.")
            if quantity_f <= 0:
                target.pop(price_f, None)
            else:
                target[price_f] = quantity_f

    def _validate_crossed_book(self) -> None:
        if self.best_bid is not None and self.best_ask is not None and self.best_bid >= self.best_ask:
            raise ValueError("invalid crossed book: best_bid must be < best_ask.")


__all__ = ["BookSide", "LocalOrderBook", "OrderBookLevel", "OrderBookSnapshot"]
