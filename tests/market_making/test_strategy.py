from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.market_data.order_book import LocalOrderBook
from src.market_data.trades import Trade
from src.market_making.adverse_selection_filter import AdverseSelectionConfig, AdverseSelectionFilter
from src.market_making.quote_generator import QuoteGenerator, QuoteGeneratorConfig
from src.market_making.spread_model import SpreadConfig
from src.market_making.strategy import DirectionalFeatureGate, FeeAwareGate, MarketMakingStrategy, SideSelectionGate


def test_adverse_selection_spread_multiplier_widens_quote() -> None:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(bids=[(100.0, 5.0)], asks=[(101.0, 5.0)])
    quote_generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="mid_price",
            spread=SpreadConfig(model="fixed", base_spread_bps=10.0, min_spread_bps=5.0, max_spread_bps=40.0),
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.01,
            lot_size=0.1,
            min_notional=1.0,
        )
    )
    strategy = MarketMakingStrategy(
        quote_generator=quote_generator,
        adverse_filter=AdverseSelectionFilter(AdverseSelectionConfig()),
    )
    recent_trades = [
        Trade("PI_XBTUSD", price=101.0, quantity=1.0, timestamp=datetime.now(timezone.utc), aggressor_side="buy"),
        Trade("PI_XBTUSD", price=101.0, quantity=1.0, timestamp=datetime.now(timezone.utc), aggressor_side="buy"),
    ]

    normal_quote = quote_generator.generate(book=book, inventory=0.0)
    filtered_quote = strategy.decide(book=book, inventory=0.0, recent_trades=recent_trades)

    assert filtered_quote.should_quote
    assert filtered_quote.spread_bps > normal_quote.spread_bps
    assert filtered_quote.bid_price < normal_quote.bid_price
    assert filtered_quote.ask_price > normal_quote.ask_price


def test_fee_aware_gate_rejects_quote_when_spread_does_not_cover_round_trip_costs() -> None:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(bids=[(100.0, 5.0)], asks=[(100.01, 5.0)])
    quote_generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="mid_price",
            quote_placement_mode="join_top_of_book",
            spread=SpreadConfig(model="fixed", base_spread_bps=1.0, min_spread_bps=1.0, max_spread_bps=5.0),
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.01,
            lot_size=0.1,
            min_notional=1.0,
        )
    )
    strategy = MarketMakingStrategy(
        quote_generator=quote_generator,
        fee_aware_gate=FeeAwareGate(
            maker_fee_bps=2.0,
            min_expected_edge_bps=0.1,
            adverse_selection_buffer_bps=0.3,
            inventory_penalty_bps_per_unit=0.25,
        ),
    )

    quote = strategy.decide(book=book, inventory=0.0)

    assert not quote.should_quote
    assert quote.reason == "insufficient edge after fees"


def test_fee_aware_gate_allows_quote_when_spread_covers_required_edge() -> None:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(bids=[(100.0, 5.0)], asks=[(101.0, 5.0)])
    quote_generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="mid_price",
            quote_placement_mode="fair_price_bps",
            spread=SpreadConfig(model="fixed", base_spread_bps=500.0, min_spread_bps=500.0, max_spread_bps=500.0),
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.01,
            lot_size=0.1,
            min_notional=1.0,
        )
    )
    strategy = MarketMakingStrategy(
        quote_generator=quote_generator,
        fee_aware_gate=FeeAwareGate(
            maker_fee_bps=2.0,
            min_expected_edge_bps=0.1,
            adverse_selection_buffer_bps=0.3,
            inventory_penalty_bps_per_unit=0.25,
        ),
    )

    quote = strategy.decide(book=book, inventory=0.0)

    assert quote.should_quote


def test_side_selection_gate_keeps_bid_only_when_fair_price_is_above_mid() -> None:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(bids=[(100.0, 9.0)], asks=[(100.01, 1.0)])
    quote_generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="microprice",
            quote_placement_mode="join_top_of_book",
            spread=SpreadConfig(model="fixed", base_spread_bps=1.0, min_spread_bps=1.0, max_spread_bps=5.0),
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.01,
            lot_size=0.1,
            min_notional=1.0,
        )
    )
    strategy = MarketMakingStrategy(
        quote_generator=quote_generator,
        side_selection_gate=SideSelectionGate(
            microprice_offset_threshold_bps=0.05,
            inventory_soft_limit_ratio=0.2,
        ),
    )

    quote = strategy.decide(book=book, inventory=0.0)

    assert quote.should_quote
    assert quote.bid_price is not None and quote.bid_size > 0
    assert quote.ask_price is None and quote.ask_size == 0.0


