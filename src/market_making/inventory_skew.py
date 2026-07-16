from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class InventorySkewConfig:
    """Inventory skew parameters."""

    max_inventory: float
    skew_strength: float = 0.5


class InventorySkew:
    """Shift quotes away from inventory risk while preserving a valid bid/ask order."""

    def __init__(self, config: InventorySkewConfig) -> None:
        if not math.isfinite(float(config.max_inventory)) or config.max_inventory <= 0:
            raise ValueError("max_inventory must be finite and > 0.")
        if not math.isfinite(float(config.skew_strength)) or config.skew_strength < 0:
            raise ValueError("skew_strength must be finite and >= 0.")
        self.config = config

    def normalized_inventory(self, inventory: float) -> float:
        """Return clipped inventory ratio in [-1, 1]."""
        if not math.isfinite(float(inventory)):
            raise ValueError("inventory must be finite.")
        ratio = float(inventory) / self.config.max_inventory
        return min(max(ratio, -1.0), 1.0)

    def reservation_price_shift(self, *, fair_price: float, inventory: float, half_spread: float) -> float:
        """
        Return signed price shift. Positive inventory shifts both quotes lower to encourage sells;
        negative inventory shifts both quotes higher to encourage buys.
        """
        ratio = self.normalized_inventory(inventory)
        return -ratio * abs(half_spread) * float(self.config.skew_strength)


__all__ = ["InventorySkew", "InventorySkewConfig"]
