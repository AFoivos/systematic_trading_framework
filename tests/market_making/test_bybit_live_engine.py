from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from src.market_data.trades import Trade
from src.market_making.live_engine import InventoryLedger, OrderCoordinator
from src.market_making.quote_generator import QuoteDecision
from src.market_making.session_reporting import (
    SessionReporter,
    TABLE_COLUMNS,
    WindowClock,
    redact_secrets,
)
from src.venues.bybit.instrument import BybitInstrument


UTC = timezone.utc


def _instrument() -> BybitInstrument:
    return BybitInstrument(
        symbol="BTCUSDT",
        category="linear",
        status="Trading",
        contract_type="LinearPerpetual",
        base_coin="BTC",
        quote_coin="USDT",
        settle_coin="USDT",
        tick_size=Decimal("0.1"),
        quantity_step=Decimal("0.001"),
        minimum_order_quantity=Decimal("0.001"),
        minimum_notional=Decimal("5"),
        maximum_order_quantity=Decimal("100"),
        minimum_price=Decimal("0.1"),
        maximum_price=Decimal("2000000"),
    )


def _reporter(tmp_path: Path, *, started_at: datetime | None = None) -> SessionReporter:
    return SessionReporter(
        root=tmp_path,
        strategy_name="adaptive_inventory_microprice",
        symbol="BTCUSDT",
        session_id="a82f19",
        config={"api_secret": "never-log", "nested": {"BYBIT_DEMO_API_KEY": "also-never"}},
        started_at=started_at or datetime(2026, 7, 17, 12, 0, tzinfo=UTC),
    )


def _quote(*, bid: float = 100.0, ask: float = 101.0) -> QuoteDecision:
    return QuoteDecision(
        symbol="BTCUSDT",
        bid_price=bid,
        ask_price=ask,
        bid_size=0.1,
        ask_size=0.1,
        fair_price=(bid + ask) / 2,
        spread_bps=(ask - bid) / ((bid + ask) / 2) * 10_000,
        inventory_ratio=0.0,
        should_quote=True,
        reason="ok",
        timestamp=datetime.now(UTC),
    )


def test_aligned_two_hour_windows_use_exact_utc_boundaries() -> None:
    clock = WindowClock(7_200, aligned=True)
    window = clock.window_at(datetime(2026, 7, 17, 13, 47, 59, tzinfo=UTC))
    assert window.start == datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
    assert window.end == datetime(2026, 7, 17, 14, 0, tzinfo=UTC)


def test_rolling_window_anchors_to_process_time() -> None:
    clock = WindowClock(7_200, aligned=False)
    first = clock.window_at(datetime(2026, 7, 17, 13, 47, tzinfo=UTC))
    second = clock.window_at(datetime(2026, 7, 17, 16, 0, tzinfo=UTC))
    assert first.start == datetime(2026, 7, 17, 13, 47, tzinfo=UTC)
    assert second.start == datetime(2026, 7, 17, 15, 47, tzinfo=UTC)


def test_window_rotation_carries_inventory_without_forced_flatten(tmp_path: Path) -> None:
    reporter = _reporter(tmp_path)
    reporter.set_start_state(open_orders=[], positions=[], inventory=0.001)
    output = reporter.rotate(
        now=datetime(2026, 7, 17, 14, 0, tzinfo=UTC),
        reconciliation={"status": "ok"},
        open_orders_at_end=[],
        position_at_end=[{"symbol": "BTCUSDT", "side": "Buy", "size": "0.002"}],
        inventory_carried_out=0.002,
    )
    assert output.name.startswith("1200_1400_adaptive_inventory_microprice_BTCUSDT_a82f19")
    assert reporter.inventory_carried_in == pytest.approx(0.002)
    assert reporter.window.start == datetime(2026, 7, 17, 14, 0, tzinfo=UTC)


