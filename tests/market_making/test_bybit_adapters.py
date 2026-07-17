from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json

import pytest
import requests

from src.venues.bybit.demo_private_stream import (
    ExecutionDeduplicator,
    PrivateAccountState,
    parse_execution_message,
    parse_order_message,
    parse_position_message,
    private_auth_message,
)
from src.venues.bybit.demo_rest_client import (
    BybitCredentials,
    BybitDemoRestClient,
    UncertainOrderState,
    require_demo_execution_environment,
    sign_rest_payload,
    validate_demo_private_ws_url,
    validate_demo_rest_url,
)
from src.venues.bybit.instrument import BybitInstrument
from src.venues.bybit.public_market_data import (
    BybitOrderBookProcessor,
    SequenceGapError,
    parse_public_trades,
)


def _instrument_payload() -> dict[str, object]:
    return {
        "retCode": 0,
        "retMsg": "OK",
        "result": {
            "category": "linear",
            "list": [
                {
                    "symbol": "BTCUSDT",
                    "contractType": "LinearPerpetual",
                    "status": "Trading",
                    "baseCoin": "BTC",
                    "quoteCoin": "USDT",
                    "settleCoin": "USDT",
                    "priceFilter": {"minPrice": "0.1", "maxPrice": "2000000", "tickSize": "0.1"},
                    "lotSizeFilter": {
                        "minOrderQty": "0.001",
                        "maxOrderQty": "100",
                        "qtyStep": "0.001",
                        "minNotionalValue": "5",
                    },
                }
            ],
        },
    }


def _snapshot(*, update_id: int = 10, seq: int = 20) -> dict[str, object]:
    return {
        "topic": "orderbook.50.BTCUSDT",
        "type": "snapshot",
        "ts": 1_700_000_000_000,
        "data": {
            "s": "BTCUSDT",
            "b": [["100.0", "2"], ["99.9", "1"]],
            "a": [["100.1", "3"], ["100.2", "1"]],
            "u": update_id,
            "seq": seq,
            "cts": 1_700_000_000_000,
        },
    }


def _delta(*, update_id: int, seq: int, bids: list[list[str]], asks: list[list[str]]) -> dict[str, object]:
    return {
        "topic": "orderbook.50.BTCUSDT",
        "type": "delta",
        "ts": 1_700_000_000_020,
        "data": {
            "s": "BTCUSDT",
            "b": bids,
            "a": asks,
            "u": update_id,
            "seq": seq,
            "cts": 1_700_000_000_019,
        },
    }


def test_public_snapshot_delta_insert_update_delete_reconstruction() -> None:
    processor = BybitOrderBookProcessor("BTCUSDT")
    assert processor.process(_snapshot(), receive_timestamp_ms=1_700_000_000_010)
    assert processor.process(
        _delta(
            update_id=11,
            seq=21,
            bids=[["100.0", "0"], ["99.95", "4"]],
            asks=[["100.1", "5"]],
        ),
        receive_timestamp_ms=1_700_000_000_025,
    )

    assert processor.book.best_bid == 99.95
    assert processor.book.best_ask == 100.1
    assert processor.book.bids[0].quantity == 4.0
    assert processor.book.asks[0].quantity == 5.0
    assert processor.health(now_ms=1_700_000_000_026).market_data_latency_ms == 6.0


def test_new_snapshot_resets_local_book() -> None:
    processor = BybitOrderBookProcessor("BTCUSDT")
    processor.process(_snapshot())
    replacement = _snapshot(update_id=50, seq=80)
    replacement["data"]["b"] = [["90", "1"]]  # type: ignore[index]
    replacement["data"]["a"] = [["91", "1"]]  # type: ignore[index]
    assert processor.process(replacement)
    assert processor.book.best_bid == 90.0
    assert processor.book.best_ask == 91.0
    assert processor.update_id == 50


def test_sequence_gap_invalidates_book_until_new_snapshot() -> None:
    processor = BybitOrderBookProcessor("BTCUSDT")
    processor.process(_snapshot())
    with pytest.raises(SequenceGapError, match="expected 11"):
        processor.process(_delta(update_id=12, seq=22, bids=[], asks=[]))
    assert not processor.health().healthy
    assert processor.sequence_gaps == 1
    assert not processor.process(_delta(update_id=13, seq=23, bids=[], asks=[]))
    assert processor.process(_snapshot(update_id=100, seq=200))
    assert processor.healthy


