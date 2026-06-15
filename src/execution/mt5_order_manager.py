from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import math
from typing import Any, Mapping

import pandas as pd

from src.execution.mt5_risk_manager import MT5RiskManager, calculate_position_size


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


@dataclass(frozen=True)
class TradeParameters:
    stop_loss_r: float
    take_profit_r: float
    volatility_col: str | None = None
    deviation_points: int = 20


@dataclass(frozen=True)
class OrderResult:
    status: str
    reason: str | None = None
    request: dict[str, Any] | None = None
    response: dict[str, Any] | None = None
    sent: bool = False
    slippage: float | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.status in {"dry_run", "submitted", "filled"}


class MT5OrderManager:
    """Build and optionally submit MT5 market orders behind explicit safety gates."""

    def __init__(
        self,
        *,
        connector: Any,
        position_manager: Any,
        risk_manager: MT5RiskManager,
        magic_number: int,
        comment: str,
        execution_mode: str,
        dry_run: bool,
    ) -> None:
        self.connector = connector
        self.position_manager = position_manager
        self.risk_manager = risk_manager
        self.magic_number = int(magic_number)
        self.comment = str(comment)
        self.execution_mode = str(execution_mode)
        self.dry_run = bool(dry_run)

    def place_market_order(
        self,
        *,
        framework_symbol: str,
        mt5_symbol: str,
        side: str,
        latest_row: pd.Series | Mapping[str, Any],
        account_info: Any,
        trade_params: TradeParameters,
        now_utc: datetime | None = None,
    ) -> OrderResult:
        normalized_side = str(side).lower()
        position_side = "long" if normalized_side == "buy" else "short"
        if normalized_side not in {"buy", "sell"}:
            return OrderResult("rejected", "unsupported_order_side")
        if self.position_manager.has_open_position(mt5_symbol):
            return OrderResult(
                "rejected",
                "duplicate_position",
                details={"framework_symbol": framework_symbol, "mt5_symbol": mt5_symbol, "side": position_side},
            )

        symbol_info = self.connector.symbol_info(mt5_symbol)
        if symbol_info is None:
            return OrderResult("rejected", "missing_symbol_info", details={"mt5_symbol": mt5_symbol})
        tick = self.connector.symbol_info_tick(mt5_symbol)
        if tick is None:
            return OrderResult("rejected", "missing_symbol_tick", details={"mt5_symbol": mt5_symbol})

        price = _optional_float(_attr(tick, "ask" if normalized_side == "buy" else "bid"))
        bid = _optional_float(_attr(tick, "bid"))
        ask = _optional_float(_attr(tick, "ask"))
        if price is None or price <= 0.0:
            return OrderResult("rejected", "invalid_entry_price", details={"mt5_symbol": mt5_symbol})
        spread_points = _spread_points(symbol_info=symbol_info, bid=bid, ask=ask)
        all_positions = self.position_manager.positions()
        risk_decision = self.risk_manager.evaluate_entry(
            account_equity=float(_attr(account_info, "equity")),
            positions=all_positions,
            mt5_symbol=mt5_symbol,
            side=normalized_side,
            spread_points=spread_points,
            now_utc=now_utc,
            symbol_info=symbol_info,
            entry_price=price,
        )
        if not risk_decision.allowed:
            return OrderResult("rejected", risk_decision.reason, details=risk_decision.details)

        volatility = _resolve_volatility_distance(latest_row, trade_params.volatility_col)
        if volatility is None or volatility <= 0.0:
            return OrderResult(
                "rejected",
                "invalid_volatility_distance",
                details={"volatility_col": trade_params.volatility_col},
            )
        stop_distance = float(trade_params.stop_loss_r) * volatility
        sizing = calculate_position_size(
            equity=float(_attr(account_info, "equity")),
            risk_per_trade=self.risk_manager.config.risk_per_trade,
            stop_distance=stop_distance,
            symbol_info=symbol_info,
        )
        if not sizing.can_trade or sizing.volume is None:
            return OrderResult(
                "rejected",
                sizing.reason or "position_sizing_failed",
                details={
                    "risk_amount": sizing.risk_amount,
                    "risk_per_lot": sizing.risk_per_lot,
                    "raw_volume": sizing.raw_volume,
                    "stop_distance": stop_distance,
                },
            )

        risk_decision = self.risk_manager.evaluate_entry(
            account_equity=float(_attr(account_info, "equity")),
            positions=all_positions,
            mt5_symbol=mt5_symbol,
            side=normalized_side,
            spread_points=spread_points,
            now_utc=now_utc,
            proposed_volume=sizing.volume,
            symbol_info=symbol_info,
            entry_price=price,
        )
        if not risk_decision.allowed:
            return OrderResult("rejected", risk_decision.reason, details=risk_decision.details)

        sl, tp = _sl_tp_prices(
            side=normalized_side,
            entry_price=price,
            stop_distance=stop_distance,
            take_profit_distance=float(trade_params.take_profit_r) * volatility,
            digits=_optional_int(_attr(symbol_info, "digits")),
        )
        request = self.connector.build_market_order_request(
            symbol=mt5_symbol,
            side=normalized_side,
            volume=sizing.volume,
            price=price,
            sl=sl,
            tp=tp,
            deviation=int(trade_params.deviation_points),
            magic=self.magic_number,
            comment=self.comment,
        )

        if self.dry_run or self.execution_mode != "demo_mt5":
            return OrderResult(
                "dry_run",
                "order_send_disabled",
                request=request,
                sent=False,
                details={
                    "framework_symbol": framework_symbol,
                    "entry_price": price,
                    "bid": bid,
                    "ask": ask,
                    "volume": sizing.volume,
                    "risk_amount": sizing.risk_amount,
                    "risk_per_lot": sizing.risk_per_lot,
                    "raw_volume": sizing.raw_volume,
                    "sl": sl,
                    "tp": tp,
                    "spread_points": spread_points,
                    "stop_distance": stop_distance,
                    "volatility_distance": volatility,
                    "volatility_col": trade_params.volatility_col,
                },
            )

        response = self.connector.order_send(request)
        response_dict = _object_to_dict(response)
        slippage = _slippage_estimate(requested_price=price, response=response)
        status = "filled" if self.connector.is_successful_order(response) else "rejected"
        reason = None if status == "filled" else "mt5_order_send_rejected"
        return OrderResult(
            status,
            reason,
            request=request,
            response=response_dict,
            sent=True,
            slippage=slippage,
            details={
                "framework_symbol": framework_symbol,
                "entry_price": price,
                "bid": bid,
                "ask": ask,
                "volume": sizing.volume,
                "risk_amount": sizing.risk_amount,
                "risk_per_lot": sizing.risk_per_lot,
                "raw_volume": sizing.raw_volume,
                "sl": sl,
                "tp": tp,
                "spread_points": spread_points,
                "stop_distance": stop_distance,
                "volatility_distance": volatility,
                "volatility_col": trade_params.volatility_col,
            },
        )


