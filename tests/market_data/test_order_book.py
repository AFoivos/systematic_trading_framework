from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.market_data.order_book import LocalOrderBook


def test_snapshot_best_prices_spread_and_imbalance() -> None:
    book = LocalOrderBook("PI_XBTUSD")
    now = datetime.now(timezone.utc)

    book.apply_snapshot(
        bids=[(100.0, 2.0), (99.5, 1.0)],
        asks=[(101.0, 3.0), (101.5, 1.0)],
        timestamp=now,
        sequence=10,
    )

    assert book.best_bid == 100.0
    assert book.best_ask == 101.0
    assert book.mid_price == 100.5
    assert book.spread == 1.0
    assert book.spread_bps == pytest.approx(99.5024875622)
    assert book.imbalance(levels=1) == pytest.approx(2.0 / 5.0)
    assert book.timestamp == now
    assert book.sequence == 10


def test_incremental_updates_remove_zero_or_negative_quantities() -> None:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(bids=[(100.0, 2.0)], asks=[(101.0, 3.0)], sequence=1)

    book.apply_update(bids=[(100.0, 0.0), (99.0, 5.0)], asks=[(101.0, -1.0), (102.0, 2.0)], sequence=2)

    assert book.best_bid == 99.0
    assert book.best_ask == 102.0
    assert book.depth(1)["bids"][0].quantity == 5.0


def test_crossed_book_is_rejected() -> None:
    book = LocalOrderBook("PI_XBTUSD")

    with pytest.raises(ValueError, match="crossed book"):
        book.apply_snapshot(bids=[(101.0, 1.0)], asks=[(100.0, 1.0)])


def test_sequence_must_be_monotonic_when_present() -> None:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(bids=[(100.0, 1.0)], asks=[(101.0, 1.0)], sequence=5)

    with pytest.raises(ValueError, match="monotonic"):
        book.apply_update(bids=[(99.0, 1.0)], sequence=4)
