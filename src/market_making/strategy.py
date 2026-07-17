from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import pstdev
from typing import Literal

from .adverse_selection_filter import AdverseSelectionFilter
from .quote_generator import QuoteDecision, QuoteGenerator
from src.market_data.order_book import LocalOrderBook
from src.market_data.trades import Trade


@dataclass(frozen=True)
class FeeAwareGate:
    """Reject quotes whose spread is too small to cover fee-adjusted edge requirements."""

    maker_fee_bps: float = 0.0
    min_expected_edge_bps: float = 0.0
    adverse_selection_buffer_bps: float = 0.0
    inventory_penalty_bps_per_unit: float = 0.0

    def __post_init__(self) -> None:
        for name, value in (
            ("maker_fee_bps", self.maker_fee_bps),
            ("min_expected_edge_bps", self.min_expected_edge_bps),
            ("adverse_selection_buffer_bps", self.adverse_selection_buffer_bps),
            ("inventory_penalty_bps_per_unit", self.inventory_penalty_bps_per_unit),
        ):
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite.")
        if any(
            value < 0.0
            for value in (
                self.min_expected_edge_bps,
                self.adverse_selection_buffer_bps,
                self.inventory_penalty_bps_per_unit,
            )
        ):
            raise ValueError("fee-aware edge and penalty thresholds must be >= 0.")

    def min_required_spread_bps(self, *, inventory_ratio: float, active_sides: int) -> float:
        fee_legs = min(max(int(active_sides), 1), 2)
        return (
            max(0.0, self.maker_fee_bps) * fee_legs
            + max(0.0, self.min_expected_edge_bps)
            + max(0.0, self.adverse_selection_buffer_bps)
            + abs(float(inventory_ratio)) * max(0.0, self.inventory_penalty_bps_per_unit)
        )

    def blocks(self, quote: QuoteDecision, *, edge_credit_bps: float = 0.0) -> bool:
        active_sides = int(quote.bid_price is not None and quote.bid_size > 0) + int(
            quote.ask_price is not None and quote.ask_size > 0
        )
        if active_sides == 0:
            return False
        required_spread = self.min_required_spread_bps(
            inventory_ratio=quote.inventory_ratio,
            active_sides=active_sides,
        )
        return quote.spread_bps + max(0.0, float(edge_credit_bps)) < required_spread


@dataclass(frozen=True)
class SideSelectionGate:
    """Restrict quoting to the less adverse side when short-horizon pressure is directional."""

    microprice_offset_threshold_bps: float = 0.0
    inventory_soft_limit_ratio: float = 1.0
    allowed_side_mode: Literal["both", "buy_only", "sell_only", "buy_only_with_unwind"] = "both"

    def __post_init__(self) -> None:
        if self.allowed_side_mode not in {"both", "buy_only", "sell_only", "buy_only_with_unwind"}:
            raise ValueError(
                "allowed_side_mode must be one of: both, buy_only, sell_only, buy_only_with_unwind"
            )
        if not math.isfinite(float(self.microprice_offset_threshold_bps)):
            raise ValueError("microprice_offset_threshold_bps must be finite.")
        if self.microprice_offset_threshold_bps < 0.0:
            raise ValueError("microprice_offset_threshold_bps must be >= 0.")
        if (
            not math.isfinite(float(self.inventory_soft_limit_ratio))
            or not 0.0 <= self.inventory_soft_limit_ratio <= 1.0
        ):
            raise ValueError("inventory_soft_limit_ratio must be finite and in [0, 1].")

    def apply(self, *, quote: QuoteDecision, book: LocalOrderBook) -> QuoteDecision:
        allowed_sides = self._allowed_sides(quote=quote, book=book)
        bid_enabled = "bid" in allowed_sides and quote.bid_price is not None and quote.bid_size > 0
        ask_enabled = "ask" in allowed_sides and quote.ask_price is not None and quote.ask_size > 0
        if bid_enabled and ask_enabled:
            return quote
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
                reason="no quote side selected",
                timestamp=quote.timestamp,
                diagnostics=quote.diagnostics,
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
            diagnostics=quote.diagnostics,
        )

    def _allowed_sides(self, *, quote: QuoteDecision, book: LocalOrderBook) -> set[str]:
        mode = str(self.allowed_side_mode).strip().lower()
        inventory_ratio = float(quote.inventory_ratio)
        soft_limit = max(0.0, min(float(self.inventory_soft_limit_ratio), 1.0))
        if mode == "buy_only_with_unwind":
            if soft_limit > 0.0 and inventory_ratio >= soft_limit:
                return {"ask"}
            return {"bid"}
        explicit_sides = self._explicit_allowed_sides()
        if explicit_sides != {"bid", "ask"}:
            return explicit_sides
        if soft_limit > 0.0:
            if inventory_ratio >= soft_limit:
                return {"ask"}
            if inventory_ratio <= -soft_limit:
                return {"bid"}
        mid = book.mid_price
        threshold = max(0.0, float(self.microprice_offset_threshold_bps))
        if mid is None or mid <= 0.0 or threshold <= 0.0:
            return {"bid", "ask"}
        fair_offset_bps = (quote.fair_price - mid) / mid * 10_000.0
        if fair_offset_bps >= threshold:
            return {"bid"}
        if fair_offset_bps <= -threshold:
            return {"ask"}
        return {"bid", "ask"}

    def _explicit_allowed_sides(self) -> set[str]:
        mode = str(self.allowed_side_mode).strip().lower()
        if mode == "buy_only":
            return {"bid"}
        if mode == "sell_only":
            return {"ask"}
        if mode == "buy_only_with_unwind":
            return {"bid", "ask"}
        return {"bid", "ask"}