def test_crossed_delta_is_rejected_without_mutating_book() -> None:
    processor = BybitOrderBookProcessor("BTCUSDT")
    processor.process(_snapshot())
    assert not processor.process(
        _delta(update_id=11, seq=21, bids=[["100.2", "1"]], asks=[])
    )
    assert not processor.healthy
    assert processor.crossed_books == 1
    assert processor.book.best_bid == 100.0


def test_stale_book_detection_uses_receive_time() -> None:
    processor = BybitOrderBookProcessor("BTCUSDT", stale_book_ms=2_000)
    processor.process(_snapshot(), receive_timestamp_ms=10_000)
    assert not processor.is_stale(now_ms=12_000)
    assert processor.is_stale(now_ms=12_001)


def test_public_trade_stream_parses_all_trades_in_message() -> None:
    trades = parse_public_trades(
        {
            "topic": "publicTrade.BTCUSDT",
            "data": [
                {"T": 1_700_000_000_000, "s": "BTCUSDT", "S": "Buy", "v": "0.001", "p": "100", "i": "a"},
                {"T": 1_700_000_000_001, "s": "BTCUSDT", "S": "Sell", "v": "0.002", "p": "99.9", "i": "b"},
            ],
        }
    )
    assert [(trade.trade_id, trade.aggressor_side) for trade in trades] == [("a", "buy"), ("b", "sell")]


def test_instrument_metadata_drives_minimum_valid_quantity() -> None:
    instrument = BybitInstrument.from_api_response(
        _instrument_payload(), expected_symbol="BTCUSDT"
    )
    assert str(instrument.minimum_valid_quantity("5000")) == "0.002"
    assert str(instrument.minimum_valid_quantity("100000")) == "0.001"
    with pytest.raises(ValueError, match="minimum notional"):
        instrument.validate_order(price=instrument.round_price("1000", side="buy"), quantity=instrument.minimum_order_quantity)


@pytest.mark.parametrize(
    "url",
    [
        "https://api.bybit.com",
        "https://api-demo.bybit.com.evil.example",
        "http://api-demo.bybit.com",
        "https://api-demo.bybit.com/v5/order/create",
        "https://api-demo.bybit.com?x=1",
    ],
)
def test_demo_host_safety_rejects_every_non_exact_url(url: str) -> None:
    with pytest.raises(RuntimeError, match="exactly"):
        validate_demo_rest_url(url)
    assert validate_demo_rest_url("https://api-demo.bybit.com") == "https://api-demo.bybit.com"


def test_private_ws_safety_rejects_production_private_endpoint() -> None:
    with pytest.raises(RuntimeError, match="stream-demo"):
        validate_demo_private_ws_url("wss://stream.bybit.com/v5/private")


def test_execution_environment_is_explicit_and_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BYBIT_EXECUTION_ENV", raising=False)
    with pytest.raises(RuntimeError, match="explicitly"):
        require_demo_execution_environment()
    monkeypatch.setenv("BYBIT_EXECUTION_ENV", "production")
    with pytest.raises(RuntimeError, match="explicitly"):
        require_demo_execution_environment()
    monkeypatch.setenv("BYBIT_EXECUTION_ENV", "demo")
    require_demo_execution_environment()


def test_rest_signing_matches_official_hmac_formula() -> None:
    signature = sign_rest_payload(
        timestamp_ms=1_650_000_000_000,
        api_key="key",
        recv_window_ms=5_000,
        payload="category=linear&symbol=BTCUSDT",
        api_secret="secret",
    )
    expected = hmac.new(
        b"secret",
        b"1650000000000key5000category=linear&symbol=BTCUSDT",
        hashlib.sha256,
    ).hexdigest()
    assert signature == expected


def test_private_auth_message_uses_get_realtime_signature() -> None:
    credentials = BybitCredentials("demo-key", "demo-secret")
    message = private_auth_message(credentials, expires_ms=123456)
    expected = hmac.new(b"demo-secret", b"GET/realtime123456", hashlib.sha256).hexdigest()
    assert message == {"op": "auth", "args": ["demo-key", 123456, expected]}
    assert "demo-secret" not in repr(credentials)


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload


class _CreateTimeoutSession:
    def __init__(self, recovered: bool) -> None:
        self.recovered = recovered
        self.create_calls = 0

    def request(self, method: str, url: str, **_: object) -> _Response:
        if url.endswith("/v5/order/create"):
            self.create_calls += 1
            raise requests.Timeout("uncertain")
        if "/v5/order/realtime" in url and self.recovered:
            return _Response(
                {"retCode": 0, "result": {"list": [{"orderId": "oid", "orderLinkId": "mm_s_b_1"}]}}
            )
        return _Response({"retCode": 0, "result": {"list": []}})

    def close(self) -> None:
        return None


