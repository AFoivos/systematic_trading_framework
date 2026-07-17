from __future__ import annotations

from copy import deepcopy
import json
from datetime import datetime, timedelta, timezone

import pytest

from scripts.run_market_making_strategy_suite import (
    DEFAULT_STRATEGY_CONFIGS,
    load_strategy_config,
    run_strategy_config,
    run_strategy_suite,
)
from src.market_data.order_book import LocalOrderBook
from src.market_data.trades import Trade
from src.market_making.paper_engine import PaperMarketMakingEngine
from src.market_making.quote_generator import QuoteGenerator, QuoteGeneratorConfig
from src.market_making.risk import RiskEngine, RiskLimits
from src.market_making.spread_model import SpreadConfig
from src.market_making.strategies import (
    AdaptiveInventoryMicropriceStrategy,
    AdaptiveInventoryStrategyConfig,
    BasisNeutralStrategyConfig,
    ConservativeQueuePosition,
    CrossPairSyntheticFairValueStrategy,
    DirectionalFlowStrategyConfig,
    DirectionalOneSidedFlowStrategy,
    ExternalFairQuoteConfig,
    FundingBasisNeutralStrategy,
    QueueAwareJoinImproveStrategy,
    QueueAwareStrategyConfig,
    QueueState,
    SyntheticFairValueStrategyConfig,
)


NOW = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)


def _book(
    symbol: str,
    *,
    bid: float,
    ask: float,
    bid_qty: float = 1.0,
    ask_qty: float = 1.0,
    timestamp: datetime = NOW,
) -> LocalOrderBook:
    book = LocalOrderBook(symbol)
    book.apply_snapshot(
        bids=[(bid, bid_qty)],
        asks=[(ask, ask_qty)],
        timestamp=timestamp,
        sequence=1,
    )
    return book


def _quote_generator(*, inventory_skew_strength: float = 1.0) -> QuoteGenerator:
    return QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="microprice",
            quote_placement_mode="fair_price_bps",
            spread=SpreadConfig(
                model="volatility_adjusted",
                base_spread_bps=100.0,
                min_spread_bps=80.0,
                max_spread_bps=200.0,
                maker_fee_bps=1.0,
            ),
            inventory_skew_strength=inventory_skew_strength,
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.1,
            lot_size=0.1,
            min_notional=1.0,
        )
    )


def _external_quote(
    *,
    spread_bps: float = 20.0,
    tick_size: float = 0.1,
    min_notional: float = 1.0,
) -> ExternalFairQuoteConfig:
    return ExternalFairQuoteConfig(
        spread_bps=spread_bps,
        order_size=1.0,
        max_inventory=10.0,
        tick_size=tick_size,
        lot_size=0.1 if tick_size >= 0.01 else 0.01,
        inventory_skew_strength=1.0,
        min_notional=min_notional,
    )


def _risk_engine(symbol_price: float = 100.0) -> RiskEngine:
    return RiskEngine(
        RiskLimits(
            max_inventory=10.0,
            max_position_value=20.0 * symbol_price,
            max_daily_loss=1_000.0,
            max_open_orders=2,
            max_order_size=2.0,
            max_allowed_spread_bps=1_000.0,
            stale_order_book_ms=10_000,
        )
    )


def test_adaptive_inventory_strategy_skews_long_inventory_lower() -> None:
    book = _book("PF_XBTUSD", bid=100.0, ask=101.0, bid_qty=5.0, ask_qty=5.0)
    strategy = AdaptiveInventoryMicropriceStrategy(
        quote_generator=_quote_generator(),
        config=AdaptiveInventoryStrategyConfig(
            maker_fee_bps=1.0,
            min_expected_edge_bps=0.1,
            adverse_selection_buffer_bps=0.1,
        ),
    )

    flat = strategy.decide(book=book, inventory=0.0, recent_returns=[0.0, 0.0001])
    long = strategy.decide(book=book, inventory=8.0, recent_returns=[0.0, 0.0001])

    assert flat.quote.should_quote
    assert long.quote.should_quote
    assert long.quote.bid_price < flat.quote.bid_price
    assert long.quote.ask_price < flat.quote.ask_price
    assert long.quote.inventory_ratio == pytest.approx(0.8)


