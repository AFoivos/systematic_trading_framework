from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import pstdev

from src.market_data.order_book import LocalOrderBook
from src.market_data.trades import Trade
from src.market_making.quote_generator import QuoteDecision, QuoteGenerator

from .common import StrategyDecision, select_quote_sides


@dataclass(frozen=True)
class DirectionalFlowStrategyConfig:
    """Causal order-book and trade-flow weights for one-sided passive quoting."""

    imbalance_weight: float = 0.45
    trade_flow_weight: float = 0.35
    trend_weight: float = 0.20
    trend_scale_bps: float = 1.0
    min_abs_signal: float = 0.25
    max_volatility_bps: float = 20.0
    inventory_soft_limit_ratio: float = 0.70
    maker_fee_bps: float = 0.0
    adverse_selection_buffer_bps: float = 0.0
    signal_edge_credit_bps: float = 0.0
    min_expected_edge_bps: float = 0.0
    quote_both_when_neutral: bool = False

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.maker_fee_bps)):
            raise ValueError("maker_fee_bps must be finite.")
        for name, value in (
            ("imbalance_weight", self.imbalance_weight),
            ("trade_flow_weight", self.trade_flow_weight),
            ("trend_weight", self.trend_weight),
            ("trend_scale_bps", self.trend_scale_bps),
            ("min_abs_signal", self.min_abs_signal),
            ("max_volatility_bps", self.max_volatility_bps),
            ("adverse_selection_buffer_bps", self.adverse_selection_buffer_bps),
            ("signal_edge_credit_bps", self.signal_edge_credit_bps),
            ("min_expected_edge_bps", self.min_expected_edge_bps),
        ):
            if not math.isfinite(float(value)) or value < 0.0:
                raise ValueError(f"{name} must be finite and >= 0.")
        if self.trend_scale_bps <= 0.0:
            raise ValueError("trend_scale_bps must be > 0.")
        if self.imbalance_weight + self.trade_flow_weight + self.trend_weight <= 0.0:
            raise ValueError("at least one directional weight must be > 0.")
        if not 0.0 <= self.min_abs_signal <= 1.0:
            raise ValueError("min_abs_signal must be in [0, 1].")
        if not 0.0 <= self.inventory_soft_limit_ratio <= 1.0:
            raise ValueError("inventory_soft_limit_ratio must be in [0, 1].")


