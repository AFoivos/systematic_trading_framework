from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import pytest
import yaml

from src.execution import AuthenticationError, OandaExecution, RateLimitExceeded, create_execution_engine
from src.execution.broker_base import BrokerBase
from src.execution.oanda_execution import OandaTransport


class FakeOandaTransport(OandaTransport):
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

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
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "json_body": dict(json_body or {}),
                "params": dict(params or {}),
                "timeout": timeout,
            }
        )
        if not self.responses:
            return {}
        return self.responses.pop(0)


def _config(**overrides: Any) -> dict[str, Any]:
    base = {
        "environment": "practice",
        "account_id": "101-001-123",
        "api_token": "token",
        "request_timeout": 12,
        "reconnect": True,
        "max_retry": 3,
        "symbols": {
            "SPX500": {"oanda_symbol": "US500_USD", "enabled": True},
            "EURUSD": {"oanda_symbol": "EUR_USD", "enabled": True},
        },
    }
    base.update(overrides)
    return base


def test_authentication_requires_token() -> None:
    with pytest.raises(AuthenticationError, match="api_token"):
        OandaExecution(_config(api_token="", api_token_env="MISSING_OANDA_TOKEN"))


def test_connect_uses_token_auth_and_loads_account_info() -> None:
    transport = FakeOandaTransport(
        [{"account": {"id": "101-001-123", "balance": "10000", "NAV": "10025", "marginUsed": "50"}}]
    )
    broker = OandaExecution(_config(), transport=transport)

    broker.connect()

    assert broker.is_connected() is True
    assert broker.get_equity() == pytest.approx(10025.0)
    assert transport.calls[0]["headers"]["Authorization"] == "Bearer token"
    assert transport.calls[0]["url"].startswith("https://api-fxpractice.oanda.com/v3/accounts/")


def test_historical_candles_return_framework_ohlcv_columns() -> None:
    transport = FakeOandaTransport(
        [
            {
                "candles": [
                    {
                        "complete": True,
                        "time": "2024-01-02T10:00:00.000000000Z",
                        "mid": {"o": "1.10", "h": "1.20", "l": "1.05", "c": "1.15"},
                        "volume": 123,
                    },
                    {
                        "complete": False,
                        "time": "2024-01-02T10:30:00.000000000Z",
                        "mid": {"o": "1.15", "h": "1.25", "l": "1.10", "c": "1.22"},
                        "volume": 99,
                    },
                ]
            }
        ]
    )
    broker = OandaExecution(_config(), transport=transport)

    bars = broker.get_historical_bars("EURUSD", "M30", 2)

    assert list(bars.columns) == ["datetime", "open", "high", "low", "close", "volume"]
    assert len(bars) == 1
    assert bars.iloc[0]["close"] == pytest.approx(1.15)
    assert pd.api.types.is_datetime64_any_dtype(bars["datetime"])
    assert transport.calls[0]["params"] == {"granularity": "M30", "count": 2, "price": "M"}


def test_symbol_mapping_and_latest_price() -> None:
    transport = FakeOandaTransport(
        [
            {
                "prices": [
                    {
                        "instrument": "US500_USD",
                        "time": "2024-01-02T10:00:00.000000000Z",
                        "bids": [{"price": "4700.1"}],
                        "asks": [{"price": "4700.6"}],
                    }
                ]
            }
        ]
    )
    broker = OandaExecution(_config(), transport=transport)

    price = broker.get_latest_price("SPX500")

    assert price.broker_symbol == "US500_USD"
    assert price.bid == pytest.approx(4700.1)
    assert transport.calls[0]["params"]["instruments"] == "US500_USD"


def test_market_order_payload_supports_dependent_orders() -> None:
    transport = FakeOandaTransport([{"orderCreateTransaction": {"id": "11"}, "orderFillTransaction": {"id": "12"}}])
    broker = OandaExecution(_config(), transport=transport)

    result = broker.place_market_order(
        symbol="EURUSD",
        side="buy",
        units=1000,
        take_profit=1.2,
        stop_loss=1.1,
        trailing_stop_distance=0.01,
    )

    order = transport.calls[0]["json_body"]["order"]
    assert result.accepted is True
    assert order["type"] == "MARKET"
    assert order["instrument"] == "EUR_USD"
    assert order["units"] == "1000"
    assert order["takeProfitOnFill"] == {"price": "1.2"}
    assert order["stopLossOnFill"] == {"price": "1.1"}
    assert order["trailingStopLossOnFill"] == {"distance": "0.01"}


def test_limit_order_payload_uses_negative_units_for_sell() -> None:
    transport = FakeOandaTransport([{"orderCreateTransaction": {"id": "21"}}])
    broker = OandaExecution(_config(), transport=transport)

    broker.place_limit_order(symbol="EURUSD", side="sell", units=500, price=1.09)

    order = transport.calls[0]["json_body"]["order"]
    assert order["type"] == "LIMIT"
    assert order["units"] == "-500"
    assert order["price"] == "1.09"
    assert order["timeInForce"] == "GTC"


def test_position_closing_supports_partial_close() -> None:
    transport = FakeOandaTransport([{"orderFillTransaction": {"id": "31"}}])
    broker = OandaExecution(_config(), transport=transport)

    result = broker.close_position("EURUSD", side="long", units=250)

    assert result.accepted is True
    assert transport.calls[0]["method"] == "PUT"
    assert transport.calls[0]["json_body"] == {"longUnits": "250"}


def test_reconnect_retries_connection_loss() -> None:
    transport = FakeOandaTransport(
        [
            {"_http_status": 503, "errorMessage": "temporary unavailable"},
            {"account": {"id": "101-001-123", "balance": "10000", "NAV": "10000", "marginUsed": "0"}},
        ]
    )
    sleeps: list[float] = []
    broker = OandaExecution(_config(max_retry=2), transport=transport, sleep_fn=sleeps.append)

    snapshot = broker.account_info()

    assert snapshot.equity == pytest.approx(10000.0)
    assert len(transport.calls) == 2
    assert sleeps


def test_rate_limit_retries_then_raises() -> None:
    transport = FakeOandaTransport(
        [
            {"_http_status": 429, "errorMessage": "rate limit"},
            {"_http_status": 429, "errorMessage": "rate limit"},
        ]
    )
    broker = OandaExecution(_config(max_retry=2), transport=transport, sleep_fn=lambda _: None)

    with pytest.raises(RateLimitExceeded):
        broker.account_info()


def test_configuration_loading_and_broker_factory() -> None:
    raw = """
execution:
  broker: oanda
  oanda:
    environment: practice
    account_id: 101-001-123
    api_token: token
    symbols:
      EURUSD:
        oanda_symbol: EUR_USD
"""
    config = yaml.safe_load(raw)

    broker = create_execution_engine(config)

    assert isinstance(broker, BrokerBase)
    assert isinstance(broker, OandaExecution)