def test_side_selection_gate_prefers_inventory_unwind_side() -> None:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(bids=[(100.0, 1.0)], asks=[(100.01, 9.0)])
    quote_generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="microprice",
            quote_placement_mode="join_top_of_book",
            spread=SpreadConfig(model="fixed", base_spread_bps=1.0, min_spread_bps=1.0, max_spread_bps=5.0),
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.01,
            lot_size=0.1,
            min_notional=1.0,
        )
    )
    strategy = MarketMakingStrategy(
        quote_generator=quote_generator,
        side_selection_gate=SideSelectionGate(
            microprice_offset_threshold_bps=0.05,
            inventory_soft_limit_ratio=0.2,
        ),
    )

    quote = strategy.decide(book=book, inventory=3.0)

    assert quote.should_quote
    assert quote.bid_price is None and quote.bid_size == 0.0
    assert quote.ask_price is not None and quote.ask_size > 0


def test_side_selection_gate_can_force_buy_only_mode() -> None:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(bids=[(100.0, 1.0)], asks=[(100.01, 9.0)])
    quote_generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="microprice",
            quote_placement_mode="join_top_of_book",
            spread=SpreadConfig(model="fixed", base_spread_bps=1.0, min_spread_bps=1.0, max_spread_bps=5.0),
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.01,
            lot_size=0.1,
            min_notional=1.0,
        )
    )
    strategy = MarketMakingStrategy(
        quote_generator=quote_generator,
        side_selection_gate=SideSelectionGate(
            microprice_offset_threshold_bps=0.05,
            inventory_soft_limit_ratio=0.2,
            allowed_side_mode="buy_only",
        ),
    )

    quote = strategy.decide(book=book, inventory=3.0)

    assert quote.should_quote
    assert quote.bid_price is not None and quote.bid_size > 0
    assert quote.ask_price is None and quote.ask_size == 0.0


def test_side_selection_gate_buy_only_with_unwind_keeps_bid_below_soft_limit() -> None:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(bids=[(100.0, 9.0)], asks=[(100.01, 1.0)])
    quote_generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="microprice",
            quote_placement_mode="join_top_of_book",
            spread=SpreadConfig(model="fixed", base_spread_bps=1.0, min_spread_bps=1.0, max_spread_bps=5.0),
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.01,
            lot_size=0.1,
            min_notional=1.0,
        )
    )
    strategy = MarketMakingStrategy(
        quote_generator=quote_generator,
        side_selection_gate=SideSelectionGate(
            microprice_offset_threshold_bps=0.05,
            inventory_soft_limit_ratio=0.2,
            allowed_side_mode="buy_only_with_unwind",
        ),
    )

    quote = strategy.decide(book=book, inventory=0.0)

    assert quote.should_quote
    assert quote.bid_price is not None and quote.bid_size > 0
    assert quote.ask_price is None and quote.ask_size == 0.0


def test_side_selection_gate_buy_only_with_unwind_switches_to_ask_above_soft_limit() -> None:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(bids=[(100.0, 9.0)], asks=[(100.01, 1.0)])
    quote_generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="microprice",
            quote_placement_mode="join_top_of_book",
            spread=SpreadConfig(model="fixed", base_spread_bps=1.0, min_spread_bps=1.0, max_spread_bps=5.0),
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.01,
            lot_size=0.1,
            min_notional=1.0,
        )
    )
    strategy = MarketMakingStrategy(
        quote_generator=quote_generator,
        side_selection_gate=SideSelectionGate(
            microprice_offset_threshold_bps=0.05,
            inventory_soft_limit_ratio=0.2,
            allowed_side_mode="buy_only_with_unwind",
        ),
    )

    quote = strategy.decide(book=book, inventory=3.0)

    assert quote.should_quote
    assert quote.bid_price is None and quote.bid_size == 0.0
    assert quote.ask_price is not None and quote.ask_size > 0


