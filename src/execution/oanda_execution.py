from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
import time
from typing import Any, Mapping, Protocol
from urllib import error, parse, request

import pandas as pd

from src.execution.broker_base import BrokerBase
from src.execution.exceptions import (
    AuthenticationError,
    ConnectionLost,
    OrderRejected,
    RateLimitExceeded,
    SymbolNotFound,
)
from src.execution.models import AccountSnapshot, Order, OrderResult, Position, PriceTick, SymbolInfo, SymbolMapping


_LOGGER = logging.getLogger(__name__)

_ENVIRONMENT_URLS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}

_TIMEFRAME_TO_GRANULARITY = {
    "M1": "M1",
    "M5": "M5",
    "M15": "M15",
    "M30": "M30",
    "H1": "H1",
    "H4": "H4",
    "D1": "D",
}

_DEFAULT_SYMBOLS = {
    "SPX500": "US500_USD",
    "US100": "NAS100_USD",
    "GER40": "DE30_EUR",
    "US30": "US30_USD",
    "XAUUSD": "XAU_USD",
    "EURUSD": "EUR_USD",
    "GBPUSD": "GBP_USD",
    "USDJPY": "USD_JPY",
    "BTCUSD": "BTC_USD",
}


class OandaTransport(Protocol):
    """HTTP transport boundary used to keep tests independent from live OANDA."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        timeout: float,
    ) -> dict[str, Any]:
        """Execute an HTTP request and return decoded JSON."""


class UrllibOandaTransport:
    """Small stdlib transport for OANDA v20 REST calls."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        timeout: float,
    ) -> dict[str, Any]:
        if params:
            query = parse.urlencode({key: value for key, value in params.items() if value is not None})
            url = f"{url}?{query}"
        data = None
        request_headers = dict(headers)
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        http_request = request.Request(url, data=data, headers=request_headers, method=method.upper())
        try:
            with request.urlopen(http_request, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
        except error.HTTPError as exc:
            payload = exc.read().decode("utf-8")
            decoded = _decode_json(payload)
            decoded["_http_status"] = exc.code
            return decoded
        except error.URLError as exc:
            raise ConnectionLost(str(exc)) from exc
        return _decode_json(payload)


@dataclass(frozen=True)
class OandaConfig:
    """Validated OANDA execution settings."""

    environment: str = "practice"
    account_id: str = ""
    api_token: str = ""
    request_timeout: float = 30.0
    reconnect: bool = True
    max_retry: int = 5
    min_request_interval: float = 0.0
    symbols: dict[str, SymbolMapping] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "OandaConfig":
        cfg = dict(raw)
        token = str(cfg.get("api_token") or "")
        token_env = cfg.get("api_token_env")
        if not token and token_env:
            token = str(os.getenv(str(token_env)) or "")
        symbols = _parse_symbol_mappings(cfg.get("symbols"))
        return cls(
            environment=str(cfg.get("environment", "practice")).lower(),
            account_id=str(cfg.get("account_id") or ""),
            api_token=token,
            request_timeout=float(cfg.get("request_timeout", 30)),
            reconnect=bool(cfg.get("reconnect", True)),
            max_retry=int(cfg.get("max_retry", 5)),
            min_request_interval=float(cfg.get("min_request_interval", 0.0)),
            symbols=symbols,
        )


class OandaExecution(BrokerBase):
    """Broker adapter for the OANDA v20 REST API."""

    def __init__(
        self,
        config: Mapping[str, Any] | OandaConfig,
        *,
        transport: OandaTransport | None = None,
        logger: logging.Logger | None = None,
        sleep_fn: Any = time.sleep,
    ) -> None:
        self.config = config if isinstance(config, OandaConfig) else OandaConfig.from_mapping(config)
        self.transport = transport or UrllibOandaTransport()
        self.logger = logger or _LOGGER
        self._sleep = sleep_fn
        self._connected = False
        self._last_request_at = 0.0
        self._account_cache: AccountSnapshot | None = None
        if self.config.environment not in _ENVIRONMENT_URLS:
            raise ValueError("oanda.environment must be 'practice' or 'live'.")
        if not self.config.account_id:
            raise AuthenticationError("oanda.account_id is required.")
        if not self.config.api_token:
            raise AuthenticationError("oanda.api_token or oanda.api_token_env is required.")

    def connect(self) -> None:
        self.logger.info("Connecting to OANDA")
        self._account_cache = self.account_info()
        self._connected = True
        self.logger.info("Connected to OANDA")

    def disconnect(self) -> None:
        self._connected = False
        self._account_cache = None

    def account_info(self) -> AccountSnapshot:
        payload = self._request("GET", f"/v3/accounts/{self.config.account_id}/summary")
        account = dict(payload.get("account", {}) or {})
        snapshot = AccountSnapshot(
            broker="oanda",
            account_id=str(account.get("id", self.config.account_id)),
            balance=_to_float(account.get("balance")),
            equity=_to_float(account.get("NAV")),
            margin_used=_to_float(account.get("marginUsed")),
            raw=account,
        )
        self._account_cache = snapshot
        return snapshot

    def get_balance(self) -> float | None:
        return (self._account_cache or self.account_info()).balance

    def get_equity(self) -> float | None:
        return (self._account_cache or self.account_info()).equity

    def get_margin(self) -> float | None:
        return (self._account_cache or self.account_info()).margin_used

    def get_positions(self) -> list[Position]:
        payload = self._request("GET", f"/v3/accounts/{self.config.account_id}/openPositions")
        positions: list[Position] = []
        for raw in payload.get("positions", []) or []:
            instrument = str(raw.get("instrument", ""))
            framework_symbol = self._from_broker_symbol(instrument)
            long_units = _to_float((raw.get("long") or {}).get("units")) or 0.0
            short_units = _to_float((raw.get("short") or {}).get("units")) or 0.0
            if long_units:
                positions.append(_position_from_oanda(raw, framework_symbol, instrument, "long", long_units))
            if short_units:
                positions.append(_position_from_oanda(raw, framework_symbol, instrument, "short", short_units))
        return positions

    def get_orders(self) -> list[Order]:
        payload = self._request("GET", f"/v3/accounts/{self.config.account_id}/pendingOrders")
        return [self._order_from_oanda(raw) for raw in payload.get("orders", []) or []]

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        broker_symbol = self._to_broker_symbol(symbol)
        payload = self._request(
            "GET",
            f"/v3/accounts/{self.config.account_id}/instruments",
            params={"instruments": broker_symbol},
        )
        instruments = payload.get("instruments", []) or []
        if not instruments:
            raise SymbolNotFound(f"OANDA instrument not found for {symbol!r}.")
        raw = dict(instruments[0])
        return SymbolInfo(
            symbol=symbol,
            broker_symbol=broker_symbol,
            display_name=raw.get("displayName"),
            pip_location=_to_int(raw.get("pipLocation")),
            margin_rate=_to_float(raw.get("marginRate")),
            minimum_trade_size=_to_float(raw.get("minimumTradeSize")),
            maximum_order_units=_to_float(raw.get("maximumOrderUnits")),
            raw=raw,
        )

    def get_latest_price(self, symbol: str) -> PriceTick:
        broker_symbol = self._to_broker_symbol(symbol)
        payload = self._request(
            "GET",
            f"/v3/accounts/{self.config.account_id}/pricing",
            params={"instruments": broker_symbol},
        )
        prices = payload.get("prices", []) or []
        if not prices:
            raise SymbolNotFound(f"OANDA price not found for {symbol!r}.")
        raw = dict(prices[0])
        bid = _first_price(raw.get("bids"))
        ask = _first_price(raw.get("asks"))
        return PriceTick(
            symbol=symbol,
            broker_symbol=broker_symbol,
            bid=bid,
            ask=ask,
            time=_parse_oanda_time(raw.get("time")),
            raw=raw,
        )

    def get_historical_bars(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        if int(count) <= 0:
            raise ValueError("count must be positive.")
        broker_symbol = self._to_broker_symbol(symbol)
        granularity = self._granularity(timeframe)
        self.logger.info("Downloading candles for %s timeframe=%s count=%s", broker_symbol, timeframe, count)
        payload = self._request(
            "GET",
            f"/v3/instruments/{broker_symbol}/candles",
            params={"granularity": granularity, "count": int(count), "price": "M"},
        )
        rows: list[dict[str, Any]] = []
        for candle in payload.get("candles", []) or []:
            if candle.get("complete") is False:
                continue
            mid = candle.get("mid") or {}
            rows.append(
                {
                    "datetime": pd.to_datetime(candle.get("time"), utc=True),
                    "open": _to_float(mid.get("o")),
                    "high": _to_float(mid.get("h")),
                    "low": _to_float(mid.get("l")),
                    "close": _to_float(mid.get("c")),
                    "volume": _to_float(candle.get("volume")) or 0.0,
                }
            )
        return pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "volume"])

    def place_market_order(self, **kwargs: Any) -> OrderResult:
        self.logger.info("Submitting %s market order for %s", str(kwargs.get("side", "")).upper(), kwargs.get("symbol"))
        order = self._base_order_payload(kwargs, order_type="MARKET")
        return self._submit_order(order)

    def place_limit_order(self, **kwargs: Any) -> OrderResult:
        self.logger.info("Submitting %s limit order for %s", str(kwargs.get("side", "")).upper(), kwargs.get("symbol"))
        order = self._base_order_payload(kwargs, order_type="LIMIT")
        order["price"] = _required_str(kwargs, "price")
        order["timeInForce"] = str(kwargs.get("time_in_force", "GTC"))
        return self._submit_order(order)

    def place_stop_order(self, **kwargs: Any) -> OrderResult:
        self.logger.info("Submitting %s stop order for %s", str(kwargs.get("side", "")).upper(), kwargs.get("symbol"))
        order = self._base_order_payload(kwargs, order_type="STOP")
        order["price"] = _required_str(kwargs, "price")
        order["timeInForce"] = str(kwargs.get("time_in_force", "GTC"))
        return self._submit_order(order)

    def modify_order(self, order_id: str, **kwargs: Any) -> OrderResult:
        order = {key: value for key, value in kwargs.items() if value is not None}
        payload = self._request("PUT", f"/v3/accounts/{self.config.account_id}/orders/{order_id}", json_body={"order": order})
        return _order_result(payload)

    def cancel_order(self, order_id: str) -> OrderResult:
        payload = self._request("PUT", f"/v3/accounts/{self.config.account_id}/orders/{order_id}/cancel")
        return _order_result(payload)

    def close_position(self, symbol: str, **kwargs: Any) -> OrderResult:
        broker_symbol = self._to_broker_symbol(symbol)
        units = kwargs.get("units", "ALL")
        side = str(kwargs.get("side", "both")).lower()
        body: dict[str, Any] = {}
        if side in {"long", "buy", "both"}:
            body["longUnits"] = str(units)
        if side in {"short", "sell", "both"}:
            body["shortUnits"] = str(units)
        self.logger.info("Position closed for %s side=%s units=%s", broker_symbol, side, units)
        payload = self._request("PUT", f"/v3/accounts/{self.config.account_id}/positions/{broker_symbol}/close", json_body=body)
        return _order_result(payload)

    def close_all_positions(self) -> list[OrderResult]:
        results: list[OrderResult] = []
        for position in self.get_positions():
            results.append(self.close_position(position.symbol, side=position.side, units="ALL"))
        return results

    def is_connected(self) -> bool:
        return self._connected

    def _submit_order(self, order: dict[str, Any]) -> OrderResult:
        payload = self._request("POST", f"/v3/accounts/{self.config.account_id}/orders", json_body={"order": order})
        result = _order_result(payload)
        if not result.accepted:
            raise OrderRejected(f"OANDA order rejected: {payload}")
        self.logger.info("Order accepted")
        return result

    def _base_order_payload(self, kwargs: Mapping[str, Any], *, order_type: str) -> dict[str, Any]:
        symbol = str(kwargs.get("symbol") or "")
        broker_symbol = self._to_broker_symbol(symbol)
        side = str(kwargs.get("side") or "").lower()
        units = float(kwargs.get("units", kwargs.get("volume", 0.0)) or 0.0)
        if side not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'.")
        if units <= 0.0:
            raise ValueError("units or volume must be positive.")
        signed_units = units if side == "buy" else -units
        order: dict[str, Any] = {
            "type": order_type,
            "instrument": broker_symbol,
            "units": _format_units(signed_units),
            "positionFill": str(kwargs.get("position_fill", "DEFAULT")),
        }
        if order_type == "MARKET":
            order["timeInForce"] = str(kwargs.get("time_in_force", "FOK"))
        _attach_dependent_orders(order, kwargs)
        return order

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        retries = max(1, self.config.max_retry)
        last_exc: Exception | None = None
        for attempt in range(1, retries + 1):
            self._rate_limit()
            try:
                response = self.transport.request(
                    method,
                    self._url(path),
                    headers=self._headers(),
                    json_body=json_body,
                    params=params,
                    timeout=self.config.request_timeout,
                )
                status = _to_int(response.get("_http_status"))
                if status in {401, 403}:
                    raise AuthenticationError(f"OANDA authentication failed: {response}")
                if status == 429:
                    raise RateLimitExceeded(f"OANDA rate limit exceeded: {response}")
                if status is not None and status >= 400:
                    if "order" in path:
                        raise OrderRejected(f"OANDA order rejected: {response}")
                    raise ConnectionLost(f"OANDA request failed status={status}: {response}")
                return response
            except RateLimitExceeded as exc:
                last_exc = exc
                if attempt >= retries:
                    raise
                self.logger.warning("Retrying connection after rate limit attempt=%s", attempt)
                self._sleep(min(2.0 ** attempt, 30.0))
            except ConnectionLost as exc:
                last_exc = exc
                if not self.config.reconnect or attempt >= retries:
                    raise
                self._connected = False
                self.logger.warning("Retrying connection attempt=%s", attempt)
                self._sleep(min(2.0 ** attempt, 30.0))
            except AuthenticationError:
                self._connected = False
                raise
        raise ConnectionLost(str(last_exc or "OANDA request failed."))

    def _rate_limit(self) -> None:
        interval = max(0.0, self.config.min_request_interval)
        if interval <= 0.0:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < interval:
            self._sleep(interval - elapsed)
        self._last_request_at = time.monotonic()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config.api_token}", "Accept-Datetime-Format": "RFC3339"}

    def _url(self, path: str) -> str:
        return _ENVIRONMENT_URLS[self.config.environment] + path

    def _to_broker_symbol(self, symbol: str) -> str:
        key = str(symbol).strip()
        mapping = self.config.symbols.get(key)
        if mapping is not None:
            return mapping.broker_symbol
        if key in _DEFAULT_SYMBOLS:
            return _DEFAULT_SYMBOLS[key]
        if "_" in key:
            return key
        raise SymbolNotFound(f"No OANDA symbol mapping configured for {symbol!r}.")

    def _from_broker_symbol(self, broker_symbol: str) -> str:
        for symbol, mapping in self.config.symbols.items():
            if mapping.broker_symbol == broker_symbol:
                return symbol
        for symbol, mapped in _DEFAULT_SYMBOLS.items():
            if mapped == broker_symbol:
                return symbol
        return broker_symbol

    def _granularity(self, timeframe: str) -> str:
        try:
            return _TIMEFRAME_TO_GRANULARITY[str(timeframe).upper()]
        except KeyError as exc:
            raise ValueError(f"Unsupported OANDA timeframe: {timeframe!r}.") from exc

    def _order_from_oanda(self, raw: Mapping[str, Any]) -> Order:
        broker_symbol = str(raw.get("instrument", ""))
        units = _to_float(raw.get("units"))
        return Order(
            id=str(raw.get("id")) if raw.get("id") is not None else None,
            symbol=self._from_broker_symbol(broker_symbol),
            broker_symbol=broker_symbol,
            side="buy" if (units or 0.0) >= 0.0 else "sell",
            order_type=str(raw.get("type", "")).lower(),
            units=units,
            price=_to_float(raw.get("price")),
            state=raw.get("state"),
            raw=dict(raw),
        )


