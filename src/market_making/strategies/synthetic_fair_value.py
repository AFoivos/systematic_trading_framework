from __future__ import annotations

from dataclasses import dataclass
import math

from src.market_data.order_book import LocalOrderBook
from src.market_making.quote_generator import QuoteDecision

from .common import (
    ExternalFairQuoteConfig,
    HedgeTemplate,
    StrategyDecision,
    books_are_synchronized,
    normalized_inventory,
    quote_around_external_fair,
    rejected_quote,
    select_quote_sides,
    side_edge_bps,
)


@dataclass(frozen=True)
class SyntheticFairValueStrategyConfig:
    quote: ExternalFairQuoteConfig
    maker_fee_bps: float = 0.0
    aggregate_hedge_cost_bps: float = 0.0
    min_expected_edge_bps: float = 0.0
    min_dislocation_bps: float = 0.0
    max_abs_dislocation_bps: float = 500.0
    max_book_time_skew_ms: int = 1_000
    quote_both_when_neutral: bool = False

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.maker_fee_bps)):
            raise ValueError("maker_fee_bps must be finite.")
        for name, value in (
            ("aggregate_hedge_cost_bps", self.aggregate_hedge_cost_bps),
            ("min_expected_edge_bps", self.min_expected_edge_bps),
            ("min_dislocation_bps", self.min_dislocation_bps),
            ("max_abs_dislocation_bps", self.max_abs_dislocation_bps),
        ):
            if not math.isfinite(float(value)) or value < 0.0:
                raise ValueError(f"{name} must be finite and >= 0.")
        if self.max_book_time_skew_ms < 0:
            raise ValueError("max_book_time_skew_ms must be >= 0.")