def test_adaptive_inventory_strategy_blocks_spread_below_fee_requirement() -> None:
    generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="mid_price",
            quote_placement_mode="join_top_of_book",
            spread=SpreadConfig(
                model="fixed",
                base_spread_bps=1.0,
                min_spread_bps=1.0,
                max_spread_bps=5.0,
            ),
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.01,
            lot_size=0.1,
            min_notional=1.0,
        )
    )
    strategy = AdaptiveInventoryMicropriceStrategy(
        quote_generator=generator,
        config=AdaptiveInventoryStrategyConfig(
            maker_fee_bps=2.0,
            min_expected_edge_bps=0.5,
            adverse_selection_buffer_bps=0.5,
        ),
    )

    decision = strategy.decide(
        book=_book("PF_XBTUSD", bid=100.0, ask=100.01),
        inventory=0.0,
    )

    assert not decision.quote.should_quote
    assert decision.quote.reason == "insufficient adaptive edge after fees"
    assert decision.expected_edge_bps < 0.0


def test_strategy_configs_accept_finite_maker_rebates() -> None:
    assert AdaptiveInventoryStrategyConfig(maker_fee_bps=-0.5).maker_fee_bps == -0.5
    assert DirectionalFlowStrategyConfig(maker_fee_bps=-0.5).maker_fee_bps == -0.5
    assert QueueAwareStrategyConfig(
        order_size=1.0,
        max_inventory=10.0,
        tick_size=0.5,
        lot_size=0.1,
        maker_fee_bps=-0.5,
    ).maker_fee_bps == -0.5
    assert BasisNeutralStrategyConfig(
        quote=_external_quote(),
        maker_fee_bps=-0.5,
    ).maker_fee_bps == -0.5
    assert SyntheticFairValueStrategyConfig(
        quote=_external_quote(),
        maker_fee_bps=-0.5,
    ).maker_fee_bps == -0.5


def test_directional_flow_quotes_bid_for_positive_causal_flow() -> None:
    book = _book("PF_XBTUSD", bid=100.0, ask=101.0, bid_qty=9.0, ask_qty=1.0)
    strategy = DirectionalOneSidedFlowStrategy(
        quote_generator=_quote_generator(),
        config=DirectionalFlowStrategyConfig(
            min_abs_signal=0.2,
            trend_scale_bps=2.0,
            maker_fee_bps=1.0,
            signal_edge_credit_bps=2.0,
        ),
    )

    decision = strategy.decide(
        book=book,
        inventory=0.0,
        recent_returns=[0.00005, 0.00005],
        recent_trades=[
            Trade(
                "PF_XBTUSD",
                price=101.0,
                quantity=2.0,
                timestamp=NOW,
                aggressor_side="buy",
            )
        ],
    )

    assert decision.quote.should_quote
    assert decision.quote.bid_price is not None
    assert decision.quote.ask_price is None
    assert decision.diagnostics["side_reason"] == "positive_flow"
    assert float(decision.diagnostics["flow_score"]) > 0.0


def test_directional_flow_inventory_unwind_overrides_positive_signal() -> None:
    book = _book("PF_XBTUSD", bid=100.0, ask=101.0, bid_qty=9.0, ask_qty=1.0)
    strategy = DirectionalOneSidedFlowStrategy(
        quote_generator=_quote_generator(),
        config=DirectionalFlowStrategyConfig(
            min_abs_signal=0.2,
            trend_scale_bps=2.0,
            inventory_soft_limit_ratio=0.5,
        ),
    )

    decision = strategy.decide(
        book=book,
        inventory=6.0,
        recent_returns=[0.0001],
        recent_trades=[
            Trade(
                "PF_XBTUSD",
                price=101.0,
                quantity=2.0,
                timestamp=NOW,
                aggressor_side="buy",
            )
        ],
    )

    assert decision.quote.should_quote
    assert decision.quote.bid_price is None
    assert decision.quote.ask_price is not None
    assert decision.diagnostics["side_reason"] == "long_inventory_unwind"


