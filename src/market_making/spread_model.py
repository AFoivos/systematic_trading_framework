from __future__ import annotations

from dataclasses import dataclass
from statistics import pstdev
from typing import Iterable, Literal


SpreadModelName = Literal["fixed", "volatility_adjusted", "fee_aware"]


@dataclass(frozen=True)
class SpreadConfig:
    """Configuration for initial quote spread models."""

    model: SpreadModelName = "fixed"
    base_spread_bps: float = 8.0
    min_spread_bps: float = 5.0
    max_spread_bps: float = 40.0
    maker_fee_bps: float = 0.0
    taker_fee_bps: float = 0.0
    volatility_multiplier: float = 1.0


class SpreadModel:
    """Compute bounded quote spreads in basis points."""

    def __init__(self, config: SpreadConfig) -> None:
        if config.min_spread_bps < 0 or config.max_spread_bps <= 0:
            raise ValueError("spread bounds must be positive.")
        if config.min_spread_bps > config.max_spread_bps:
            raise ValueError("min_spread_bps cannot exceed max_spread_bps.")
        self.config = config

    def compute_spread_bps(self, *, recent_returns: Iterable[float] = ()) -> float:
        spread = float(self.config.base_spread_bps)
        if self.config.model == "volatility_adjusted":
            returns = [float(value) for value in recent_returns]
            if len(returns) >= 2:
                spread += pstdev(returns) * 10_000.0 * self.config.volatility_multiplier
        elif self.config.model == "fee_aware":
            spread += max(0.0, self.config.maker_fee_bps * 2.0)
        elif self.config.model != "fixed":
            raise ValueError(f"unsupported spread model: {self.config.model}")
        spread += max(0.0, self.config.maker_fee_bps)
        return min(max(spread, self.config.min_spread_bps), self.config.max_spread_bps)


__all__ = ["SpreadConfig", "SpreadModel", "SpreadModelName"]
