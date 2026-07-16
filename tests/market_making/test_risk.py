from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.market_data.order_book import LocalOrderBook
from src.market_making.quote_generator import QuoteDecision
from src.market_making.risk import RiskEngine, RiskLimits, RiskState


def _limits() -> RiskLimits:
    return RiskLimits(
        max_inventory=1.0,
        max_position_value=1_000.0,
        max_daily_loss=50.0,
        max_open_orders=2,
        max_order_size=0.5,
        max_allowed_spread_bps=100.0,
        stale_order_book_ms=1_000,
    )


def _book(now: datetime | None = None) -> LocalOrderBook:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(
        bids=[(100.0, 1.0)],
        asks=[(100.5, 1.0)],
        timestamp=now or datetime.now(timezone.utc),
    )
    return book


def _quote() -> QuoteDecision:
    return QuoteDecision(
        symbol="PI_XBTUSD",
        bid_price=99.5,
        ask_price=101.0,
        bid_size=0.1,
        ask_size=0.1,
        fair_price=100.0,
        spread_bps=50.0,
        inventory_ratio=0.0,
        should_quote=True,
        reason="ok",
        timestamp=datetime.now(timezone.utc),
    )


def test_max_inventory_triggers_kill_switch() -> None:
    risk = RiskEngine(_limits())

    decision = risk.check_quote(quote=_quote(), book=_book(), state=RiskState(inventory=1.1, realized_pnl=0, unrealized_pnl=0, open_orders=0))

    assert not decision.allowed
    assert decision.kill_switch
    assert decision.cancel_all
    assert decision.reason == "max inventory exceeded"


def test_max_daily_loss_triggers_kill_switch() -> None:
    risk = RiskEngine(_limits())

    decision = risk.check_quote(quote=_quote(), book=_book(), state=RiskState(inventory=0, realized_pnl=-51, unrealized_pnl=0, open_orders=0))

    assert not decision.allowed
    assert decision.reason == "max daily loss exceeded"


def test_stale_order_book_triggers_kill_switch() -> None:
    now = datetime.now(timezone.utc)
    risk = RiskEngine(_limits())

    decision = risk.check_quote(
        quote=_quote(),
        book=_book(now - timedelta(seconds=5)),
        state=RiskState(inventory=0, realized_pnl=0, unrealized_pnl=0, open_orders=0, now=now),
    )

    assert not decision.allowed
    assert decision.reason == "stale order book"


def test_extreme_spread_triggers_kill_switch() -> None:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(bids=[(100.0, 1.0)], asks=[(103.0, 1.0)])
    risk = RiskEngine(_limits())

    decision = risk.check_quote(quote=_quote(), book=book, state=RiskState(inventory=0, realized_pnl=0, unrealized_pnl=0, open_orders=0))

    assert not decision.allowed
    assert decision.reason == "extreme order book spread"


def test_manual_kill_switch_blocks_future_quotes() -> None:
    risk = RiskEngine(_limits())
    risk.trigger_kill_switch("manual")

    decision = risk.check_quote(quote=_quote(), book=_book(), state=RiskState(inventory=0, realized_pnl=0, unrealized_pnl=0, open_orders=0))

    assert not decision.allowed
    assert decision.reason == "kill switch active"


def test_worst_case_bid_fill_blocks_inventory_limit_breach_without_kill_switch() -> None:
    risk = RiskEngine(_limits())

    decision = risk.check_quote(
        quote=_quote(),
        book=_book(),
        state=RiskState(inventory=0.95, realized_pnl=0, unrealized_pnl=0, open_orders=2),
    )

    assert not decision.allowed
    assert not decision.kill_switch
    assert not decision.cancel_all
    assert decision.reason == "worst-case inventory would exceed limit"


def test_worst_case_position_value_blocks_quote_without_kill_switch() -> None:
    risk = RiskEngine(
        RiskLimits(
            max_inventory=10.0,
            max_position_value=100.0,
            max_daily_loss=50.0,
            max_open_orders=2,
            max_order_size=0.5,
            max_allowed_spread_bps=100.0,
            stale_order_book_ms=1_000,
        )
    )

    decision = risk.check_quote(
        quote=_quote(),
        book=_book(),
        state=RiskState(inventory=0.95, realized_pnl=0, unrealized_pnl=0, open_orders=2),
    )

    assert not decision.allowed
    assert not decision.kill_switch
    assert decision.reason == "worst-case position value would exceed limit"


def test_max_open_orders_allows_candidate_count_equal_to_limit() -> None:
    risk = RiskEngine(_limits())

    decision = risk.check_quote(
        quote=_quote(),
        book=_book(),
        state=RiskState(inventory=0.0, realized_pnl=0, unrealized_pnl=0, open_orders=2),
    )

    assert decision.allowed


def test_non_finite_risk_state_triggers_fail_closed_kill_switch() -> None:
    risk = RiskEngine(_limits())

    decision = risk.check_quote(
        quote=_quote(),
        book=_book(),
        state=RiskState(
            inventory=float("nan"),
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            open_orders=0,
        ),
    )

    assert not decision.allowed
    assert decision.kill_switch
    assert decision.cancel_all
    assert decision.reason == "invalid non-finite risk state"


def test_quote_symbol_mismatch_is_rejected() -> None:
    risk = RiskEngine(_limits())
    quote = QuoteDecision(
        **{**_quote().__dict__, "symbol": "ETH/USD"}
    )

    decision = risk.check_quote(
        quote=quote,
        book=_book(),
        state=RiskState(inventory=0.0, realized_pnl=0.0, unrealized_pnl=0.0, open_orders=0),
    )

    assert not decision.allowed
    assert decision.reason == "quote symbol does not match order book"


def test_invalid_risk_limit_is_rejected_at_construction() -> None:
    with pytest.raises(ValueError, match="max_position_value"):
        RiskEngine(
            RiskLimits(
                max_inventory=1.0,
                max_position_value=float("nan"),
                max_daily_loss=50.0,
                max_open_orders=2,
                max_order_size=0.5,
                max_allowed_spread_bps=100.0,
                stale_order_book_ms=1_000,
            )
        )