def _parse_symbol_mappings(raw: Any) -> dict[str, SymbolMapping]:
    if raw in (None, ""):
        raw = {symbol: {"oanda_symbol": broker_symbol, "enabled": True} for symbol, broker_symbol in _DEFAULT_SYMBOLS.items()}
    if not isinstance(raw, Mapping):
        raise TypeError("oanda.symbols must be a mapping.")
    parsed: dict[str, SymbolMapping] = {}
    for framework_symbol, cfg in raw.items():
        if not isinstance(cfg, Mapping):
            raise TypeError(f"oanda.symbols.{framework_symbol} must be a mapping.")
        broker_symbol = str(cfg.get("oanda_symbol") or cfg.get("broker_symbol") or cfg.get("symbol") or "").strip()
        if not broker_symbol:
            raise ValueError(f"oanda.symbols.{framework_symbol}.oanda_symbol must be configured.")
        key = str(framework_symbol).strip()
        parsed[key] = SymbolMapping(key, broker_symbol, bool(cfg.get("enabled", True)))
    return parsed


def _position_from_oanda(raw: Mapping[str, Any], symbol: str, broker_symbol: str, side: str, units: float) -> Position:
    side_raw = raw.get(side) or {}
    return Position(
        id=broker_symbol,
        symbol=symbol,
        broker_symbol=broker_symbol,
        side=side,
        units=abs(units),
        average_price=_to_float(side_raw.get("averagePrice")),
        unrealized_pl=_to_float(side_raw.get("unrealizedPL")),
        raw=dict(raw),
    )


