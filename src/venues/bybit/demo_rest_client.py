from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import os
import threading
import time
from typing import Any, Callable, Mapping
from urllib.parse import urlencode, urlparse

import requests

from .instrument import BybitInstrument


DEMO_REST_URL = "https://api-demo.bybit.com"
DEMO_PRIVATE_WS_URL = "wss://stream-demo.bybit.com/v5/private"
PUBLIC_WS_URL = "wss://stream.bybit.com/v5/public/linear"


class BybitAPIError(RuntimeError):
    """A sanitized Bybit transport or business error."""

    def __init__(self, message: str, *, ret_code: int | None = None) -> None:
        super().__init__(message)
        self.ret_code = ret_code


class UncertainOrderState(BybitAPIError):
    """Create request outcome could not be proven after orderLinkId reconciliation."""


@dataclass(frozen=True, repr=False)
class BybitCredentials:
    api_key: str
    api_secret: str = field(repr=False)

    @classmethod
    def from_env(cls) -> "BybitCredentials":
        api_key = os.environ.get("BYBIT_DEMO_API_KEY", "").strip()
        api_secret = os.environ.get("BYBIT_DEMO_API_SECRET", "").strip()
        if not api_key or not api_secret:
            raise RuntimeError(
                "Missing Bybit Demo credentials. Set BYBIT_DEMO_API_KEY and "
                "BYBIT_DEMO_API_SECRET in the environment."
            )
        return cls(api_key=api_key, api_secret=api_secret)

    def __repr__(self) -> str:
        return "BybitCredentials(api_key='***', api_secret='***')"


def require_demo_execution_environment(value: str | None = None) -> None:
    actual = os.environ.get("BYBIT_EXECUTION_ENV") if value is None else value
    if actual != "demo":
        raise RuntimeError("BYBIT_EXECUTION_ENV must be explicitly set to 'demo'.")


def validate_demo_rest_url(url: str) -> str:
    parsed = urlparse(str(url))
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api-demo.bybit.com"
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("Fatal safety error: Bybit REST URL must be exactly https://api-demo.bybit.com.")
    return DEMO_REST_URL


