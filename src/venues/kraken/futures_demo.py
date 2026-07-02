from __future__ import annotations

from typing import Any, Literal

from .adapter import ExchangeAdapter, LiveTradingDisabledError
from .schemas import KrakenCredentials
from src.market_data.order_book import LocalOrderBook


ExecutionMode = Literal["data_only", "paper", "kraken_futures_demo", "live"]


class KrakenFuturesDemoAdapter(ExchangeAdapter):
    """
    Safe Kraken Futures Demo adapter scaffold.

    Public data methods are intentionally minimal in this first pass. Demo order methods require
    mode="kraken_futures_demo", allow_demo_orders=True, and credentials from environment variables.
    """

    def __init__(
        self,
        *,
        mode: ExecutionMode,
        allow_demo_orders: bool = False,
        credentials: KrakenCredentials | None = None,
    ) -> None:
        if mode == "live":
            raise LiveTradingDisabledError("Live trading is intentionally disabled.")
        self.mode = mode
        self.allow_demo_orders = bool(allow_demo_orders)
        self.credentials = credentials
        self.connected = False
        self.books: dict[str, LocalOrderBook] = {}

    async def connect(self) -> None:
        """Mark the adapter connected after validating safe mode constraints."""
        if self.mode == "kraken_futures_demo":
            if not self.allow_demo_orders:
                raise PermissionError("Kraken Futures demo orders require allow_demo_orders: true.")
            if self.credentials is None:
                self.credentials = KrakenCredentials.from_env()
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def subscribe_order_book(self, symbol: str) -> None:
        self.books.setdefault(symbol, LocalOrderBook(symbol))

    async def subscribe_trades(self, symbol: str) -> None:
        if symbol not in self.books:
            self.books[symbol] = LocalOrderBook(symbol)

    def get_order_book(self, symbol: str) -> LocalOrderBook | None:
        return self.books.get(symbol)

    async def place_limit_order(self, *, symbol: str, side: str, price: float, quantity: float) -> Any:
        """Submit a demo order placeholder; real REST signing is intentionally left explicit."""
        self._require_demo_orders()
        raise NotImplementedError("Kraken Futures demo REST order placement scaffold is not wired yet.")

    async def cancel_order(self, order_id: str) -> Any:
        self._require_demo_orders()
        raise NotImplementedError("Kraken Futures demo REST cancellation scaffold is not wired yet.")

    async def cancel_all_orders(self) -> Any:
        self._require_demo_orders()
        raise NotImplementedError("Kraken Futures demo REST cancel-all scaffold is not wired yet.")

    async def get_open_orders(self) -> list[Any]:
        return []

    async def get_positions(self) -> list[Any]:
        return []

    async def get_balances(self) -> dict[str, Any]:
        return {}

    def _require_demo_orders(self) -> None:
        if self.mode == "live":
            raise LiveTradingDisabledError("Live trading is intentionally disabled.")
        if self.mode != "kraken_futures_demo":
            raise PermissionError("Order placement is only available in kraken_futures_demo mode.")
        if not self.allow_demo_orders:
            raise PermissionError("Kraken Futures demo orders require allow_demo_orders: true.")
        if self.credentials is None:
            raise RuntimeError("Kraken Futures demo credentials are not loaded.")


__all__ = ["ExecutionMode", "KrakenFuturesDemoAdapter"]
