from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PnLSnapshot:
    """PnL snapshot shared by market-making monitoring and reports."""

    realized_pnl: float
    unrealized_pnl: float
    fees: float

    @property
    def total_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl


__all__ = ["PnLSnapshot"]