def test_window_realized_pnl_is_reported_as_window_delta(tmp_path: Path) -> None:
    reporter = _reporter(tmp_path)
    reporter.record(
        "pnl_timeseries",
        {"event_time": datetime(2026, 7, 17, 13, 59, tzinfo=UTC), "realized_pnl": 10.0, "unrealized_pnl": 1.0, "fees": 0.5},
    )
    first = reporter.rotate(
        now=datetime(2026, 7, 17, 14, 0, tzinfo=UTC),
        reconciliation={},
        open_orders_at_end=[],
        position_at_end=[],
        inventory_carried_out=0.0,
    )
    reporter.record(
        "pnl_timeseries",
        {"event_time": datetime(2026, 7, 17, 15, 0, tzinfo=UTC), "realized_pnl": 12.0, "unrealized_pnl": 0.5, "fees": 0.6},
    )
    second = reporter.finalize(
        reconciliation={}, open_orders_at_end=[], position_at_end=[], inventory_carried_out=0.0
    )
    import json

    first_summary = json.loads((first / "summary.json").read_text(encoding="utf-8"))
    second_summary = json.loads((second / "summary.json").read_text(encoding="utf-8"))
    assert first_summary["realized_pnl"] == pytest.approx(10.0)
    assert second_summary["realized_pnl"] == pytest.approx(2.0)


def test_session_report_writes_every_required_artifact_and_redacts_secrets(tmp_path: Path) -> None:
    reporter = _reporter(tmp_path)
    output = reporter.finalize(
        reconciliation={"status": "ok"},
        open_orders_at_end=[],
        position_at_end=[],
        inventory_carried_out=0.0,
    )
    required = {
        "summary.json", "report.md", "config_used_redacted.yaml", "run_metadata.json",
        "reconciliation.json", "open_orders_at_start.json", "open_orders_at_end.json",
        "position_at_start.json", "position_at_end.json",
        *{f"{table}.csv" for table in TABLE_COLUMNS},
    }
    assert required <= {path.name for path in output.iterdir()}
    redacted = (output / "config_used_redacted.yaml").read_text(encoding="utf-8")
    assert "never-log" not in redacted
    assert "also-never" not in redacted
    assert "REDACTED" in redacted


def test_markout_sign_is_positive_for_favorable_buy_and_sell(tmp_path: Path) -> None:
    reporter = _reporter(tmp_path)
    base = 1_700_000_000_000
    reporter.record(
        "executions",
        {"exec_id": "buy", "side": "buy", "price": 100.0, "quantity": 2.0, "exec_time": base},
    )
    reporter.record_midpoint(timestamp_ms=base + 100, mid_price=101.0)
    sell_time = base + 10_000
    reporter.record(
        "executions",
        {"exec_id": "sell", "side": "sell", "price": 100.0, "quantity": 3.0, "exec_time": sell_time},
    )
    reporter.record_midpoint(timestamp_ms=sell_time + 100, mid_price=99.0)
    output = reporter.finalize(
        reconciliation={}, open_orders_at_end=[], position_at_end=[], inventory_carried_out=0.0
    )
    rows = (output / "markouts.csv").read_text(encoding="utf-8").splitlines()
    assert any("buy,buy,100.0" in row and ",100," in row and ",100.0," in row for row in rows)
    assert any("sell,sell,100.0" in row and ",100," in row and ",100.0," in row for row in rows)


def test_recursive_secret_redaction() -> None:
    value = redact_secrets(
        {"api_secret": "s", "BYBIT_DEMO_API_KEY": "k", "safe": {"token": "t", "venue": "bybit"}}
    )
    assert value == {
        "api_secret": "***REDACTED***",
        "BYBIT_DEMO_API_KEY": "***REDACTED***",
        "safe": {"token": "***REDACTED***", "venue": "bybit"},
    }


def test_inventory_and_fee_accounting_across_partial_close_and_flip() -> None:
    ledger = InventoryLedger()
    assert ledger.apply_fill(side="Buy", price=100.0, quantity=2.0, fee=0.1) == (0.0, 2.0, 0.0)
    before, after, realized = ledger.apply_fill(side="Sell", price=110.0, quantity=1.0, fee=0.05)
    assert (before, after, realized) == pytest.approx((2.0, 1.0, 10.0))
    before, after, realized = ledger.apply_fill(side="Sell", price=90.0, quantity=2.0, fee=0.05)
    assert (before, after, realized) == pytest.approx((1.0, -1.0, -10.0))
    assert ledger.average_entry_price == pytest.approx(90.0)
    assert ledger.fees == pytest.approx(0.2)