def test_create_timeout_reconciles_by_order_link_id_without_blind_retry() -> None:
    session = _CreateTimeoutSession(recovered=True)
    client = BybitDemoRestClient(
        credentials=BybitCredentials("key", "secret"),
        session=session,  # type: ignore[arg-type]
        now_ms=lambda: 1_700_000_000_000,
    )
    result = client.place_order(
        category="linear",
        symbol="BTCUSDT",
        side="buy",
        price="100",
        quantity="0.001",
        order_link_id="mm_s_b_1",
    )
    assert result["reconciled"] is True
    assert session.create_calls == 1


def test_unresolved_create_timeout_raises_uncertain_state_after_one_create() -> None:
    session = _CreateTimeoutSession(recovered=False)
    client = BybitDemoRestClient(
        credentials=BybitCredentials("key", "secret"),
        session=session,  # type: ignore[arg-type]
    )
    with pytest.raises(UncertainOrderState, match="quoting must stop"):
        client.place_order(
            category="linear",
            symbol="BTCUSDT",
            side="buy",
            price="100",
            quantity="0.001",
            order_link_id="mm_s_b_1",
        )
    assert session.create_calls == 1


def _execution_message() -> dict[str, object]:
    return {
        "topic": "execution.linear",
        "creationTime": 1_700_000_000_100,
        "data": [
            {
                "execId": "e1", "orderId": "o1", "orderLinkId": "l1", "symbol": "BTCUSDT",
                "side": "Buy", "execPrice": "100", "execQty": "0.001", "execTime": "1700000000000",
                "isMaker": True, "execFee": "0.0001", "feeCurrency": "USDT", "execPnl": "0",
            },
            {
                "execId": "e2", "orderId": "o1", "orderLinkId": "l1", "symbol": "BTCUSDT",
                "side": "Buy", "execPrice": "99", "execQty": "0.002", "execTime": "1700000000050",
                "isMaker": True, "execFee": "0.0002", "feeCurrency": "USDT", "execPnl": "0",
            },
        ],
    }


def test_multiple_partial_executions_are_separate_canonical_records() -> None:
    executions = parse_execution_message(_execution_message(), receive_time_ms=1_700_000_000_100)
    assert [execution.exec_id for execution in executions] == ["e1", "e2"]
    assert sum(execution.quantity for execution in executions) == pytest.approx(0.003)


def test_duplicate_execution_detection_uses_exec_order_symbol_key() -> None:
    execution = parse_execution_message(_execution_message(), receive_time_ms=1_700_000_000_100)[0]
    dedupe = ExecutionDeduplicator()
    assert dedupe.accept(execution)
    assert not dedupe.accept(execution)
    assert dedupe.duplicate_count == 1


def test_cancel_fill_race_keeps_execution_after_cancel_message() -> None:
    cancelled = parse_order_message(
        {
            "topic": "order.linear",
            "data": [{
                "orderId": "o1", "orderLinkId": "l1", "symbol": "BTCUSDT", "side": "Buy",
                "price": "100", "qty": "0.003", "leavesQty": "0", "cumExecQty": "0.003",
                "orderStatus": "Cancelled", "cancelType": "CancelByUser", "updatedTime": "1700000000100",
            }],
        }
    )[0]
    fills = parse_execution_message(_execution_message(), receive_time_ms=1_700_000_000_200)
    assert cancelled.status == "Cancelled"
    assert len(fills) == 2


def test_private_account_state_handles_execution_then_newer_position() -> None:
    executions = parse_execution_message(_execution_message(), receive_time_ms=1_700_000_000_100)
    state = PrivateAccountState("BTCUSDT")
    state.apply_execution(executions[0])
    assert state.inventory == pytest.approx(0.001)
    position = parse_position_message(
        {
            "topic": "position.linear",
            "creationTime": 1_700_000_000_200,
            "data": [{
                "symbol": "BTCUSDT", "side": "Buy", "size": "0.003", "entryPrice": "99.5",
                "unrealisedPnl": "1", "curRealisedPnl": "2", "updatedTime": "1700000000200",
            }],
        }
    )[0]
    state.apply_position(position)
    state.apply_execution(executions[1])  # Older than the confirmed position; retained but not double-counted.
    assert state.inventory == pytest.approx(0.003)
    assert len(state.executions) == 2
