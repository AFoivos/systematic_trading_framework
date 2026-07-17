from __future__ import annotations

from dataclasses import dataclass
import math

from src.market_data.order_book import LocalOrderBook
from src.market_making.quote_generator import QuoteGenerator
from src.market_making.strategy import FeeAwareGate

from .common import StrategyDecision, active_side_count, select_quote_sides


@dataclass(frozen=True)
class AdaptiveInventoryStrategyConfig:
    """Fee and adverse-selection requirements for adaptive microprice quoting."""

    maker_fee_bps: float = 0.0
    min_expected_edge_bps: float = 0.0
    adverse_selection_buffer_bps: float = 0.0
    inventory_penalty_bps_per_unit: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.maker_fee_bps)):
            raise ValueError("maker_fee_bps must be finite.")
        for name, value in (
            ("min_expected_edge_bps", self.min_expected_edge_bps),
            ("adverse_selection_buffer_bps", self.adverse_selection_buffer_bps),
            ("inventory_penalty_bps_per_unit", self.inventory_penalty_bps_per_unit),
        ):
            if not math.isfinite(float(value)) or value < 0.0:
                raise ValueError(f"{name} must be finite and >= 0.")


class AdaptiveInventoryMicropriceStrategy:
    """
    Two-sided microprice strategy with volatility-aware spread and inventory skew.

    The supplied QuoteGenerator owns the fair-price, spread, rounding, and inventory
    configuration. This strategy adds a strict fee-aware economic gate.
    """

    name = "adaptive_inventory_microprice"

    def __init__(
        self,
        *,
        quote_generator: QuoteGenerator,
        config: AdaptiveInventoryStrategyConfig,
    ) -> None:
        self.quote_generator = quote_generator
        self.config = config
        self.fee_gate = FeeAwareGate(
            maker_fee_bps=config.maker_fee_bps,
            min_expected_edge_bps=config.min_expected_edge_bps,
            adverse_selection_buffer_bps=config.adverse_selection_buffer_bps,
            inventory_penalty_bps_per_unit=config.inventory_penalty_bps_per_unit,
        )

    def decide(
        self,
        *,
        book: LocalOrderBook,
        inventory: float,
        recent_returns: list[float] | None = None,
    ) -> StrategyDecision:
        quote = self.quote_generator.generate(
            book=book,
            inventory=inventory,
            recent_returns=recent_returns,
        )
        active_sides = active_side_count(quote)
        required_spread = self.fee_gate.min_required_spread_bps(
            inventory_ratio=quote.inventory_ratio,
            active_sides=max(active_sides, 1),
        )
        expected_edge = quote.spread_bps - required_spread
        if quote.should_quote and self.fee_gate.blocks(quote):
            quote = select_quote_sides(
                quote,
                allow_buy=False,
                allow_sell=False,
                reason="insufficient adaptive edge after fees",
            )
        return StrategyDecision(
            strategy_name=self.name,
            quote=quote,
            expected_edge_bps=expected_edge,
            diagnostics={
                "required_spread_bps": required_spread,
                "quoted_spread_bps": quote.spread_bps,
                "inventory_ratio": quote.inventory_ratio,
                "active_sides": active_sides,
            },
        )


__all__ = [
    "AdaptiveInventoryMicropriceStrategy",
    "AdaptiveInventoryStrategyConfig",
]
