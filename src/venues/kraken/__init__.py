"""Kraken Futures venue adapter scaffolding."""

from .adapter import ExchangeAdapter, LiveTradingDisabledError
from .futures_demo import KrakenFuturesDemoAdapter
from .schemas import KrakenCredentials

__all__ = [
    "ExchangeAdapter",
    "KrakenCredentials",
    "KrakenFuturesDemoAdapter",
    "LiveTradingDisabledError",
]
