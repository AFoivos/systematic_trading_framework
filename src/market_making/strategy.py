from __future__ import annotations

from dataclasses import dataclass

from .adverse_selection_filter import AdverseSelectionFilter
from .quote_generator import QuoteDecision, QuoteGenerator
from src.market_data.order_book import LocalOrderBook
from src.market_data.trades import Trade


@dataclass(frozen=True)
class MarketMakingStrategy:
    """Small orchestrator that turns book state into a quote decision."""

    quote_generator: QuoteGenerator
    adverse_filter: AdverseSelectionFilter | None = None

    def decide(
        self,
        *,
        book: LocalOrderBook,
        inventory: float,
        recent_returns: list[float] | None = None,
        recent_trades: list[Trade] | None = None,
    ) -> QuoteDecision:
        """Generate a quote after optional adverse-selection gating."""
        if self.adverse_filter is not None:
            filter_decision = self.adverse_filter.evaluate(book=book, recent_trades=recent_trades)
            if not filter_decision.should_quote:
                fair_quote = self.quote_generator.generate(
                    book=book,
                    inventory=inventory,
                    recent_returns=recent_returns,
                )
                return QuoteDecision(
                    symbol=fair_quote.symbol,
                    bid_price=None,
                    ask_price=None,
                    bid_size=0.0,
                    ask_size=0.0,
                    fair_price=fair_quote.fair_price,
                    spread_bps=fair_quote.spread_bps,
                    inventory_ratio=fair_quote.inventory_ratio,
                    should_quote=False,
                    reason=filter_decision.reason,
                    timestamp=fair_quote.timestamp,
                )
            return self.quote_generator.generate(
                book=book,
                inventory=inventory,
                recent_returns=recent_returns,
                spread_multiplier=filter_decision.spread_multiplier,
            )
        return self.quote_generator.generate(book=book, inventory=inventory, recent_returns=recent_returns)


__all__ = ["MarketMakingStrategy"]