def test_directional_feature_gate_grants_edge_credit_for_aligned_one_sided_quote() -> None:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(bids=[(100.0, 9.0)], asks=[(100.01, 1.0)])
    quote_generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="microprice",
            quote_placement_mode="join_top_of_book",
            spread=SpreadConfig(model="fixed", base_spread_bps=1.0, min_spread_bps=1.0, max_spread_bps=5.0),
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.01,
            lot_size=0.1,
            min_notional=1.0,
        )
    )
    strategy = MarketMakingStrategy(
        quote_generator=quote_generator,
        side_selection_gate=SideSelectionGate(
            microprice_offset_threshold_bps=0.05,
            inventory_soft_limit_ratio=0.2,
            allowed_side_mode="buy_only",
        ),
        fee_aware_gate=FeeAwareGate(
            maker_fee_bps=2.0,
            min_expected_edge_bps=0.1,
            adverse_selection_buffer_bps=0.3,
            inventory_penalty_bps_per_unit=0.25,
        ),
        directional_feature_gate=DirectionalFeatureGate(
            microprice_offset_threshold_bps=0.05,
            imbalance_threshold=0.2,
            trend_threshold_bps=0.02,
            max_volatility_bps=0.2,
            edge_credit_bps=2.75,
        ),
    )

    quote = strategy.decide(book=book, inventory=0.0, recent_returns=[0.00001, 0.000015, 0.000005])

    assert quote.should_quote
    assert quote.bid_price is not None and quote.ask_price is None


def test_directional_feature_gate_does_not_override_fee_gate_without_aligned_signal() -> None:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(bids=[(100.0, 9.0)], asks=[(100.01, 1.0)])
    quote_generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="microprice",
            quote_placement_mode="join_top_of_book",
            spread=SpreadConfig(model="fixed", base_spread_bps=1.0, min_spread_bps=1.0, max_spread_bps=5.0),
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.01,
            lot_size=0.1,
            min_notional=1.0,
        )
    )
    strategy = MarketMakingStrategy(
        quote_generator=quote_generator,
        side_selection_gate=SideSelectionGate(
            microprice_offset_threshold_bps=0.05,
            inventory_soft_limit_ratio=0.2,
            allowed_side_mode="buy_only",
        ),
        fee_aware_gate=FeeAwareGate(
            maker_fee_bps=2.0,
            min_expected_edge_bps=0.1,
            adverse_selection_buffer_bps=0.3,
            inventory_penalty_bps_per_unit=0.25,
        ),
        directional_feature_gate=DirectionalFeatureGate(
            microprice_offset_threshold_bps=0.05,
            imbalance_threshold=0.2,
            trend_threshold_bps=0.02,
            max_volatility_bps=0.2,
            edge_credit_bps=2.75,
        ),
    )

    quote = strategy.decide(book=book, inventory=0.0, recent_returns=[-0.00001, -0.000015, -0.000005])

    assert not quote.should_quote
    assert quote.reason == "insufficient edge after fees"


def test_invalid_side_selection_mode_is_rejected_instead_of_failing_open() -> None:
    with pytest.raises(ValueError, match="allowed_side_mode"):
        SideSelectionGate(allowed_side_mode="typo")  # type: ignore[arg-type]


def test_adverse_filter_blocks_non_finite_volatility() -> None:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(bids=[(100.0, 1.0)], asks=[(101.0, 1.0)])
    adverse_filter = AdverseSelectionFilter(AdverseSelectionConfig())

    decision = adverse_filter.evaluate(
        book=book,
        recent_volatility_bps=float("nan"),
    )

    assert not decision.should_quote
    assert decision.reason == "invalid recent volatility"


def test_strategy_passes_recent_return_volatility_to_adverse_filter() -> None:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(bids=[(100.0, 1.0)], asks=[(101.0, 1.0)])
    quote_generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="mid_price",
            spread=SpreadConfig(
                model="fixed",
                base_spread_bps=10.0,
                min_spread_bps=5.0,
                max_spread_bps=40.0,
            ),
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.01,
            lot_size=0.1,
            min_notional=1.0,
        )
    )
    strategy = MarketMakingStrategy(
        quote_generator=quote_generator,
        adverse_filter=AdverseSelectionFilter(
            AdverseSelectionConfig(high_volatility_bps=1.0)
        ),
    )

    quote = strategy.decide(
        book=book,
        inventory=0.0,
        recent_returns=[0.0, 0.001],
    )

    assert not quote.should_quote
    assert quote.reason == "high recent volatility"
