from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit", "stop"]


@dataclass(frozen=True)
class AccountSnapshot:
    """Normalized broker account state."""

    broker: str
    account_id: str
    balance: float | None = None
    equity: float | None = None
    margin_used: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PriceTick:
    """Normalized bid/ask snapshot."""

    symbol: str
    broker_symbol: str
    bid: float | None
    ask: float | None
    time: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SymbolInfo:
    """Normalized broker instrument metadata."""

    symbol: str
    broker_symbol: str
    display_name: str | None = None
    pip_location: int | None = None
    margin_rate: float | None = None
    minimum_trade_size: float | None = None
    maximum_order_units: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Position:
    """Normalized open position snapshot."""

    id: str | None
    symbol: str
    broker_symbol: str
    side: str
    units: float
    average_price: float | None = None
    unrealized_pl: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Order:
    """Normalized order snapshot."""

    id: str | None
    symbol: str
    broker_symbol: str
    side: str
    order_type: str
    units: float | None = None
    price: float | None = None
    state: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderResult:
    """Normalized result returned by broker order mutations."""

    accepted: bool
    order_id: str | None = None
    trade_id: str | None = None
    status: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SymbolMapping:
    """Framework-to-broker symbol mapping."""

    framework_symbol: str
    broker_symbol: str
    enabled: bool = True


__all__ = [
    "AccountSnapshot",
    "Order",
    "OrderResult",
    "OrderSide",
    "OrderType",
    "Position",
    "PriceTick",
    "SymbolInfo",
    "SymbolMapping",
]
