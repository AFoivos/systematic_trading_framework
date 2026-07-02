from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LatencySample:
    """Latency sample for event-driven execution paths."""

    name: str
    started_at: datetime
    finished_at: datetime

    @property
    def latency_ms(self) -> float:
        return (self.finished_at - self.started_at).total_seconds() * 1000.0


__all__ = ["LatencySample"]