@dataclass(frozen=True)
class DirectionalFeatureGate:
    """Grant edge credit only when directional microstructure features align."""

    microprice_offset_threshold_bps: float = 0.0
    imbalance_threshold: float = 0.0
    trend_threshold_bps: float = 0.0
    max_volatility_bps: float = 1.0e9
    edge_credit_bps: float = 0.0

    def __post_init__(self) -> None:
        for name, value in (
            ("microprice_offset_threshold_bps", self.microprice_offset_threshold_bps),
            ("imbalance_threshold", self.imbalance_threshold),
            ("trend_threshold_bps", self.trend_threshold_bps),
            ("max_volatility_bps", self.max_volatility_bps),
            ("edge_credit_bps", self.edge_credit_bps),
        ):
            if not math.isfinite(float(value)) or float(value) < 0.0:
                raise ValueError(f"{name} must be finite and >= 0.")

    def edge_credit(
        self,
        *,
        quote: QuoteDecision,
        book: LocalOrderBook,
        recent_returns: list[float] | None = None,
    ) -> float:
        active_side = self._active_side(quote)
        if active_side is None:
            return 0.0
        mid = book.mid_price
        if mid is None or mid <= 0.0:
            return 0.0
        fair_offset_bps = (quote.fair_price - mid) / mid * 10_000.0
        if active_side == "bid" and fair_offset_bps < float(self.microprice_offset_threshold_bps):
            return 0.0
        if active_side == "ask" and fair_offset_bps > -float(self.microprice_offset_threshold_bps):
            return 0.0
        imbalance = book.imbalance(1)
        if imbalance is None:
            return 0.0
        imbalance_strength = abs(float(imbalance) - 0.5) * 2.0
        if imbalance_strength < float(self.imbalance_threshold):
            return 0.0
        returns = [float(value) for value in list(recent_returns or [])]
        trend_bps = sum(returns) * 10_000.0 if returns else 0.0
        if active_side == "bid" and trend_bps < float(self.trend_threshold_bps):
            return 0.0
        if active_side == "ask" and trend_bps > -float(self.trend_threshold_bps):
            return 0.0
        volatility_bps = pstdev(returns) * 10_000.0 if len(returns) >= 2 else 0.0
        if volatility_bps > float(self.max_volatility_bps):
            return 0.0
        return max(0.0, float(self.edge_credit_bps))

    @staticmethod
    def _active_side(quote: QuoteDecision) -> str | None:
        bid_enabled = quote.bid_price is not None and quote.bid_size > 0
        ask_enabled = quote.ask_price is not None and quote.ask_size > 0
        if bid_enabled and not ask_enabled:
            return "bid"
        if ask_enabled and not bid_enabled:
            return "ask"
        return None


@dataclass(frozen=True)
class MarketMakingStrategy:
    """Small orchestrator that turns book state into a quote decision."""

    quote_generator: QuoteGenerator
    adverse_filter: AdverseSelectionFilter | None = None
    fee_aware_gate: FeeAwareGate | None = None
    side_selection_gate: SideSelectionGate | None = None
    directional_feature_gate: DirectionalFeatureGate | None = None

    def decide(
        self,
        *,
        book: LocalOrderBook,
        inventory: float,
        recent_returns: list[float] | None = None,
        recent_trades: list[Trade] | None = None,
    ) -> QuoteDecision:
        """Generate a quote after optional adverse-selection gating."""
        spread_multiplier = 1.0
        if self.adverse_filter is not None:
            returns = [float(value) for value in list(recent_returns or [])]
            recent_volatility_bps = (
                pstdev(returns) * 10_000.0
                if len(returns) >= 2
                else 0.0
            )
            filter_decision = self.adverse_filter.evaluate(
                book=book,
                recent_trades=recent_trades,
                recent_volatility_bps=recent_volatility_bps,
            )
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
                    diagnostics=fair_quote.diagnostics,
                )
            spread_multiplier = filter_decision.spread_multiplier

        quote = self.quote_generator.generate(
            book=book,
            inventory=inventory,
            recent_returns=recent_returns,
            spread_multiplier=spread_multiplier,
        )
        if self.side_selection_gate is not None and quote.should_quote:
            quote = self.side_selection_gate.apply(quote=quote, book=book)
        edge_credit_bps = 0.0
        if self.directional_feature_gate is not None and quote.should_quote:
            edge_credit_bps = self.directional_feature_gate.edge_credit(
                quote=quote,
                book=book,
                recent_returns=recent_returns,
            )
        if self.fee_aware_gate is not None and quote.should_quote and self.fee_aware_gate.blocks(
            quote,
            edge_credit_bps=edge_credit_bps,
        ):
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
                reason="insufficient edge after fees",
                timestamp=quote.timestamp,
                diagnostics=quote.diagnostics,
            )
        return quote


__all__ = ["DirectionalFeatureGate", "FeeAwareGate", "MarketMakingStrategy", "SideSelectionGate"]