def _spread_points(*, symbol_info: Any, bid: float | None, ask: float | None) -> float | None:
    if bid is not None and ask is not None:
        point = _optional_float(_attr(symbol_info, "point"))
        if point is not None and point > 0.0:
            return (ask - bid) / point
    spread = _optional_float(_attr(symbol_info, "spread"))
    return spread


def _resolve_volatility_distance(row: pd.Series | Mapping[str, Any], volatility_col: str | None) -> float | None:
    if volatility_col:
        return _volatility_value(row, volatility_col)
    keys = list(row.index) if isinstance(row, pd.Series) else list(row.keys())
    atr_cols = sorted(
        str(col)
        for col in keys
        if str(col).startswith("atr_") and "over_price" not in str(col)
    )
    for col in atr_cols:
        value = _volatility_value(row, col)
        if value is not None and value > 0.0:
            return value
    atr_over_price_cols = sorted(str(col) for col in keys if str(col).startswith("atr_over_price"))
    for col in atr_over_price_cols:
        value = _volatility_value(row, col)
        if value is not None and value > 0.0:
            return value
    return None


def _volatility_value(row: pd.Series | Mapping[str, Any], column: str) -> float | None:
    if column not in row:
        return None
    raw_value = _optional_float(row[column])
    if raw_value is None:
        return None
    if "over_price" in column:
        close = _optional_float(row["close"]) if "close" in row else None
        if close is None or close <= 0.0:
            return None
        return raw_value * close
    return raw_value


def _sl_tp_prices(
    *,
    side: str,
    entry_price: float,
    stop_distance: float,
    take_profit_distance: float,
    digits: int | None,
) -> tuple[float, float]:
    if side == "buy":
        sl = entry_price - stop_distance
        tp = entry_price + take_profit_distance
    else:
        sl = entry_price + stop_distance
        tp = entry_price - take_profit_distance
    if digits is None:
        return sl, tp
    return round(sl, digits), round(tp, digits)


def _object_to_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return dict(obj)
    if hasattr(obj, "_asdict"):
        return dict(obj._asdict())
    return {
        name: getattr(obj, name)
        for name in dir(obj)
        if not name.startswith("_") and not callable(getattr(obj, name))
    }


def _slippage_estimate(*, requested_price: float, response: Any) -> float | None:
    fill_price = _optional_float(_attr(response, "price"))
    if fill_price is None:
        return None
    return fill_price - float(requested_price)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = ["MT5OrderManager", "OrderResult", "TradeParameters"]