class CrossPairSyntheticFairValueStrategy:
    """
    Market make a ratio cross using numerator/denominator reference books.

    For target BASE/QUOTE, the synchronized synthetic fair is:
    numerator(BASE/USD) / denominator(QUOTE/USD).
    """

    name = "cross_pair_synthetic_fair_value"

    def __init__(self, config: SyntheticFairValueStrategyConfig) -> None:
        self.config = config

    def decide(
        self,
        *,
        target_book: LocalOrderBook,
        numerator_book: LocalOrderBook,
        denominator_book: LocalOrderBook,
        inventory: float,
    ) -> StrategyDecision:
        books = (target_book, numerator_book, denominator_book)
        if not books_are_synchronized(
            books,
            max_time_skew_ms=self.config.max_book_time_skew_ms,
        ):
            fair = target_book.mid_price or 1.0
            quote = rejected_quote(
                book=target_book,
                fair_price=fair,
                spread_bps=self.config.quote.spread_bps,
                inventory_ratio=normalized_inventory(inventory, self.config.quote.max_inventory),
                reason="synthetic books are not synchronized",
            )
            return StrategyDecision(self.name, quote, 0.0, diagnostics={"synchronized": False})
        if (
            target_book.mid_price is None
            or numerator_book.mid_price is None
            or denominator_book.mid_price is None
        ):
            raise ValueError("synthetic strategy requires complete books.")
        if denominator_book.mid_price <= 0.0:
            raise ValueError("synthetic denominator fair value must be positive.")

        fair_price = numerator_book.mid_price / denominator_book.mid_price
        dislocation_bps = (
            target_book.mid_price / fair_price - 1.0
        ) * 10_000.0
        if abs(dislocation_bps) > self.config.max_abs_dislocation_bps:
            quote = rejected_quote(
                book=target_book,
                fair_price=fair_price,
                spread_bps=self.config.quote.spread_bps,
                inventory_ratio=normalized_inventory(inventory, self.config.quote.max_inventory),
                reason="synthetic dislocation exceeds safety limit",
            )
            return self._decision(
                quote=quote,
                fair_price=fair_price,
                dislocation_bps=dislocation_bps,
                buy_edge=float("-inf"),
                sell_edge=float("-inf"),
                hedges=(),
            )

        quote = quote_around_external_fair(
            book=target_book,
            fair_price=fair_price,
            inventory=inventory,
            config=self.config.quote,
        )
        total_cost_bps = (
            self.config.maker_fee_bps
            + self.config.aggregate_hedge_cost_bps
        )
        buy_edge = side_edge_bps(
            side="buy",
            price=quote.bid_price,
            fair_price=fair_price,
            cost_bps=total_cost_bps,
        )
        sell_edge = side_edge_bps(
            side="sell",
            price=quote.ask_price,
            fair_price=fair_price,
            cost_bps=total_cost_bps,
        )
        allow_buy, allow_sell = self._dislocation_sides(dislocation_bps)
        allow_buy = allow_buy and buy_edge >= self.config.min_expected_edge_bps
        allow_sell = allow_sell and sell_edge >= self.config.min_expected_edge_bps
        quote = select_quote_sides(
            quote,
            allow_buy=allow_buy,
            allow_sell=allow_sell,
            reason="insufficient fee-adjusted synthetic edge",
        )
        hedges = self._hedge_templates(
            numerator_book=numerator_book,
            denominator_book=denominator_book,
        )
        return self._decision(
            quote=quote,
            fair_price=fair_price,
            dislocation_bps=dislocation_bps,
            buy_edge=buy_edge,
            sell_edge=sell_edge,
            hedges=hedges,
        )

    def _dislocation_sides(self, dislocation_bps: float) -> tuple[bool, bool]:
        threshold = self.config.min_dislocation_bps
        if dislocation_bps > threshold:
            return False, True
        if dislocation_bps < -threshold:
            return True, False
        if self.config.quote_both_when_neutral:
            return True, True
        return False, False

    @staticmethod
    def _hedge_templates(
        *,
        numerator_book: LocalOrderBook,
        denominator_book: LocalOrderBook,
    ) -> tuple[HedgeTemplate, ...]:
        assert numerator_book.mid_price is not None
        assert denominator_book.mid_price is not None
        return (
            HedgeTemplate(
                trigger_side="buy",
                symbol=numerator_book.symbol,
                side="sell",
                reference_price=numerator_book.mid_price,
                quantity_per_fill_unit=1.0,
                reason="neutralize target base acquired on synthetic buy fill",
            ),
            HedgeTemplate(
                trigger_side="buy",
                symbol=denominator_book.symbol,
                side="buy",
                reference_price=denominator_book.mid_price,
                quantity_per_fill_notional=1.0,
                reason="neutralize target quote spent on synthetic buy fill",
            ),
            HedgeTemplate(
                trigger_side="sell",
                symbol=numerator_book.symbol,
                side="buy",
                reference_price=numerator_book.mid_price,
                quantity_per_fill_unit=1.0,
                reason="neutralize target base sold on synthetic sell fill",
            ),
            HedgeTemplate(
                trigger_side="sell",
                symbol=denominator_book.symbol,
                side="sell",
                reference_price=denominator_book.mid_price,
                quantity_per_fill_notional=1.0,
                reason="neutralize target quote received on synthetic sell fill",
            ),
        )

    def _decision(
        self,
        *,
        quote: QuoteDecision,
        fair_price: float,
        dislocation_bps: float,
        buy_edge: float,
        sell_edge: float,
        hedges: tuple[HedgeTemplate, ...],
    ) -> StrategyDecision:
        active_edges = []
        if quote.bid_price is not None and math.isfinite(buy_edge):
            active_edges.append(buy_edge)
        if quote.ask_price is not None and math.isfinite(sell_edge):
            active_edges.append(sell_edge)
        expected_edge = sum(active_edges) / len(active_edges) if active_edges else 0.0
        return StrategyDecision(
            strategy_name=self.name,
            quote=quote,
            expected_edge_bps=expected_edge,
            hedge_templates=hedges,
            diagnostics={
                "synchronized": True,
                "synthetic_fair_price": fair_price,
                "synthetic_dislocation_bps": dislocation_bps,
                "buy_expected_edge_bps": buy_edge if math.isfinite(buy_edge) else None,
                "sell_expected_edge_bps": sell_edge if math.isfinite(sell_edge) else None,
            },
        )


__all__ = [
    "CrossPairSyntheticFairValueStrategy",
    "SyntheticFairValueStrategyConfig",
]
