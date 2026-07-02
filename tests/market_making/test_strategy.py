from __future__ import annotations

from datetime import datetime, timezone

from src.market_data.order_book import LocalOrderBook
from src.market_data.trades import Trade
from src.market_making.adverse_selection_filter import AdverseSelectionConfig, AdverseSelectionFilter
from src.market_making.quote_generator import QuoteGenerator, QuoteGeneratorConfig
from src.market_making.spread_model import SpreadConfig
from src.market_making.strategy import MarketMakingStrategy


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