def _attach_dependent_orders(order: dict[str, Any], kwargs: Mapping[str, Any]) -> None:
    if kwargs.get("take_profit") is not None:
        order["takeProfitOnFill"] = {"price": str(kwargs["take_profit"])}
    if kwargs.get("stop_loss") is not None:
        order["stopLossOnFill"] = {"price": str(kwargs["stop_loss"])}
    if kwargs.get("trailing_stop_distance") is not None:
        order["trailingStopLossOnFill"] = {"distance": str(kwargs["trailing_stop_distance"])}


def _order_result(payload: Mapping[str, Any]) -> OrderResult:
    raw = dict(payload)
    create = raw.get("orderCreateTransaction") or raw.get("orderFillTransaction") or raw.get("orderCancelTransaction") or {}
    fill = raw.get("orderFillTransaction") or {}
    reject = raw.get("orderRejectTransaction") or raw.get("orderCancelRejectTransaction")
    return OrderResult(
        accepted=reject is None,
        order_id=str(create.get("id")) if create.get("id") is not None else None,
        trade_id=str(fill.get("id")) if fill.get("id") is not None else None,
        status="rejected" if reject is not None else "accepted",
        raw=raw,
    )


def _decode_json(payload: str) -> dict[str, Any]:
    if not payload:
        return {}
    decoded = json.loads(payload)
    return decoded if isinstance(decoded, dict) else {"data": decoded}


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_price(levels: Any) -> float | None:
    if not levels:
        return None
    first = levels[0]
    return _to_float(first.get("price") if isinstance(first, Mapping) else None)


def _parse_oanda_time(value: Any) -> datetime | None:
    if not value:
        return None
    raw = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw).astimezone(timezone.utc)
    except ValueError:
        return None


def _required_str(kwargs: Mapping[str, Any], key: str) -> str:
    if kwargs.get(key) in (None, ""):
        raise ValueError(f"{key} is required.")
    return str(kwargs[key])


def _format_units(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)


__all__ = ["OandaConfig", "OandaExecution", "OandaTransport", "UrllibOandaTransport"]
