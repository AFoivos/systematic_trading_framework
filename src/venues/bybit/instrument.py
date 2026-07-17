from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Any, Mapping


def _decimal(value: object, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except Exception as exc:  # Decimal exposes several implementation-specific errors.
        raise ValueError(f"invalid Bybit instrument {field}: {value!r}") from exc
    if not parsed.is_finite():
        raise ValueError(f"Bybit instrument {field} must be finite.")
    return parsed


@dataclass(frozen=True)
class BybitInstrument:
    """Validated execution constraints returned by V5 instruments-info."""

    symbol: str
    category: str
    status: str
    contract_type: str
    base_coin: str
    quote_coin: str
    settle_coin: str
    tick_size: Decimal
    quantity_step: Decimal
    minimum_order_quantity: Decimal
    minimum_notional: Decimal
    maximum_order_quantity: Decimal
    minimum_price: Decimal
    maximum_price: Decimal

    def __post_init__(self) -> None:
        if self.category != "linear":
            raise ValueError("Bybit market-making currently supports category=linear only.")
        if not self.symbol or self.symbol != self.symbol.upper():
            raise ValueError("Bybit symbol must be non-empty and uppercase.")
        for field in ("tick_size", "quantity_step", "minimum_order_quantity", "maximum_order_quantity"):
            if getattr(self, field) <= 0:
                raise ValueError(f"{field} must be > 0.")
        if self.minimum_notional < 0:
            raise ValueError("minimum_notional must be >= 0.")
        if self.minimum_price <= 0 or self.maximum_price <= self.minimum_price:
            raise ValueError("invalid Bybit instrument price limits.")
        if self.maximum_order_quantity < self.minimum_order_quantity:
            raise ValueError("maximum_order_quantity is below minimum_order_quantity.")

    @classmethod
    def from_api_response(
        cls,
        payload: Mapping[str, Any],
        *,
        expected_symbol: str,
        expected_category: str = "linear",
    ) -> "BybitInstrument":
        if int(payload.get("retCode", -1)) != 0:
            raise ValueError(f"Bybit instruments-info failed: {payload.get('retMsg', 'unknown error')}")
        result = payload.get("result")
        if not isinstance(result, Mapping) or result.get("category") != expected_category:
            raise ValueError("Bybit instruments-info returned the wrong category.")
        rows = result.get("list")
        if not isinstance(rows, list):
            raise ValueError("Bybit instruments-info result.list is missing.")
        row = next(
            (item for item in rows if isinstance(item, Mapping) and item.get("symbol") == expected_symbol),
            None,
        )
        if row is None:
            raise ValueError(f"Bybit instrument {expected_symbol!r} was not returned.")
        price_filter = row.get("priceFilter")
        lot_filter = row.get("lotSizeFilter")
        if not isinstance(price_filter, Mapping) or not isinstance(lot_filter, Mapping):
            raise ValueError("Bybit instrument filters are missing.")
        return cls(
            symbol=str(row.get("symbol", "")),
            category=expected_category,
            status=str(row.get("status", "")),
            contract_type=str(row.get("contractType", "")),
            base_coin=str(row.get("baseCoin", "")),
            quote_coin=str(row.get("quoteCoin", "")),
            settle_coin=str(row.get("settleCoin", "")),
            tick_size=_decimal(price_filter.get("tickSize"), "tickSize"),
            quantity_step=_decimal(lot_filter.get("qtyStep"), "qtyStep"),
            minimum_order_quantity=_decimal(lot_filter.get("minOrderQty"), "minOrderQty"),
            minimum_notional=_decimal(lot_filter.get("minNotionalValue", "0"), "minNotionalValue"),
            maximum_order_quantity=_decimal(lot_filter.get("maxOrderQty"), "maxOrderQty"),
            minimum_price=_decimal(price_filter.get("minPrice"), "minPrice"),
            maximum_price=_decimal(price_filter.get("maxPrice"), "maxPrice"),
        )

    def require_tradable(self) -> None:
        if self.status != "Trading":
            raise RuntimeError(f"Bybit instrument {self.symbol} status is {self.status!r}, not 'Trading'.")
        if self.contract_type and self.contract_type != "LinearPerpetual":
            raise RuntimeError(
                f"Bybit instrument {self.symbol} is {self.contract_type!r}, not LinearPerpetual."
            )

    def round_price(self, value: Decimal | float | str, *, side: str) -> Decimal:
        price = _decimal(value, "price")
        rounding = ROUND_FLOOR if side.lower() in {"buy", "bid"} else ROUND_CEILING
        rounded = (price / self.tick_size).to_integral_value(rounding=rounding) * self.tick_size
        if rounded < self.minimum_price or rounded > self.maximum_price:
            raise ValueError("rounded order price is outside Bybit instrument price limits.")
        return rounded

    def round_quantity(self, value: Decimal | float | str, *, round_up: bool = False) -> Decimal:
        quantity = _decimal(value, "quantity")
        rounding = ROUND_CEILING if round_up else ROUND_FLOOR
        rounded = (quantity / self.quantity_step).to_integral_value(rounding=rounding) * self.quantity_step
        if rounded < self.minimum_order_quantity or rounded > self.maximum_order_quantity:
            raise ValueError("rounded order quantity is outside Bybit instrument limits.")
        return rounded

    def minimum_valid_quantity(
        self,
        reference_price: Decimal | float | str,
        *,
        safety_margin: Decimal | float | str = "1.02",
    ) -> Decimal:
        """Return the smallest step-aligned quantity covering minimum notional plus margin."""
        price = _decimal(reference_price, "reference_price")
        margin = _decimal(safety_margin, "safety_margin")
        if price <= 0 or margin < 1:
            raise ValueError("reference_price must be > 0 and safety_margin must be >= 1.")
        notional_quantity = (self.minimum_notional * margin) / price
        candidate = max(self.minimum_order_quantity, notional_quantity)
        return self.round_quantity(candidate, round_up=True)

    def validate_order(self, *, price: Decimal, quantity: Decimal) -> None:
        if price < self.minimum_price or price > self.maximum_price:
            raise ValueError("order price is outside Bybit instrument limits.")
        if price % self.tick_size != 0:
            raise ValueError("order price is not aligned to tick size.")
        if quantity < self.minimum_order_quantity or quantity > self.maximum_order_quantity:
            raise ValueError("order quantity is outside Bybit instrument limits.")
        if quantity % self.quantity_step != 0:
            raise ValueError("order quantity is not aligned to quantity step.")
        if price * quantity < self.minimum_notional:
            raise ValueError("order notional is below Bybit minimum notional.")

    @staticmethod
    def format_decimal(value: Decimal) -> str:
        return format(value, "f")


__all__ = ["BybitInstrument"]