def test_queue_aware_strategy_prefers_improve_when_join_queue_is_large() -> None:
    book = _book("PF_XBTUSD", bid=100.0, ask=102.0, bid_qty=20.0, ask_qty=20.0)
    strategy = QueueAwareJoinImproveStrategy(
        QueueAwareStrategyConfig(
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.5,
            lot_size=0.1,
            maker_fee_bps=0.5,
            min_expected_edge_bps=0.1,
            replacement_cost_bps=0.05,
            min_notional=1.0,
        )
    )

    decision = strategy.decide(
        book=book,
        inventory=0.0,
        queue_state=QueueState(
            bid_queue_ahead=20.0,
            ask_queue_ahead=20.0,
            expected_aggressive_sell_qty=1.0,
            expected_aggressive_buy_qty=1.0,
        ),
    )

    assert decision.quote.should_quote
    assert decision.quote.bid_price == pytest.approx(100.5)
    assert decision.quote.ask_price == pytest.approx(101.5)
    assert decision.diagnostics["buy_mode"] == "improve"
    assert decision.diagnostics["sell_mode"] == "improve"
    assert decision.diagnostics["buy_fill_probability"] == pytest.approx(1.0)


def test_queue_fill_probability_falls_with_queue_ahead() -> None:
    strategy = QueueAwareJoinImproveStrategy(
        QueueAwareStrategyConfig(
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.5,
            lot_size=0.1,
            allow_improve=False,
        )
    )
    book = _book("PF_XBTUSD", bid=100.0, ask=102.0)

    short_queue = strategy.decide(
        book=book,
        inventory=0.0,
        queue_state=QueueState(
            bid_queue_ahead=1.0,
            ask_queue_ahead=1.0,
            expected_aggressive_sell_qty=1.0,
            expected_aggressive_buy_qty=1.0,
        ),
    )
    long_queue = strategy.decide(
        book=book,
        inventory=0.0,
        queue_state=QueueState(
            bid_queue_ahead=20.0,
            ask_queue_ahead=20.0,
            expected_aggressive_sell_qty=1.0,
            expected_aggressive_buy_qty=1.0,
        ),
    )

    assert float(short_queue.diagnostics["buy_fill_probability"]) > float(
        long_queue.diagnostics["buy_fill_probability"]
    )


def test_conservative_queue_position_tracks_partial_fills() -> None:
    initial = ConservativeQueuePosition(order_quantity=2.0, queue_ahead=3.0)

    after_first, first_fill = initial.advance(
        traded_quantity=2.0,
        cancelled_ahead=0.5,
    )
    after_second, second_fill = after_first.advance(traded_quantity=2.0)

    assert first_fill == 0.0
    assert after_first.queue_ahead == pytest.approx(0.5)
    assert second_fill == pytest.approx(1.5)
    assert after_second.remaining_quantity == pytest.approx(0.5)
    assert after_second.filled_quantity == pytest.approx(1.5)


