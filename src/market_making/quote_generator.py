from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from .fair_price import FairPriceModel, compute_fair_price
from .inventory_skew import InventorySkew, InventorySkewConfig
from .spread_model import SpreadConfig, SpreadModel
from src.market_data.order_book import LocalOrderBook


QuotePlacementMode = Literal["fair_price_bps", "join_top_of_book", "improve_top_of_book"]


@dataclass(frozen=True)
class QuoteGeneratorConfig:
    """Static quote-generation constraints."""

    fair_price_model: FairPriceModel = "microprice"
    quote_placement_mode: QuotePlacementMode = "fair_price_bps"
    spread: SpreadConfig = SpreadConfig()
    inventory_skew_strength: float = 0.5
    order_size: float = 0.001
    max_inventory: float = 0.01
    tick_size: float = 0.5
    lot_size: float = 0.0001
    min_order_size: float = 0.0
    min_notional: float = 5.0


@dataclass(frozen=True)
class QuoteDecision:
    """Final bid/ask quote decision after pricing, skew, and exchange constraints."""

    symbol: str
    bid_price: float | None
    ask_price: float | None
    bid_size: float
    ask_size: float
    fair_price: float
    spread_bps: float
    inventory_ratio: float
    should_quote: bool
    reason: str
    timestamp: datetime


class QuoteGenerator:
    """Generate constrained bid/ask quotes from order book state and inventory."""

    def __init__(self, config: QuoteGeneratorConfig) -> None:
        self.config = config
        self.spread_model = SpreadModel(config.spread)
        self.inventory_skew = InventorySkew(
            InventorySkewConfig(
                max_inventory=config.max_inventory,
                skew_strength=config.inventory_skew_strength,
            )
        )

    def generate(
        self,
        *,
        book: LocalOrderBook,
        inventory: float,
        recent_returns: list[float] | None = None,
        spread_multiplier: float = 1.0,
    ) -> QuoteDecision:
        """Return a complete quote decision for the current book state."""
        if spread_multiplier <= 0:
            raise ValueError("spread_multiplier must be > 0.")
        fair_price = compute_fair_price(book, self.config.fair_price_model)
        raw_spread_bps = self.spread_model.compute_spread_bps(recent_returns=recent_returns or ())
        spread_bps = min(
            max(raw_spread_bps * spread_multiplier, self.config.spread.min_spread_bps),
            self.config.spread.max_spread_bps,
        )
        bid_price, ask_price, spread_bps = self._place_quote(
            book=book,
            fair_price=fair_price,
            spread_bps=spread_bps,
            inventory=inventory,
        )
        size = self._round_down(self.config.order_size, self.config.lot_size)
        inventory_ratio = self.inventory_skew.normalized_inventory(inventory)

        if bid_price <= 0 or ask_price <= 0 or bid_price >= ask_price:
            return self._reject(book.symbol, fair_price, spread_bps, inventory_ratio, "invalid quote prices")
        if size < max(self.config.min_order_size, self.config.lot_size):
            return self._reject(book.symbol, fair_price, spread_bps, inventory_ratio, "order size below minimum")
        if bid_price * size < self.config.min_notional and ask_price * size < self.config.min_notional:
            return self._reject(book.symbol, fair_price, spread_bps, inventory_ratio, "quote notional below minimum")

        return QuoteDecision(
            symbol=book.symbol,
            bid_price=bid_price,
            ask_price=ask_price,
            bid_size=size,
            ask_size=size,
            fair_price=fair_price,
            spread_bps=spread_bps,
            inventory_ratio=inventory_ratio,
            should_quote=True,
            reason="ok",
            timestamp=datetime.now(timezone.utc),
        )

    def _place_quote(
        self,
        *,
        book: LocalOrderBook,
        fair_price: float,
        spread_bps: float,
        inventory: float,
    ) -> tuple[float, float, float]:
        mode = self.config.quote_placement_mode
        if mode == "fair_price_bps":
            half_spread = fair_price * (spread_bps / 10_000.0) / 2.0
            shift = self.inventory_skew.reservation_price_shift(
                fair_price=fair_price,
                inventory=inventory,
                half_spread=half_spread,
            )
            bid_price = self._round_down(fair_price + shift - half_spread, self.config.tick_size)
            ask_price = self._round_up(fair_price + shift + half_spread, self.config.tick_size)
            return bid_price, ask_price, spread_bps
        if mode == "join_top_of_book":
            return self._join_top_of_book(book)
        if mode == "improve_top_of_book":
            return self._improve_top_of_book(book)
        raise ValueError(f"unsupported quote placement mode: {mode}")

    def _join_top_of_book(self, book: LocalOrderBook) -> tuple[float, float, float]:
        if book.best_bid is None or book.best_ask is None:
            raise ValueError("top-of-book quote placement requires both best_bid and best_ask.")
        bid_price = float(book.best_bid)
        ask_price = float(book.best_ask)
        return bid_price, ask_price, self._quoted_spread_bps(bid_price, ask_price)

    def _improve_top_of_book(self, book: LocalOrderBook) -> tuple[float, float, float]:
        if book.best_bid is None or book.best_ask is None:
            raise ValueError("top-of-book quote placement requires both best_bid and best_ask.")
        bid_price = float(book.best_bid) + self.config.tick_size
        ask_price = float(book.best_ask) - self.config.tick_size
        if bid_price >= ask_price:
            return self._join_top_of_book(book)
        return bid_price, ask_price, self._quoted_spread_bps(bid_price, ask_price)

    @staticmethod
    def _quoted_spread_bps(bid_price: float, ask_price: float) -> float:
        quote_mid = (bid_price + ask_price) / 2.0
        if quote_mid <= 0:
            return 0.0
        return (ask_price - bid_price) / quote_mid * 10_000.0

    @staticmethod
    def _round_down(value: float, step: float) -> float:
        if step <= 0:
            raise ValueError("rounding step must be > 0.")
        return int(value / step) * step

    @staticmethod
    def _round_up(value: float, step: float) -> float:
        if step <= 0:
            raise ValueError("rounding step must be > 0.")
        units = int(value / step)
        rounded = units * step
        return rounded if rounded >= value else (units + 1) * step

    @staticmethod
    def _reject(
        symbol: str,
        fair_price: float,
        spread_bps: float,
        inventory_ratio: float,
        reason: str,
    ) -> QuoteDecision:
        return QuoteDecision(
            symbol=symbol,
            bid_price=None,
            ask_price=None,
            bid_size=0.0,
            ask_size=0.0,
            fair_price=fair_price,
            spread_bps=spread_bps,
            inventory_ratio=inventory_ratio,
            should_quote=False,
            reason=reason,
            timestamp=datetime.now(timezone.utc),
        )


__all__ = ["QuoteDecision", "QuoteGenerator", "QuoteGeneratorConfig", "QuotePlacementMode"]
