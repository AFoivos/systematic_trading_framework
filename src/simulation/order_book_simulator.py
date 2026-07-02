from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Literal

from src.market_data.order_book import LocalOrderBook


EventType = Literal["snapshot", "update"]


@dataclass(frozen=True)
class OrderBookEvent:
    """Synthetic order book event used in deterministic tests and paper simulations."""

    event_type: EventType
    bids: list[tuple[float, float]]
    asks: list[tuple[float, float]]
    timestamp: datetime
    sequence: int | None = None


def replay_order_book_events(symbol: str, events: Iterable[OrderBookEvent]) -> LocalOrderBook:
    """Replay synthetic order-book events into a LocalOrderBook."""
    book = LocalOrderBook(symbol)
    for event in events:
        if event.event_type == "snapshot":
            book.apply_snapshot(
                bids=event.bids,
                asks=event.asks,
                timestamp=event.timestamp,
                sequence=event.sequence,
            )
        elif event.event_type == "update":
            book.apply_update(
                bids=event.bids,
                asks=event.asks,
                timestamp=event.timestamp,
                sequence=event.sequence,
            )
        else:
            raise ValueError(f"unsupported event type: {event.event_type}")
    return book


__all__ = ["EventType", "OrderBookEvent", "replay_order_book_events"]
