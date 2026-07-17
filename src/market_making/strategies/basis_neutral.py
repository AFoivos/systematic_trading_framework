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
class BasisNeutralStrategyConfig:
    quote: ExternalFairQuoteConfig
    target_basis_bps: float = 0.0
    funding_to_basis_multiplier: float = 0.0
    maker_fee_bps: float = 0.0
    hedge_fee_bps: float = 0.0
    hedge_slippage_bps: float = 0.0
    min_expected_edge_bps: float = 0.0
    min_dislocation_bps: float = 0.0
    max_abs_observed_basis_bps: float = 500.0
    max_book_time_skew_ms: int = 1_000
    quote_both_when_neutral: bool = True
    hedge_ratio: float = 1.0

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.maker_fee_bps)):
            raise ValueError("maker_fee_bps must be finite.")
        for name, value in (
            ("target_basis_bps", self.target_basis_bps),
            ("funding_to_basis_multiplier", self.funding_to_basis_multiplier),
        ):
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite.")
        for name, value in (
            ("hedge_fee_bps", self.hedge_fee_bps),
            ("hedge_slippage_bps", self.hedge_slippage_bps),
            ("min_expected_edge_bps", self.min_expected_edge_bps),
            ("min_dislocation_bps", self.min_dislocation_bps),
            ("max_abs_observed_basis_bps", self.max_abs_observed_basis_bps),
        ):
            if not math.isfinite(float(value)) or value < 0.0:
                raise ValueError(f"{name} must be finite and >= 0.")
        if self.max_book_time_skew_ms < 0:
            raise ValueError("max_book_time_skew_ms must be >= 0.")
        if not math.isfinite(float(self.hedge_ratio)) or self.hedge_ratio <= 0.0:
            raise ValueError("hedge_ratio must be finite and > 0.")


class FundingBasisNeutralStrategy:
    """Quote a perpetual around synchronized spot fair value and hedge every fill."""

    name = "funding_basis_neutral"

    def __init__(self, config: BasisNeutralStrategyConfig) -> None:
        self.config = config

    def decide(
        self,
        *,
        perpetual_book: LocalOrderBook,
        hedge_book: LocalOrderBook,
        inventory: float,
        expected_funding_bps: float = 0.0,
    ) -> StrategyDecision:
        if not math.isfinite(float(expected_funding_bps)):
            raise ValueError("expected_funding_bps must be finite.")
        if not books_are_synchronized(
            (perpetual_book, hedge_book),
            max_time_skew_ms=self.config.max_book_time_skew_ms,
        ):
            fair = hedge_book.mid_price or perpetual_book.mid_price or 1.0
            quote = rejected_quote(
                book=perpetual_book,
                fair_price=fair,
                spread_bps=self.config.quote.spread_bps,
                inventory_ratio=normalized_inventory(inventory, self.config.quote.max_inventory),
                reason="basis books are not synchronized",
            )
            return StrategyDecision(self.name, quote, 0.0, diagnostics={"synchronized": False})
        if perpetual_book.mid_price is None or hedge_book.mid_price is None:
            raise ValueError("basis strategy requires complete books.")

        target_basis_bps = (
            self.config.target_basis_bps
            + self.config.funding_to_basis_multiplier * float(expected_funding_bps)
        )
        fair_price = hedge_book.mid_price * (1.0 + target_basis_bps / 10_000.0)
        observed_basis_bps = (
            perpetual_book.mid_price / hedge_book.mid_price - 1.0
        ) * 10_000.0
        dislocation_bps = observed_basis_bps - target_basis_bps
        if abs(observed_basis_bps) > self.config.max_abs_observed_basis_bps:
            quote = rejected_quote(
                book=perpetual_book,
                fair_price=fair_price,
                spread_bps=self.config.quote.spread_bps,
                inventory_ratio=normalized_inventory(inventory, self.config.quote.max_inventory),
                reason="observed basis exceeds safety limit",
            )
            return self._decision(
                quote=quote,
                fair_price=fair_price,
                observed_basis_bps=observed_basis_bps,
                target_basis_bps=target_basis_bps,
                dislocation_bps=dislocation_bps,
                buy_edge=float("-inf"),
                sell_edge=float("-inf"),
                hedges=(),
            )

        quote = quote_around_external_fair(
            book=perpetual_book,
            fair_price=fair_price,
            inventory=inventory,
            config=self.config.quote,
        )
        total_cost_bps = (
            self.config.maker_fee_bps
            + self.config.hedge_fee_bps
            + self.config.hedge_slippage_bps
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
            reason="insufficient fee-adjusted basis edge",
        )
        hedges = (
            HedgeTemplate(
                trigger_side="buy",
                symbol=hedge_book.symbol,
                side="sell",
                reference_price=hedge_book.mid_price,
                quantity_per_fill_unit=self.config.hedge_ratio,
                reason="delta hedge long perpetual fill",
            ),
            HedgeTemplate(
                trigger_side="sell",
                symbol=hedge_book.symbol,
                side="buy",
                reference_price=hedge_book.mid_price,
                quantity_per_fill_unit=self.config.hedge_ratio,
                reason="delta hedge short perpetual fill",
            ),
        )
        return self._decision(
            quote=quote,
            fair_price=fair_price,
            observed_basis_bps=observed_basis_bps,
            target_basis_bps=target_basis_bps,
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

    def _decision(
        self,
        *,
        quote: QuoteDecision,
        fair_price: float,
        observed_basis_bps: float,
        target_basis_bps: float,
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
                "fair_price": fair_price,
                "observed_basis_bps": observed_basis_bps,
                "target_basis_bps": target_basis_bps,
                "basis_dislocation_bps": dislocation_bps,
                "buy_expected_edge_bps": buy_edge if math.isfinite(buy_edge) else None,
                "sell_expected_edge_bps": sell_edge if math.isfinite(sell_edge) else None,
            },
        )


__all__ = [
    "BasisNeutralStrategyConfig",
    "FundingBasisNeutralStrategy",
]