def validate_demo_private_ws_url(url: str) -> str:
    parsed = urlparse(str(url))
    if (
        parsed.scheme != "wss"
        or parsed.hostname != "stream-demo.bybit.com"
        or parsed.port is not None
        or parsed.path != "/v5/private"
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError(
            "Fatal safety error: Bybit private WebSocket URL must be exactly "
            "wss://stream-demo.bybit.com/v5/private."
        )
    return DEMO_PRIVATE_WS_URL


def validate_public_ws_url(url: str) -> str:
    parsed = urlparse(str(url))
    if (
        parsed.scheme != "wss"
        or parsed.hostname != "stream.bybit.com"
        or parsed.port is not None
        or parsed.path != "/v5/public/linear"
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError(
            "Bybit public WebSocket URL must be exactly "
            "wss://stream.bybit.com/v5/public/linear."
        )
    return PUBLIC_WS_URL


def sign_rest_payload(
    *,
    timestamp_ms: int,
    api_key: str,
    recv_window_ms: int,
    payload: str,
    api_secret: str,
) -> str:
    message = f"{timestamp_ms}{api_key}{recv_window_ms}{payload}"
    return hmac.new(api_secret.encode(), message.encode(), hashlib.sha256).hexdigest()


class RequestRateLimiter:
    def __init__(self, max_requests_per_second: int) -> None:
        if max_requests_per_second <= 0:
            raise ValueError("max_requests_per_second must be > 0.")
        self.max_requests = int(max_requests_per_second)
        self._times: deque[float] = deque()
        self._lock = threading.Lock()

    def wait(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                while self._times and now - self._times[0] >= 1.0:
                    self._times.popleft()
                if len(self._times) < self.max_requests:
                    self._times.append(now)
                    return
                delay = max(0.001, 1.0 - (now - self._times[0]))
            time.sleep(delay)


class BybitDemoRestClient:
    """Small V5 client whose private calls are hard-bound to Bybit Demo REST."""

    def __init__(
        self,
        *,
        credentials: BybitCredentials | None = None,
        base_url: str | None = None,
        recv_window_ms: int = 5_000,
        timeout_seconds: float = 5.0,
        max_requests_per_second: int = 8,
        session: requests.Session | None = None,
        now_ms: Callable[[], int] | None = None,
        latency_callback: Callable[[str, float], None] | None = None,
        error_callback: Callable[[Mapping[str, Any]], None] | None = None,
        success_callback: Callable[[str], None] | None = None,
    ) -> None:
        configured_url = base_url or os.environ.get("BYBIT_DEMO_REST_URL", DEMO_REST_URL)
        self.base_url = validate_demo_rest_url(configured_url)
        if recv_window_ms <= 0 or timeout_seconds <= 0:
            raise ValueError("recv_window_ms and timeout_seconds must be > 0.")
        self.credentials = credentials
        self.recv_window_ms = int(recv_window_ms)
        self.timeout_seconds = float(timeout_seconds)
        self.session = session or requests.Session()
        self._now_ms = now_ms or (lambda: time.time_ns() // 1_000_000)
        self._rate_limiter = RequestRateLimiter(max_requests_per_second)
        self._latency_callback = latency_callback
        self._error_callback = error_callback
        self._success_callback = success_callback

    def close(self) -> None:
        self.session.close()

    def load_instrument(self, *, category: str, symbol: str) -> BybitInstrument:
        payload = self._request(
            "GET",
            "/v5/market/instruments-info",
            params={"category": category, "symbol": symbol},
            authenticated=False,
            retry_safe=True,
        )
        instrument = BybitInstrument.from_api_response(
            payload,
            expected_symbol=symbol,
            expected_category=category,
        )
        instrument.require_tradable()
        return instrument

    def get_market_orderbook(self, *, category: str, symbol: str, limit: int = 1) -> dict[str, Any]:
        return self._request(
            "GET",
            "/v5/market/orderbook",
            params={"category": category, "symbol": symbol, "limit": int(limit)},
            authenticated=False,
            retry_safe=True,
        )

    def get_server_time_ms(self) -> int:
        payload = self._request(
            "GET", "/v5/market/time", authenticated=False, retry_safe=True
        )
        result = payload.get("result", {})
        if isinstance(result, Mapping) and result.get("timeNano"):
            return int(str(result["timeNano"])) // 1_000_000
        if isinstance(result, Mapping) and result.get("timeSecond"):
            return int(str(result["timeSecond"])) * 1_000
        return int(payload.get("time", 0))

    def require_clock_synchronized(self, *, maximum_drift_ms: int = 1_000) -> int:
        before = self._now_ms()
        server_time = self.get_server_time_ms()
        after = self._now_ms()
        local_midpoint = before + (after - before) // 2
        offset = server_time - local_midpoint
        if server_time <= 0 or abs(offset) > maximum_drift_ms:
            raise RuntimeError(f"Bybit clock drift safety check failed ({offset} ms).")
        return offset

    def get_wallet_balance(self, *, account_type: str = "UNIFIED") -> dict[str, Any]:
        return self._request(
            "GET",
            "/v5/account/wallet-balance",
            params={"accountType": account_type},
            authenticated=True,
            retry_safe=True,
        )

    def get_open_orders(
        self,
        *,
        category: str,
        symbol: str,
        order_link_id: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"category": category, "symbol": symbol, "openOnly": 0, "limit": 50}
        if order_link_id:
            params["orderLinkId"] = order_link_id
        payload = self._request(
            "GET", "/v5/order/realtime", params=params, authenticated=True, retry_safe=True
        )
        return self._result_list(payload)

    def get_order_history(
        self,
        *,
        category: str,
        symbol: str,
        order_link_id: str | None = None,
        start_time_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"category": category, "symbol": symbol, "limit": 50}
        if order_link_id:
            params["orderLinkId"] = order_link_id
        if start_time_ms is not None:
            params["startTime"] = int(start_time_ms)
        payload = self._request(
            "GET", "/v5/order/history", params=params, authenticated=True, retry_safe=True
        )
        return self._result_list(payload)

    def get_recent_executions(
        self,
        *,
        category: str,
        symbol: str,
        start_time_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"category": category, "symbol": symbol, "limit": 100}
        if start_time_ms is not None:
            params["startTime"] = int(start_time_ms)
        payload = self._request(
            "GET", "/v5/execution/list", params=params, authenticated=True, retry_safe=True
        )
        return self._result_list(payload)

    def get_positions(self, *, category: str, symbol: str) -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            "/v5/position/list",
            params={"category": category, "symbol": symbol},
            authenticated=True,
            retry_safe=True,
        )
        return self._result_list(payload)

    def place_order(
        self,
        *,
        category: str,
        symbol: str,
        side: str,
        price: str,
        quantity: str,
        order_link_id: str,
        reduce_only: bool = False,
    ) -> dict[str, Any]:
        if not order_link_id or len(order_link_id) > 36:
            raise ValueError("orderLinkId must be non-empty and no longer than 36 characters.")
        body = {
            "category": category,
            "symbol": symbol,
            "side": "Buy" if side.lower() in {"buy", "bid"} else "Sell",
            "orderType": "Limit",
            "qty": quantity,
            "price": price,
            "timeInForce": "PostOnly",
            "reduceOnly": bool(reduce_only),
            "orderLinkId": order_link_id,
        }
        try:
            return self._request(
                "POST", "/v5/order/create", body=body, authenticated=True, retry_safe=False
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            recovered = self._reconcile_create(
                category=category, symbol=symbol, order_link_id=order_link_id
            )
            if recovered is not None:
                return {"retCode": 0, "retMsg": "reconciled", "result": recovered, "reconciled": True}
            raise UncertainOrderState(
                f"Order create outcome is uncertain for orderLinkId={order_link_id}; quoting must stop."
            ) from exc

    def place_reduce_only_market_order(
        self,
        *,
        category: str,
        symbol: str,
        side: str,
        quantity: str,
        order_link_id: str,
    ) -> dict[str, Any]:
        if not order_link_id or len(order_link_id) > 36:
            raise ValueError("orderLinkId must be non-empty and no longer than 36 characters.")
        try:
            return self._request(
                "POST",
                "/v5/order/create",
                body={
                    "category": category,
                    "symbol": symbol,
                    "side": "Buy" if side.lower() == "buy" else "Sell",
                    "orderType": "Market",
                    "qty": quantity,
                    "timeInForce": "IOC",
                    "reduceOnly": True,
                    "orderLinkId": order_link_id,
                },
                authenticated=True,
                retry_safe=False,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            recovered = self._reconcile_create(
                category=category, symbol=symbol, order_link_id=order_link_id
            )
            if recovered is not None:
                return {"retCode": 0, "retMsg": "reconciled", "result": recovered, "reconciled": True}
            raise UncertainOrderState(
                f"Emergency unwind outcome is uncertain for orderLinkId={order_link_id}."
            ) from exc

    def amend_order(
        self,
        *,
        category: str,
        symbol: str,
        order_id: str,
        price: str,
        quantity: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v5/order/amend",
            body={
                "category": category,
                "symbol": symbol,
                "orderId": order_id,
                "price": price,
                "qty": quantity,
            },
            authenticated=True,
            retry_safe=True,
        )

    def cancel_order(
        self,
        *,
        category: str,
        symbol: str,
        order_id: str | None = None,
        order_link_id: str | None = None,
    ) -> dict[str, Any]:
        if not order_id and not order_link_id:
            raise ValueError("cancel_order requires order_id or order_link_id.")
        body: dict[str, Any] = {"category": category, "symbol": symbol}
        if order_id:
            body["orderId"] = order_id
        else:
            body["orderLinkId"] = order_link_id
        return self._request(
            "POST", "/v5/order/cancel", body=body, authenticated=True, retry_safe=True
        )

    def cancel_all_orders(self, *, category: str, symbol: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v5/order/cancel-all",
            body={"category": category, "symbol": symbol},
            authenticated=True,
            retry_safe=True,
        )

    def _reconcile_create(
        self, *, category: str, symbol: str, order_link_id: str
    ) -> dict[str, Any] | None:
        for query in (self.get_open_orders, self.get_order_history):
            try:
                rows = query(category=category, symbol=symbol, order_link_id=order_link_id)
            except Exception:
                continue
            match = next((row for row in rows if row.get("orderLinkId") == order_link_id), None)
            if match is not None:
                return dict(match)
        return None

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        authenticated: bool,
        retry_safe: bool,
    ) -> dict[str, Any]:
        method_upper = method.upper()
        query = urlencode(sorted((str(k), str(v)) for k, v in (params or {}).items()))
        body_text = json.dumps(dict(body or {}), separators=(",", ":"), ensure_ascii=False)
        url = f"{self.base_url}{path}" + (f"?{query}" if query else "")
        headers = {"Content-Type": "application/json"}
        if authenticated:
            credentials = self._credentials()
            timestamp_ms = self._now_ms()
            signature_payload = query if method_upper == "GET" else body_text
            headers.update(
                {
                    "X-BAPI-API-KEY": credentials.api_key,
                    "X-BAPI-TIMESTAMP": str(timestamp_ms),
                    "X-BAPI-RECV-WINDOW": str(self.recv_window_ms),
                    "X-BAPI-SIGN": sign_rest_payload(
                        timestamp_ms=timestamp_ms,
                        api_key=credentials.api_key,
                        recv_window_ms=self.recv_window_ms,
                        payload=signature_payload,
                        api_secret=credentials.api_secret,
                    ),
                }
            )

        attempts = 3 if retry_safe else 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            self._rate_limiter.wait()
            started = time.perf_counter()
            try:
                response = self.session.request(
                    method_upper,
                    url,
                    headers=headers,
                    data=body_text if method_upper != "GET" else None,
                    timeout=self.timeout_seconds,
                )
                latency_ms = (time.perf_counter() - started) * 1_000.0
                if self._latency_callback:
                    self._latency_callback(path, latency_ms)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise BybitAPIError("Bybit returned a non-object JSON response.")
                ret_code = int(payload.get("retCode", -1))
                if ret_code == 0:
                    if self._success_callback:
                        self._success_callback(path)
                    return payload
                message = str(payload.get("retMsg", "unknown Bybit error"))
                error = BybitAPIError(
                    f"Bybit API {path} failed with retCode={ret_code}: {message}",
                    ret_code=ret_code,
                )
                self._record_error(path=path, error=error, ret_code=ret_code)
                if retry_safe and ret_code in {10000, 10006, 10016} and attempt + 1 < attempts:
                    time.sleep(0.25 * (2**attempt))
                    continue
                raise error
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                self._record_error(path=path, error=exc)
                if retry_safe and attempt + 1 < attempts:
                    time.sleep(0.25 * (2**attempt))
                    continue
                raise
            except requests.RequestException as exc:
                self._record_error(path=path, error=exc)
                raise BybitAPIError(f"Bybit HTTP request failed for {path}: {type(exc).__name__}") from exc
        assert last_error is not None
        raise last_error

    def _credentials(self) -> BybitCredentials:
        if self.credentials is None:
            self.credentials = BybitCredentials.from_env()
        return self.credentials

    def _record_error(self, *, path: str, error: Exception, ret_code: int | None = None) -> None:
        if self._error_callback:
            self._error_callback(
                {
                    "timestamp_ms": self._now_ms(),
                    "path": path,
                    "error_type": type(error).__name__,
                    "ret_code": ret_code,
                    "message": str(error),
                }
            )

    @staticmethod
    def _result_list(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        result = payload.get("result")
        rows = result.get("list") if isinstance(result, Mapping) else None
        if not isinstance(rows, list):
            raise BybitAPIError("Bybit result.list is missing.")
        return [dict(row) for row in rows if isinstance(row, Mapping)]


__all__ = [
    "BybitAPIError",
    "BybitCredentials",
    "BybitDemoRestClient",
    "DEMO_PRIVATE_WS_URL",
    "DEMO_REST_URL",
    "PUBLIC_WS_URL",
    "RequestRateLimiter",
    "UncertainOrderState",
    "require_demo_execution_environment",
    "sign_rest_payload",
    "validate_demo_private_ws_url",
    "validate_demo_rest_url",
    "validate_public_ws_url",
]
