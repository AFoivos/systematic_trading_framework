from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class SymbolMapping:
    framework_symbol: str
    mt5_symbol: str
    enabled: bool = True


class MT5SymbolMapper:
    """Resolve framework symbols to broker-specific MT5 symbols from config."""

    def __init__(self, mappings: Mapping[str, Mapping[str, Any]]) -> None:
        if not isinstance(mappings, Mapping) or not mappings:
            raise ValueError("symbols config must be a non-empty mapping.")
        parsed: dict[str, SymbolMapping] = {}
        for framework_symbol, raw_mapping in mappings.items():
            if not isinstance(framework_symbol, str) or not framework_symbol.strip():
                raise ValueError("framework symbols must be non-empty strings.")
            if not isinstance(raw_mapping, Mapping):
                raise TypeError(f"symbols.{framework_symbol} must be a mapping.")
            mt5_symbol = str(raw_mapping.get("mt5_symbol", "")).strip()
            if not mt5_symbol:
                raise ValueError(f"symbols.{framework_symbol}.mt5_symbol must be a non-empty string.")
            parsed[framework_symbol.strip()] = SymbolMapping(
                framework_symbol=framework_symbol.strip(),
                mt5_symbol=mt5_symbol,
                enabled=bool(raw_mapping.get("enabled", True)),
            )
        self._mappings = parsed

    @classmethod
    def from_config(cls, symbols_cfg: Mapping[str, Mapping[str, Any]]) -> "MT5SymbolMapper":
        return cls(symbols_cfg)

    def to_mt5(self, framework_symbol: str) -> str:
        mapping = self._mappings.get(str(framework_symbol))
        if mapping is None:
            raise KeyError(f"No MT5 symbol mapping configured for {framework_symbol!r}.")
        return mapping.mt5_symbol

    def is_enabled(self, framework_symbol: str) -> bool:
        mapping = self._mappings.get(str(framework_symbol))
        return bool(mapping.enabled) if mapping is not None else False

    def enabled_symbols(self) -> list[str]:
        return [
            symbol
            for symbol, mapping in self._mappings.items()
            if mapping.enabled
        ]

    def as_dict(self) -> dict[str, dict[str, object]]:
        return {
            symbol: {"mt5_symbol": mapping.mt5_symbol, "enabled": mapping.enabled}
            for symbol, mapping in self._mappings.items()
        }


__all__ = ["MT5SymbolMapper", "SymbolMapping"]
