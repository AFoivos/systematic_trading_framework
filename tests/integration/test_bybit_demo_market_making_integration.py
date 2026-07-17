from __future__ import annotations

from decimal import Decimal
import os

import pytest

from src.venues.bybit.demo_rest_client import BybitCredentials, BybitDemoRestClient


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_BYBIT_DEMO_INTEGRATION_TESTS") != "1"
    or not os.environ.get("BYBIT_DEMO_API_KEY")
    or not os.environ.get("BYBIT_DEMO_API_SECRET"),
    reason="Bybit Demo integration tests are explicitly opt-in.",
)


def test_minimum_demo_post_only_order_is_always_cancelled() -> None:
    client = BybitDemoRestClient(credentials=BybitCredentials.from_env())
    symbol = "BTCUSDT"
    category = "linear"
    try:
        instrument = client.load_instrument(category=category, symbol=symbol)
        book = client.get_market_orderbook(category=category, symbol=symbol, limit=1)
        result = book["result"]
        best_bid = Decimal(str(result["b"][0][0]))
        price = instrument.round_price(best_bid - instrument.tick_size, side="buy")
        quantity = instrument.minimum_valid_quantity(price)
        order_link_id = "mm_integration_b_1"
        client.place_order(
            category=category,
            symbol=symbol,
            side="buy",
            price=instrument.format_decimal(price),
            quantity=instrument.format_decimal(quantity),
            order_link_id=order_link_id,
        )
    finally:
        try:
            client.cancel_all_orders(category=category, symbol=symbol)
        finally:
            client.close()
