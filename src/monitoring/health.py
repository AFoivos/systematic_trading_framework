from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class HealthStatus:
    """Simple health status for event-driven services."""

    component: str
    ok: bool
    checked_at: datetime
    message: str = "ok"


__all__ = ["HealthStatus"]
