from __future__ import annotations

from typing import Literal

from src.market_data.order_book import LocalOrderBook


FairPriceModel = Literal["mid_price", "microprice"]


def mid_price(book: LocalOrderBook) -> float:
    """Return top-of-book midpoint."""
    value = book.mid_price
    if value is None:
        raise ValueError("mid price is unavailable without both bid and ask.")
    return value


def microprice(book: LocalOrderBook) -> float:
    """Return volume-weighted top-of-book microprice."""
    bids = book.bids[:1]
    asks = book.asks[:1]
    if not bids or not asks:
        raise ValueError("microprice is unavailable without both bid and ask.")
    bid = bids[0]
    ask = asks[0]
    total_qty = bid.quantity + ask.quantity
    if total_qty <= 0:
        return mid_price(book)
    return (ask.price * bid.quantity + bid.price * ask.quantity) / total_qty


def compute_fair_price(book: LocalOrderBook, model: FairPriceModel = "microprice") -> float:
    """Compute a fair price from the selected initial model."""
    if model == "mid_price":
        return mid_price(book)
    if model == "microprice":
        return microprice(book)
    raise ValueError(f"unsupported fair price model: {model}")


__all__ = ["FairPriceModel", "compute_fair_price", "microprice", "mid_price"]
