from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


AggressorSide = Literal["buy", "sell", "unknown"]


@dataclass(frozen=True)
class Trade:
    """Normalized market trade event."""

    symbol: str
    price: float
    quantity: float
    timestamp: datetime
    aggressor_side: AggressorSide = "unknown"
    trade_id: str | None = None

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise ValueError("trade price must be positive.")
        if self.quantity <= 0:
            raise ValueError("trade quantity must be positive.")


__all__ = ["AggressorSide", "Trade"]
