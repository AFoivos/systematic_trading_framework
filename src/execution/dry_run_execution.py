from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from src.execution.broker_base import BrokerBase
from src.execution.models import OrderResult
from src.execution.mt5_execution import MT5Execution


class DryRunExecution(BrokerBase):
    """Read-capable broker facade whose mutation methods never reach a broker."""

    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        read_broker: BrokerBase | None = None,
    ) -> None:
        self.config = dict(config)
        self._read_broker = read_broker or MT5Execution(
            {**self.config, "mode": "dry_run"},
        )

    def connect(self) -> None:
        self._read_broker.connect()

    def disconnect(self) -> None:
        self._read_broker.disconnect()

    def account_info(self) -> Any:
        return self._read_broker.account_info()

    def get_balance(self) -> float | None:
        return self._read_broker.get_balance()

    def get_equity(self) -> float | None:
        return self._read_broker.get_equity()

    def get_margin(self) -> float | None:
        return self._read_broker.get_margin()

    def get_positions(self) -> list[Any]:
        return self._read_broker.get_positions()

    def get_orders(self) -> list[Any]:
        return self._read_broker.get_orders()

    def get_symbol_info(self, symbol: str) -> Any:
        return self._read_broker.get_symbol_info(symbol)

    def get_latest_price(self, symbol: str) -> Any:
        return self._read_broker.get_latest_price(symbol)

    def get_historical_bars(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        return self._read_broker.get_historical_bars(symbol, timeframe, count)

    def place_market_order(self, **kwargs: Any) -> OrderResult:
        return self._simulated_result("market", kwargs)

    def place_limit_order(self, **kwargs: Any) -> OrderResult:
        return self._simulated_result("limit", kwargs)

    def modify_order(self, order_id: str, **kwargs: Any) -> OrderResult:
        return self._simulated_result("modify", {"order_id": order_id, **kwargs})

    def cancel_order(self, order_id: str) -> OrderResult:
        return self._simulated_result("cancel", {"order_id": order_id})

    def close_position(self, symbol: str, **kwargs: Any) -> OrderResult:
        return self._simulated_result("close_position", {"symbol": symbol, **kwargs})

    def close_all_positions(self) -> list[OrderResult]:
        return [self._simulated_result("close_all_positions", {})]

    def is_connected(self) -> bool:
        return self._read_broker.is_connected()

    @staticmethod
    def _simulated_result(operation: str, request: Mapping[str, Any]) -> OrderResult:
        return OrderResult(
            accepted=True,
            status="dry_run",
            raw={
                "operation": operation,
                "request": dict(request),
                "sent": False,
            },
        )


__all__ = ["DryRunExecution"]