def test_basis_neutral_strategy_quotes_rich_perpetual_ask_and_hedges_spot() -> None:
    spot = _book("BTC/USD", bid=99.9, ask=100.1, bid_qty=10.0, ask_qty=10.0)
    perpetual = _book("PF_XBTUSD", bid=100.9, ask=101.1, bid_qty=10.0, ask_qty=10.0)
    strategy = FundingBasisNeutralStrategy(
        BasisNeutralStrategyConfig(
            quote=_external_quote(),
            maker_fee_bps=1.0,
            hedge_fee_bps=1.0,
            hedge_slippage_bps=0.5,
            min_expected_edge_bps=0.1,
            min_dislocation_bps=5.0,
        )
    )

    decision = strategy.decide(
        perpetual_book=perpetual,
        hedge_book=spot,
        inventory=0.0,
    )
    hedges = decision.hedges_for_fill(
        fill_side="sell",
        fill_quantity=2.0,
        fill_price=float(decision.quote.ask_price),
    )

    assert decision.quote.should_quote
    assert decision.quote.bid_price is None
    assert decision.quote.ask_price is not None
    assert float(decision.diagnostics["basis_dislocation_bps"]) > 0.0
    assert len(hedges) == 1
    assert hedges[0].symbol == "BTC/USD"
    assert hedges[0].side == "buy"
    assert hedges[0].quantity == pytest.approx(2.0)


def test_basis_neutral_strategy_rejects_unsynchronized_books() -> None:
    spot = _book("BTC/USD", bid=99.9, ask=100.1, timestamp=NOW)
    perpetual = _book(
        "PF_XBTUSD",
        bid=100.9,
        ask=101.1,
        timestamp=NOW + timedelta(seconds=2),
    )
    strategy = FundingBasisNeutralStrategy(
        BasisNeutralStrategyConfig(
            quote=_external_quote(),
            max_book_time_skew_ms=500,
        )
    )

    decision = strategy.decide(
        perpetual_book=perpetual,
        hedge_book=spot,
        inventory=0.0,
    )

    assert not decision.quote.should_quote
    assert decision.quote.reason == "basis books are not synchronized"
    assert decision.diagnostics["synchronized"] is False


def test_synthetic_strategy_quotes_rich_cross_ask_and_builds_two_leg_hedge() -> None:
    target = _book(
        "ETH/BTC",
        bid=0.0519,
        ask=0.0521,
        bid_qty=20.0,
        ask_qty=20.0,
    )
    numerator = _book("ETH/USD", bid=1_999.0, ask=2_001.0, bid_qty=20.0, ask_qty=20.0)
    denominator = _book("BTC/USD", bid=39_990.0, ask=40_010.0, bid_qty=20.0, ask_qty=20.0)
    strategy = CrossPairSyntheticFairValueStrategy(
        SyntheticFairValueStrategyConfig(
            quote=_external_quote(
                spread_bps=20.0,
                tick_size=0.0001,
                min_notional=0.001,
            ),
            maker_fee_bps=1.0,
            aggregate_hedge_cost_bps=1.0,
            min_expected_edge_bps=0.1,
            min_dislocation_bps=5.0,
            max_abs_dislocation_bps=1_000.0,
        )
    )

    decision = strategy.decide(
        target_book=target,
        numerator_book=numerator,
        denominator_book=denominator,
        inventory=0.0,
    )
    fill_price = float(decision.quote.ask_price)
    hedges = decision.hedges_for_fill(
        fill_side="sell",
        fill_quantity=2.0,
        fill_price=fill_price,
    )

    assert decision.quote.should_quote
    assert decision.quote.bid_price is None
    assert decision.quote.ask_price is not None
    assert decision.quote.fair_price == pytest.approx(0.05)
    assert len(hedges) == 2
    assert [(hedge.symbol, hedge.side) for hedge in hedges] == [
        ("ETH/USD", "buy"),
        ("BTC/USD", "sell"),
    ]
    assert hedges[0].quantity == pytest.approx(2.0)
    assert hedges[1].quantity == pytest.approx(2.0 * fill_price)


