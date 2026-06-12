from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


@dataclass(frozen=True)
class PositionSnapshot:
    ticket: int | None
    symbol: str
    side: str
    volume: float
    magic: int | None
    price_open: float | None = None
    sl: float | None = None
    tp: float | None = None
    profit: float | None = None


class MT5PositionManager:
    """Read and filter open positions by MT5 magic number."""

    def __init__(self, connector: Any, *, magic_number: int) -> None:
        self.connector = connector
        self.magic_number = int(magic_number)

    def positions(self, *, mt5_symbol: str | None = None) -> list[PositionSnapshot]:
        raw_positions = self.connector.positions_get(symbol=mt5_symbol)
        snapshots = [self._snapshot(position) for position in raw_positions]
        return [
            position
            for position in snapshots
            if position.magic == self.magic_number
        ]

    def positions_for_symbol(self, mt5_symbol: str) -> list[PositionSnapshot]:
        return [
            position
            for position in self.positions(mt5_symbol=mt5_symbol)
            if position.symbol == mt5_symbol
        ]

    def has_open_position(self, mt5_symbol: str, *, side: str | None = None) -> bool:
        positions = self.positions_for_symbol(mt5_symbol)
        if side is None:
            return bool(positions)
        normalized = str(side).lower()
        return any(position.side == normalized for position in positions)

    def count_for_symbol(self, mt5_symbol: str) -> int:
        return len(self.positions_for_symbol(mt5_symbol))

    def _snapshot(self, position: Any) -> PositionSnapshot:
        type_value = _attr(position, "type")
        side = self._side_from_type(type_value)
        return PositionSnapshot(
            ticket=_optional_int(_attr(position, "ticket")),
            symbol=str(_attr(position, "symbol", "")),
            side=side,
            volume=float(_attr(position, "volume", 0.0) or 0.0),
            magic=_optional_int(_attr(position, "magic")),
            price_open=_optional_float(_attr(position, "price_open")),
            sl=_optional_float(_attr(position, "sl")),
            tp=_optional_float(_attr(position, "tp")),
            profit=_optional_float(_attr(position, "profit")),
        )

    @staticmethod
    def _side_from_type(type_value: Any) -> str:
        if isinstance(type_value, str):
            normalized = type_value.lower()
            if normalized in {"buy", "long"}:
                return "long"
            if normalized in {"sell", "short"}:
                return "short"
        return "long" if type_value == 0 else "short"


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = ["MT5PositionManager", "PositionSnapshot"]
