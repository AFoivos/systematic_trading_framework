from __future__ import annotations

from dataclasses import dataclass
import math
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
        if config.model not in {"fixed", "volatility_adjusted", "fee_aware"}:
            raise ValueError(f"unsupported spread model: {config.model}")
        for name, value in (
            ("base_spread_bps", config.base_spread_bps),
            ("min_spread_bps", config.min_spread_bps),
            ("max_spread_bps", config.max_spread_bps),
            ("maker_fee_bps", config.maker_fee_bps),
            ("taker_fee_bps", config.taker_fee_bps),
            ("volatility_multiplier", config.volatility_multiplier),
        ):
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite.")
        if config.base_spread_bps < 0:
            raise ValueError("base_spread_bps must be >= 0.")
        if config.min_spread_bps < 0 or config.max_spread_bps <= 0:
            raise ValueError("spread bounds must be nonnegative with max_spread_bps > 0.")
        if config.min_spread_bps > config.max_spread_bps:
            raise ValueError("min_spread_bps cannot exceed max_spread_bps.")
        if config.volatility_multiplier < 0:
            raise ValueError("volatility_multiplier must be >= 0.")
        self.config = config

    def compute_spread_bps(self, *, recent_returns: Iterable[float] = ()) -> float:
        spread = float(self.config.base_spread_bps)
        if self.config.model == "volatility_adjusted":
            returns = [float(value) for value in recent_returns]
            if not all(math.isfinite(value) for value in returns):
                raise ValueError("recent_returns must contain only finite values.")
            if len(returns) >= 2:
                spread += pstdev(returns) * 10_000.0 * self.config.volatility_multiplier
        elif self.config.model == "fee_aware":
            spread += max(0.0, self.config.maker_fee_bps * 2.0)
        if self.config.model != "fee_aware":
            spread += max(0.0, self.config.maker_fee_bps)
        return min(max(spread, self.config.min_spread_bps), self.config.max_spread_bps)


__all__ = ["SpreadConfig", "SpreadModel", "SpreadModelName"]
