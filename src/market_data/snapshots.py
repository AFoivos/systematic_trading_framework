from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .order_book import OrderBookSnapshot


def snapshot_to_dict(snapshot: OrderBookSnapshot) -> dict[str, Any]:
    """Convert an order book snapshot into JSON/CSV friendly primitives."""
    data = asdict(snapshot)
    data["timestamp"] = snapshot.timestamp.isoformat()
    return data


__all__ = ["snapshot_to_dict"]
