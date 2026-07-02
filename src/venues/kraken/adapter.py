from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.market_data.order_book import LocalOrderBook


class LiveTradingDisabledError(RuntimeError):
    """Raised whenever unsupported live trading is requested."""


class ExchangeAdapter(ABC):
    """Async exchange adapter interface for order-book driven engines."""

    @abstractmethod
    async def connect(self) -> None:
        """Connect to the exchange transport."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect and release local resources."""

    @abstractmethod
    async def subscribe_order_book(self, symbol: str) -> None:
        """Subscribe to level-2 order book updates."""

    @abstractmethod
    async def subscribe_trades(self, symbol: str) -> None:
        """Subscribe to trade prints."""

    @abstractmethod
    def get_order_book(self, symbol: str) -> LocalOrderBook | None:
        """Return the current local order book for a symbol."""

    @abstractmethod
    async def place_limit_order(self, *, symbol: str, side: str, price: float, quantity: float) -> Any:
        """Place a limit order after risk gates have allowed it."""

    @abstractmethod
    async def cancel_order(self, order_id: str) -> Any:
        """Cancel one order."""

    @abstractmethod
    async def cancel_all_orders(self) -> Any:
        """Cancel all visible open orders."""

    @abstractmethod
    async def get_open_orders(self) -> list[Any]:
        """Return open exchange orders."""

    @abstractmethod
    async def get_positions(self) -> list[Any]:
        """Return exchange positions."""

    @abstractmethod
    async def get_balances(self) -> dict[str, Any]:
        """Return exchange balances."""


__all__ = ["ExchangeAdapter", "LiveTradingDisabledError"]
