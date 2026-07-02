from __future__ import annotations

from src.market_data.order_book import LocalOrderBook
from src.market_making.quote_generator import QuoteGenerator, QuoteGeneratorConfig
from src.market_making.spread_model import SpreadConfig


def _book() -> LocalOrderBook:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(bids=[(100.0, 2.0)], asks=[(101.0, 2.0)])
    return book


def test_quote_is_around_fair_price_with_tick_rounding() -> None:
    generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="mid_price",
            quote_placement_mode="fair_price_bps",
            spread=SpreadConfig(model="fixed", base_spread_bps=100, min_spread_bps=100, max_spread_bps=100),
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.25,
            lot_size=0.1,
            min_notional=1.0,
        )
    )

    quote = generator.generate(book=_book(), inventory=0.0)

    assert quote.should_quote
    assert quote.fair_price == 100.5
    assert quote.bid_price == 99.75
    assert quote.ask_price == 101.25
    assert quote.bid_size == 1.0


def test_join_top_of_book_quotes_at_best_bid_and_best_ask() -> None:
    generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="mid_price",
            quote_placement_mode="join_top_of_book",
            spread=SpreadConfig(model="fixed", base_spread_bps=100, min_spread_bps=100, max_spread_bps=100),
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.25,
            lot_size=0.1,
            min_notional=1.0,
        )
    )

    quote = generator.generate(book=_book(), inventory=10.0)

    assert quote.should_quote
    assert quote.bid_price == 100.0
    assert quote.ask_price == 101.0
    assert quote.fair_price == 100.5
    assert quote.spread_bps == 1.0 / 100.5 * 10_000.0


def test_improve_top_of_book_quotes_inside_spread_when_there_is_room() -> None:
    generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="mid_price",
            quote_placement_mode="improve_top_of_book",
            spread=SpreadConfig(model="fixed", base_spread_bps=100, min_spread_bps=100, max_spread_bps=100),
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.25,
            lot_size=0.1,
            min_notional=1.0,
        )
    )

    quote = generator.generate(book=_book(), inventory=0.0)

    assert quote.should_quote
    assert quote.bid_price == 100.25
    assert quote.ask_price == 100.75


def test_improve_top_of_book_falls_back_to_join_when_it_would_cross() -> None:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(bids=[(100.0, 2.0)], asks=[(100.5, 2.0)])
    generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="mid_price",
            quote_placement_mode="improve_top_of_book",
            spread=SpreadConfig(model="fixed", base_spread_bps=100, min_spread_bps=100, max_spread_bps=100),
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.5,
            lot_size=0.1,
            min_notional=1.0,
        )
    )

    quote = generator.generate(book=book, inventory=0.0)

    assert quote.should_quote
    assert quote.bid_price == 100.0
    assert quote.ask_price == 100.5


def test_positive_inventory_skews_quotes_lower() -> None:
    generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="mid_price",
            quote_placement_mode="fair_price_bps",
            spread=SpreadConfig(model="fixed", base_spread_bps=100, min_spread_bps=100, max_spread_bps=100),
            inventory_skew_strength=1.0,
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.01,
            lot_size=0.1,
            min_notional=1.0,
        )
    )

    flat_quote = generator.generate(book=_book(), inventory=0.0)
    long_quote = generator.generate(book=_book(), inventory=10.0)

    assert long_quote.bid_price < flat_quote.bid_price
    assert long_quote.ask_price < flat_quote.ask_price
    assert long_quote.inventory_ratio == 1.0


def test_top_of_book_mode_does_not_apply_inventory_skew() -> None:
    generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model="mid_price",
            quote_placement_mode="join_top_of_book",
            spread=SpreadConfig(model="fixed", base_spread_bps=100, min_spread_bps=100, max_spread_bps=100),
            inventory_skew_strength=1.0,
            order_size=1.0,
            max_inventory=10.0,
            tick_size=0.01,
            lot_size=0.1,
            min_notional=1.0,
        )
    )

    flat_quote = generator.generate(book=_book(), inventory=0.0)
    long_quote = generator.generate(book=_book(), inventory=10.0)

    assert long_quote.bid_price == flat_quote.bid_price
    assert long_quote.ask_price == flat_quote.ask_price