class _FakeRest:
    def __init__(self) -> None:
        self.place_calls = 0
        self.amend_calls = 0
        self.cancel_calls = 0
        self.cancel_all_calls = 0

    def place_order(self, **_: object) -> dict[str, object]:
        self.place_calls += 1
        return {"result": {"orderId": f"order-{self.place_calls}"}}

    def amend_order(self, **_: object) -> dict[str, object]:
        self.amend_calls += 1
        return {"retCode": 0}

    def cancel_order(self, **_: object) -> dict[str, object]:
        self.cancel_calls += 1
        return {"retCode": 0}

    def cancel_all_orders(self, **_: object) -> dict[str, object]:
        self.cancel_all_calls += 1
        return {"retCode": 0}


def _coordinator(tmp_path: Path, *, mode: str = "live_dry_run", rest: _FakeRest | None = None) -> OrderCoordinator:
    return OrderCoordinator(
        mode=mode,  # type: ignore[arg-type]
        rest_client=rest or _FakeRest(),  # type: ignore[arg-type]
        instrument=_instrument(),
        reporter=_reporter(tmp_path),
        session_id="a82f19",
        minimum_quote_lifetime_ms=750,
        minimum_reprice_ticks=2,
        maximum_quote_age_ms=5_000,
        maximum_cancel_rate_per_minute=30,
    )


def test_quote_diff_avoids_cancel_replace_on_every_book_event(tmp_path: Path) -> None:
    coordinator = _coordinator(tmp_path)

    async def scenario() -> None:
        await coordinator.synchronize(_quote(), quote_event_id="q1")
        first_ids = {side: order.order_id for side, order in coordinator.active.items()}
        await coordinator.synchronize(_quote(bid=100.1, ask=100.9), quote_event_id="q2")
        assert {side: order.order_id for side, order in coordinator.active.items()} == first_ids
        for order in coordinator.active.values():
            order.created_monotonic -= 1.0
        await coordinator.synchronize(_quote(bid=100.3, ask=100.7), quote_event_id="q3")
        assert {side: order.order_id for side, order in coordinator.active.items()} == first_ids

    asyncio.run(scenario())
    actions = [row["action"] for row in coordinator.reporter.rows["order_intents"]]
    assert actions.count("place") == 2
    assert actions.count("amend") == 2
    assert "cancel" not in actions


def test_dry_fill_model_is_conservative_and_supports_partial_fills(tmp_path: Path) -> None:
    coordinator = _coordinator(tmp_path)

    async def scenario() -> None:
        await coordinator.synchronize(_quote(), quote_event_id="q1")

    asyncio.run(scenario())
    now = datetime.now(UTC)
    equal_price = Trade("BTCUSDT", 100.0, 0.05, now, aggressor_side="sell", trade_id="equal")
    assert coordinator.conservative_dry_fills(equal_price, receive_time_ms=int(now.timestamp() * 1_000)) == []
    through = Trade("BTCUSDT", 99.9, 0.04, now, aggressor_side="sell", trade_id="through")
    fills = coordinator.conservative_dry_fills(through, receive_time_ms=int(now.timestamp() * 1_000))
    assert len(fills) == 1
    assert fills[0].quantity == pytest.approx(0.04)
    assert coordinator.active["buy"].leaves_quantity == Decimal("0.06")


def test_graceful_demo_cancel_all_uses_rest_and_clears_local_orders(tmp_path: Path) -> None:
    rest = _FakeRest()
    coordinator = _coordinator(tmp_path, mode="demo_submit", rest=rest)

    async def scenario() -> None:
        await coordinator.synchronize(_quote(), quote_event_id="q1")
        await coordinator.cancel_all(reason="shutdown")

    asyncio.run(scenario())
    assert rest.place_calls == 2
    assert rest.cancel_all_calls == 1
    assert coordinator.active == {}
    assert coordinator.find_order(
        order_id="order-1", order_link_id="mm_a82f19_b_1"
    ) is not None