class DirectionalOneSidedFlowStrategy:
    """Quote only the side aligned with causal microstructure flow or inventory unwind."""

    name = "directional_one_sided_flow"

    def __init__(
        self,
        *,
        quote_generator: QuoteGenerator,
        config: DirectionalFlowStrategyConfig,
    ) -> None:
        self.quote_generator = quote_generator
        self.config = config

    def decide(
        self,
        *,
        book: LocalOrderBook,
        inventory: float,
        recent_returns: list[float] | None = None,
        recent_trades: list[Trade] | None = None,
    ) -> StrategyDecision:
        returns = [float(value) for value in list(recent_returns or [])]
        if not all(math.isfinite(value) for value in returns):
            raise ValueError("recent_returns must contain only finite values.")
        quote = self.quote_generator.generate(
            book=book,
            inventory=inventory,
            recent_returns=returns,
        )
        volatility_bps = pstdev(returns) * 10_000.0 if len(returns) >= 2 else 0.0
        score, components = self._flow_score(
            book=book,
            recent_returns=returns,
            recent_trades=recent_trades,
        )
        if volatility_bps > self.config.max_volatility_bps:
            quote = select_quote_sides(
                quote,
                allow_buy=False,
                allow_sell=False,
                reason="directional volatility limit exceeded",
            )
            return self._decision(
                quote=quote,
                score=score,
                volatility_bps=volatility_bps,
                expected_edge_bps=-self.config.adverse_selection_buffer_bps,
                side_reason="volatility_gate",
                components=components,
            )

        allow_buy, allow_sell, side_reason = self._allowed_sides(
            inventory_ratio=quote.inventory_ratio,
            score=score,
        )
        quote = select_quote_sides(
            quote,
            allow_buy=allow_buy,
            allow_sell=allow_sell,
            reason="directional signal below threshold",
        )
        expected_edge = (
            quote.spread_bps / 2.0
            + abs(score) * self.config.signal_edge_credit_bps
            - self.config.maker_fee_bps
            - self.config.adverse_selection_buffer_bps
        )
        if quote.should_quote and expected_edge < self.config.min_expected_edge_bps:
            quote = select_quote_sides(
                quote,
                allow_buy=False,
                allow_sell=False,
                reason="insufficient directional edge after fees",
            )
        return self._decision(
            quote=quote,
            score=score,
            volatility_bps=volatility_bps,
            expected_edge_bps=expected_edge,
            side_reason=side_reason,
            components=components,
        )

    def _flow_score(
        self,
        *,
        book: LocalOrderBook,
        recent_returns: list[float],
        recent_trades: list[Trade] | None,
    ) -> tuple[float, dict[str, float]]:
        imbalance = book.imbalance(1)
        imbalance_signal = 0.0 if imbalance is None else (float(imbalance) - 0.5) * 2.0
        matching_trades = [
            trade
            for trade in list(recent_trades or [])
            if trade.symbol == book.symbol
        ]
        buy_qty = sum(
            trade.quantity
            for trade in matching_trades
            if trade.aggressor_side == "buy"
        )
        sell_qty = sum(
            trade.quantity
            for trade in matching_trades
            if trade.aggressor_side == "sell"
        )
        total_qty = buy_qty + sell_qty
        trade_flow_signal = (buy_qty - sell_qty) / total_qty if total_qty > 0.0 else 0.0
        trend_bps = sum(recent_returns) * 10_000.0
        trend_signal = min(max(trend_bps / self.config.trend_scale_bps, -1.0), 1.0)
        weight_sum = (
            self.config.imbalance_weight
            + self.config.trade_flow_weight
            + self.config.trend_weight
        )
        score = (
            self.config.imbalance_weight * imbalance_signal
            + self.config.trade_flow_weight * trade_flow_signal
            + self.config.trend_weight * trend_signal
        ) / weight_sum
        score = min(max(score, -1.0), 1.0)
        return score, {
            "imbalance_signal": imbalance_signal,
            "trade_flow_signal": trade_flow_signal,
            "trend_signal": trend_signal,
            "trend_bps": trend_bps,
        }

    def _allowed_sides(
        self,
        *,
        inventory_ratio: float,
        score: float,
    ) -> tuple[bool, bool, str]:
        soft_limit = self.config.inventory_soft_limit_ratio
        if soft_limit > 0.0 and inventory_ratio >= soft_limit:
            return False, True, "long_inventory_unwind"
        if soft_limit > 0.0 and inventory_ratio <= -soft_limit:
            return True, False, "short_inventory_unwind"
        if score > 0.0 and score >= self.config.min_abs_signal:
            return True, False, "positive_flow"
        if score < 0.0 and -score >= self.config.min_abs_signal:
            return False, True, "negative_flow"
        if self.config.quote_both_when_neutral:
            return True, True, "neutral_two_sided"
        return False, False, "weak_flow"

    def _decision(
        self,
        *,
        quote: QuoteDecision,
        score: float,
        volatility_bps: float,
        expected_edge_bps: float,
        side_reason: str,
        components: dict[str, float],
    ) -> StrategyDecision:
        return StrategyDecision(
            strategy_name=self.name,
            quote=quote,
            expected_edge_bps=expected_edge_bps,
            diagnostics={
                **components,
                "flow_score": score,
                "recent_volatility_bps": volatility_bps,
                "side_reason": side_reason,
                "inventory_ratio": quote.inventory_ratio,
            },
        )


__all__ = [
    "DirectionalFlowStrategyConfig",
    "DirectionalOneSidedFlowStrategy",
]