def test_synthetic_strategy_rejects_excessive_cross_dislocation() -> None:
    target = _book("ETH/BTC", bid=0.0599, ask=0.0601)
    numerator = _book("ETH/USD", bid=1_999.0, ask=2_001.0)
    denominator = _book("BTC/USD", bid=39_990.0, ask=40_010.0)
    strategy = CrossPairSyntheticFairValueStrategy(
        SyntheticFairValueStrategyConfig(
            quote=_external_quote(
                spread_bps=20.0,
                tick_size=0.0001,
                min_notional=0.001,
            ),
            max_abs_dislocation_bps=500.0,
        )
    )

    decision = strategy.decide(
        target_book=target,
        numerator_book=numerator,
        denominator_book=denominator,
        inventory=0.0,
    )

    assert not decision.quote.should_quote
    assert decision.quote.reason == "synthetic dislocation exceeds safety limit"


def test_all_strategy_quotes_pass_existing_risk_gate_when_valid() -> None:
    book = _book("PF_XBTUSD", bid=100.0, ask=102.0, bid_qty=20.0, ask_qty=20.0)
    adaptive = AdaptiveInventoryMicropriceStrategy(
        quote_generator=_quote_generator(),
        config=AdaptiveInventoryStrategyConfig(),
    ).decide(book=book, inventory=0.0)
    queue = QueueAwareJoinImproveStrategy(
        QueueAwareStrategyConfig(
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.5,
            lot_size=0.1,
        )
    ).decide(
        book=book,
        inventory=0.0,
        queue_state=QueueState(
            bid_queue_ahead=1.0,
            ask_queue_ahead=1.0,
            expected_aggressive_sell_qty=2.0,
            expected_aggressive_buy_qty=2.0,
        ),
    )

    for decision in (adaptive, queue):
        engine = PaperMarketMakingEngine(risk_engine=_risk_engine(), maker_fee_bps=0.0)
        assert decision.quote.should_quote
        assert engine.place_quote(quote=decision.quote, book=book, now=NOW)


def test_strategy_suite_smoke_is_deterministic_and_json_serializable() -> None:
    first = run_strategy_suite()
    second = run_strategy_suite()

    assert first == second
    assert set(first) == {
        "adaptive_inventory_microprice",
        "directional_one_sided_flow",
        "queue_aware_join_improve",
        "funding_basis_neutral",
        "cross_pair_synthetic_fair_value",
    }
    assert all(result["should_quote"] for result in first.values())
    assert all(result["risk_allowed"] for result in first.values())
    assert json.loads(json.dumps(first)) == first


def test_strategy_yaml_configs_are_self_contained_and_research_only() -> None:
    assert len(DEFAULT_STRATEGY_CONFIGS) == 5

    configs = [load_strategy_config(path) for path in DEFAULT_STRATEGY_CONFIGS]

    assert {config["strategy"]["type"] for config in configs} == {
        "adaptive_inventory_microprice",
        "directional_one_sided_flow",
        "queue_aware_join_improve",
        "funding_basis_neutral",
        "cross_pair_synthetic_fair_value",
    }
    for path, config in zip(DEFAULT_STRATEGY_CONFIGS, configs, strict=True):
        assert "extends:" not in path.read_text(encoding="utf-8")
        assert config["experiment"]["research_only"] is True
        assert config["execution"]["mode"] == "research_smoke"
        assert config["execution"]["allow_order_submission"] is False


def test_strategy_yaml_loader_rejects_unknown_parameters() -> None:
    config = deepcopy(load_strategy_config(DEFAULT_STRATEGY_CONFIGS[0]))
    config["strategy"]["parameters"]["future_only_alpha"] = 1.0

    with pytest.raises(ValueError, match="unsupported"):
        run_strategy_config(config)


def test_directional_yaml_rejects_future_trade_input() -> None:
    config = deepcopy(load_strategy_config(DEFAULT_STRATEGY_CONFIGS[1]))
    config["scenario"]["trades"][0]["timestamp"] = "2026-07-17T12:00:01+00:00"

    with pytest.raises(ValueError, match="cannot be after scenario.timestamp"):
        run_strategy_config(config)
