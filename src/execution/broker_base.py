from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class BrokerBase(ABC):
    """Common execution interface implemented by all broker adapters."""

    @abstractmethod
    def connect(self) -> None:
        """Connect and authenticate with the broker."""

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the broker and release local resources."""

    @abstractmethod
    def account_info(self) -> Any:
        """Return normalized account information."""

    @abstractmethod
    def get_balance(self) -> float | None:
        """Return account balance."""

    @abstractmethod
    def get_equity(self) -> float | None:
        """Return account equity or NAV."""

    @abstractmethod
    def get_margin(self) -> float | None:
        """Return currently used margin."""

    @abstractmethod
    def get_positions(self) -> list[Any]:
        """Return open positions."""

    @abstractmethod
    def get_orders(self) -> list[Any]:
        """Return pending orders."""

    @abstractmethod
    def get_symbol_info(self, symbol: str) -> Any:
        """Return broker instrument metadata for a framework symbol."""

    @abstractmethod
    def get_latest_price(self, symbol: str) -> Any:
        """Return latest broker price for a framework symbol."""

    @abstractmethod
    def get_historical_bars(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        """Return OHLCV bars with datetime, open, high, low, close, volume columns."""

    @abstractmethod
    def place_market_order(self, **kwargs: Any) -> Any:
        """Submit a market order."""

    @abstractmethod
    def place_limit_order(self, **kwargs: Any) -> Any:
        """Submit a limit order."""

    @abstractmethod
    def modify_order(self, order_id: str, **kwargs: Any) -> Any:
        """Modify a pending order."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> Any:
        """Cancel a pending order."""

    @abstractmethod
    def close_position(self, symbol: str, **kwargs: Any) -> Any:
        """Close all or part of a position."""

    @abstractmethod
    def close_all_positions(self) -> list[Any]:
        """Close all open positions visible to the broker account."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Return whether the adapter considers itself connected."""


__all__ = ["BrokerBase"]
