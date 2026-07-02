from __future__ import annotations

from dataclasses import dataclass

from src.market_data.order_book import LocalOrderBook
from src.market_data.trades import Trade


@dataclass(frozen=True)
class AdverseSelectionConfig:
    """Initial adverse-selection filter thresholds."""

    max_imbalance: float = 0.8
    min_imbalance: float = 0.2
    disable_on_high_volatility: bool = True
    high_volatility_bps: float = 40.0
    disable_on_strong_trend: bool = True


@dataclass(frozen=True)
class FilterDecision:
    """Decision returned by adverse-selection checks."""

    should_quote: bool
    reason: str = "ok"
    spread_multiplier: float = 1.0


class TrendRegimeProvider:
    """Interface for future integration with existing candle/regime features."""

    def is_strong_trend(self, symbol: str) -> bool:
        """Return whether the current external regime says the symbol is strongly trending."""
        raise NotImplementedError


class AdverseSelectionFilter:
    """Stop or widen quotes during unstable microstructure regimes."""

    def __init__(self, config: AdverseSelectionConfig, trend_provider: TrendRegimeProvider | None = None) -> None:
        self.config = config
        self.trend_provider = trend_provider

    def evaluate(
        self,
        *,
        book: LocalOrderBook,
        recent_trades: list[Trade] | None = None,
        recent_volatility_bps: float = 0.0,
    ) -> FilterDecision:
        imbalance = book.imbalance(levels=1)
        if imbalance is not None and imbalance >= self.config.max_imbalance:
            return FilterDecision(False, "extreme bid-side imbalance")
        if imbalance is not None and imbalance <= self.config.min_imbalance:
            return FilterDecision(False, "extreme ask-side imbalance")
        if self.config.disable_on_high_volatility and recent_volatility_bps >= self.config.high_volatility_bps:
            return FilterDecision(False, "high recent volatility")
        if self.config.disable_on_strong_trend and self.trend_provider is not None:
            if self.trend_provider.is_strong_trend(book.symbol):
                return FilterDecision(False, "strong external trend regime")
        if recent_trades:
            buy_qty = sum(t.quantity for t in recent_trades if t.aggressor_side == "buy")
            sell_qty = sum(t.quantity for t in recent_trades if t.aggressor_side == "sell")
            total = buy_qty + sell_qty
            if total > 0 and max(buy_qty, sell_qty) / total >= 0.9:
                return FilterDecision(True, "one-sided aggressive flow", spread_multiplier=1.5)
        return FilterDecision(True)


__all__ = [
    "AdverseSelectionConfig",
    "AdverseSelectionFilter",
    "FilterDecision",
    "TrendRegimeProvider",
]
