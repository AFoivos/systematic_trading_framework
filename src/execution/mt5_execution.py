from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from src.execution.broker_base import BrokerBase
from src.execution.exceptions import OrderRejected
from src.execution.models import AccountSnapshot, PriceTick
from src.execution.mt5_connector import MT5Connector


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class MT5Execution(BrokerBase):
    """BrokerBase facade over the existing MT5 connector."""

    def __init__(self, config: Mapping[str, Any], *, connector: MT5Connector | None = None) -> None:
        self.config = dict(config)
        mt5_cfg = dict(self.config.get("mt5", self.config) or {})
        self.connector = connector or MT5Connector(terminal_path=mt5_cfg.get("terminal_path"))
        self._connected = False

    def connect(self) -> None:
        mt5_cfg = dict(self.config.get("mt5", self.config) or {})
        self.connector.initialize()
        if all(mt5_cfg.get(key) for key in ("login", "password", "server")):
            self.connector.login_from_mapping(mt5_cfg)
        else:
            self.connector.login_from_env(
                login_env=str(mt5_cfg.get("login_env", "MT5_LOGIN")),
                password_env=str(mt5_cfg.get("password_env", "MT5_PASSWORD")),
                server_env=str(mt5_cfg.get("server_env", "MT5_SERVER")),
            )
        self._connected = True

    def disconnect(self) -> None:
        self.connector.shutdown()
        self._connected = False

    def account_info(self) -> AccountSnapshot:
        raw = self.connector.account_info()
        return AccountSnapshot(
            broker="mt5",
            account_id=str(_attr(raw, "login", "")),
            balance=_optional_float(_attr(raw, "balance")),
            equity=_optional_float(_attr(raw, "equity")),
            margin_used=_optional_float(_attr(raw, "margin")),
            raw=_object_to_dict(raw),
        )

    def get_balance(self) -> float | None:
        return self.account_info().balance

    def get_equity(self) -> float | None:
        return self.account_info().equity

    def get_margin(self) -> float | None:
        return self.account_info().margin_used

    def get_positions(self) -> list[Any]:
        return self.connector.positions_get()

    def get_orders(self) -> list[Any]:
        orders_get = getattr(self.connector.mt5, "orders_get", None)
        if orders_get is None:
            return []
        raw = orders_get()
        return list(raw or [])

    def get_symbol_info(self, symbol: str) -> Any:
        return self.connector.symbol_info(symbol)

    def get_latest_price(self, symbol: str) -> PriceTick:
        tick = self.connector.symbol_info_tick(symbol)
        return PriceTick(
            symbol=symbol,
            broker_symbol=symbol,
            bid=_optional_float(_attr(tick, "bid")),
            ask=_optional_float(_attr(tick, "ask")),
            raw=_object_to_dict(tick),
        )

    def get_historical_bars(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        frame = self.connector.fetch_candles(symbol=symbol, timeframe=timeframe, count=count, closed_only=True)
        out = frame.reset_index()
        if "time" in out.columns:
            out = out.rename(columns={"time": "datetime"})
        return out[["datetime", "open", "high", "low", "close", "volume"]]

    def place_market_order(self, **kwargs: Any) -> Any:
        request = self.connector.build_market_order_request(**kwargs)
        result = self.connector.order_send(request)
        if not self.connector.is_successful_order(result):
            raise OrderRejected(f"MT5 order rejected: {_object_to_dict(result)}")
        return result

    def place_limit_order(self, **_: Any) -> Any:
        kwargs = dict(_)
        mt5 = self.connector.mt5
        side = str(kwargs.get("side", "")).lower()
        if side not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'.")
        order_type_name = "ORDER_TYPE_BUY_LIMIT" if side == "buy" else "ORDER_TYPE_SELL_LIMIT"
        request = {
            "action": getattr(mt5, "TRADE_ACTION_PENDING"),
            "symbol": str(kwargs["symbol"]),
            "volume": float(kwargs.get("volume", kwargs.get("units"))),
            "type": getattr(mt5, order_type_name),
            "price": float(kwargs["price"]),
            "sl": float(kwargs.get("sl", kwargs.get("stop_loss", 0.0)) or 0.0),
            "tp": float(kwargs.get("tp", kwargs.get("take_profit", 0.0)) or 0.0),
            "deviation": int(kwargs.get("deviation", 20)),
            "magic": int(kwargs.get("magic", 0)),
            "comment": str(kwargs.get("comment", "broker_factory_limit_order")),
            "type_time": getattr(mt5, "ORDER_TIME_GTC", 0),
        }
        filling = getattr(mt5, "ORDER_FILLING_RETURN", None)
        if filling is not None:
            request["type_filling"] = filling
        result = self.connector.order_send(request)
        if not self.connector.is_successful_order(result):
            raise OrderRejected(f"MT5 limit order rejected: {_object_to_dict(result)}")
        return result

    def modify_order(self, order_id: str, **kwargs: Any) -> Any:
        mt5 = self.connector.mt5
        request = {
            "action": getattr(mt5, "TRADE_ACTION_MODIFY"),
            "order": int(order_id),
        }
        for key in ("price", "sl", "tp"):
            if kwargs.get(key) is not None:
                request[key] = float(kwargs[key])
        result = self.connector.order_send(request)
        if not self.connector.is_successful_order(result):
            raise OrderRejected(f"MT5 order modify rejected: {_object_to_dict(result)}")
        return result

    def cancel_order(self, order_id: str) -> Any:
        mt5 = self.connector.mt5
        request = {"action": getattr(mt5, "TRADE_ACTION_REMOVE"), "order": int(order_id)}
        result = self.connector.order_send(request)
        if not self.connector.is_successful_order(result):
            raise OrderRejected(f"MT5 order cancel rejected: {_object_to_dict(result)}")
        return result

    def close_position(self, symbol: str, **kwargs: Any) -> Any:
        side_filter = str(kwargs.get("side", "")).lower()
        max_volume = _optional_float(kwargs.get("volume", kwargs.get("units")))
        results: list[Any] = []
        for position in self.connector.positions_get(symbol=symbol):
            position_side = "buy" if _attr(position, "type") == 0 else "sell"
            if side_filter in {"long", "buy"} and position_side != "buy":
                continue
            if side_filter in {"short", "sell"} and position_side != "sell":
                continue
            results.append(self._close_mt5_position(position, max_volume=max_volume))
        return results

    def close_all_positions(self) -> list[Any]:
        results: list[Any] = []
        for position in self.get_positions():
            result = self._close_mt5_position(position, max_volume=None)
            results.append(result)
        return results

    def is_connected(self) -> bool:
        return self._connected

    def _close_mt5_position(self, position: Any, *, max_volume: float | None) -> Any:
        mt5 = self.connector.mt5
        symbol = str(_attr(position, "symbol"))
        position_type = _attr(position, "type")
        close_side = "sell" if position_type == 0 else "buy"
        tick = self.connector.symbol_info_tick(symbol)
        price = _optional_float(_attr(tick, "bid" if close_side == "sell" else "ask"))
        if price is None:
            raise OrderRejected(f"MT5 close rejected: missing tick for {symbol}")
        position_volume = float(_attr(position, "volume", 0.0) or 0.0)
        volume = min(position_volume, max_volume) if max_volume is not None else position_volume
        request = self.connector.build_market_order_request(
            symbol=symbol,
            side=close_side,
            volume=volume,
            price=price,
            sl=0.0,
            tp=0.0,
            deviation=20,
            magic=int(_attr(position, "magic", 0) or 0),
            comment="broker_factory_close_position",
        )
        request["position"] = int(_attr(position, "ticket"))
        result = self.connector.order_send(request)
        if not self.connector.is_successful_order(result):
            raise OrderRejected(f"MT5 position close rejected: {_object_to_dict(result)}")
        return result


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


__all__ = ["MT5Execution"]
