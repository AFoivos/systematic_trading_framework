from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.market_data.order_book import LocalOrderBook
from src.market_data.trades import Trade
from src.market_making.paper_engine import PaperMarketMakingEngine
from src.market_making.quote_generator import QuoteDecision
from src.market_making.metrics import max_drawdown
from src.market_making.risk import RiskEngine, RiskLimits


def _risk() -> RiskEngine:
    return RiskEngine(
        RiskLimits(
            max_inventory=10.0,
            max_position_value=10_000.0,
            max_daily_loss=1_000.0,
            max_open_orders=4,
            max_order_size=2.0,
            max_allowed_spread_bps=200.0,
            stale_order_book_ms=10_000,
        )
    )


def _book() -> LocalOrderBook:
    book = LocalOrderBook("PI_XBTUSD")
    book.apply_snapshot(bids=[(99.0, 1.0)], asks=[(101.0, 1.0)], timestamp=datetime.now(timezone.utc))
    return book


def _quote() -> QuoteDecision:
    return QuoteDecision(
        symbol="PI_XBTUSD",
        bid_price=99.0,
        ask_price=101.0,
        bid_size=1.0,
        ask_size=1.0,
        fair_price=100.0,
        spread_bps=200.0,
        inventory_ratio=0.0,
        should_quote=True,
        reason="ok",
        timestamp=datetime.now(timezone.utc),
    )


def test_virtual_buy_fill_updates_inventory_cash_and_fees() -> None:
    engine = PaperMarketMakingEngine(risk_engine=_risk(), maker_fee_bps=10.0)
    engine.place_quote(quote=_quote(), book=_book())

    fills = engine.process_trade(Trade("PI_XBTUSD", price=99.0, quantity=1.0, timestamp=datetime.now(timezone.utc)))

    assert len(fills) == 1
    assert fills[0].side == "buy"
    assert engine.orders[0].status == "filled"
    assert engine.orders[1].status == "open"
    assert engine.account.inventory == 1.0
    assert engine.account.average_entry_price == pytest.approx(99.0)
    assert engine.account.fees == pytest.approx(0.099)
    assert engine.account.realized_pnl == pytest.approx(-0.099)
    assert engine.account.cash == pytest.approx(-99.099)


def test_virtual_sell_fill_updates_inventory_and_pnl() -> None:
    engine = PaperMarketMakingEngine(risk_engine=_risk(), maker_fee_bps=0.0)
    engine.place_quote(quote=_quote(), book=_book())
    engine.process_trade(Trade("PI_XBTUSD", price=99.0, quantity=1.0, timestamp=datetime.now(timezone.utc)))
    engine.place_quote(quote=_quote(), book=_book())

    fills = engine.process_trade(Trade("PI_XBTUSD", price=101.0, quantity=1.0, timestamp=datetime.now(timezone.utc)))

    assert len(fills) == 1
    assert fills[0].side == "sell"
    assert engine.account.inventory == 0.0
    assert engine.account.realized_pnl == pytest.approx(2.0)
    assert engine.total_pnl(100.0) == pytest.approx(2.0)


def test_report_summary_tracks_fill_ratio_and_drawdown(tmp_path) -> None:
    engine = PaperMarketMakingEngine(risk_engine=_risk(), maker_fee_bps=0.0)
    engine.place_quote(quote=_quote(), book=_book())
    engine.process_trade(Trade("PI_XBTUSD", price=99.0, quantity=1.0, timestamp=datetime.now(timezone.utc)))

    summary = engine.write_report(tmp_path, mark_price=100.0)

    assert summary.number_of_fills == 1
    assert summary.number_of_quotes == 1
    assert summary.realized_pnl == pytest.approx(0.0)
    assert summary.unrealized_pnl == pytest.approx(1.0)
    assert summary.total_pnl == pytest.approx(1.0)
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "orders.csv").exists()
    assert (tmp_path / "trades.csv").exists()
    assert (tmp_path / "quote_events.csv").exists()


def test_quote_events_capture_risk_and_book_context(tmp_path) -> None:
    engine = PaperMarketMakingEngine(risk_engine=_risk(), maker_fee_bps=0.0)

    assert engine.place_quote(quote=_quote(), book=_book())
    engine.write_report(tmp_path, mark_price=100.0)

    text = (tmp_path / "quote_events.csv").read_text(encoding="utf-8")
    assert "quote_event_id" in text
    assert "bid_order_id" in text
    assert "ask_order_id" in text
    assert "risk_allowed" in text
    assert "book_best_bid" in text
    assert "placed" in text


def test_order_and_fill_rows_include_parent_quote_event_id(tmp_path) -> None:
    engine = PaperMarketMakingEngine(risk_engine=_risk(), maker_fee_bps=0.0)
    engine.place_quote(quote=_quote(), book=_book())
    engine.process_trade(Trade("PI_XBTUSD", price=99.0, quantity=1.0, timestamp=datetime.now(timezone.utc)))

    engine.write_report(tmp_path, mark_price=100.0)

    assert "parent_quote_event_id" in (tmp_path / "orders.csv").read_text(encoding="utf-8")
    assert "parent_quote_event_id" in (tmp_path / "trades.csv").read_text(encoding="utf-8")


def test_cancel_replace_risk_uses_candidate_orders_not_existing_open_orders() -> None:
    risk = RiskEngine(
        RiskLimits(
            max_inventory=10.0,
            max_position_value=10_000.0,
            max_daily_loss=1_000.0,
            max_open_orders=2,
            max_order_size=2.0,
            max_allowed_spread_bps=300.0,
            stale_order_book_ms=10_000,
        )
    )
    engine = PaperMarketMakingEngine(risk_engine=risk, maker_fee_bps=0.0)
    book = _book()

    assert engine.place_quote(quote=_quote(), book=book)
    first_order_ids = set(engine.open_orders)
    assert len(first_order_ids) == 2

    assert engine.place_quote(quote=_quote(), book=book)

    assert len(engine.open_orders) == 2
    assert set(engine.open_orders).isdisjoint(first_order_ids)
    assert engine.number_of_cancels == 2
    assert [order.status for order in engine.orders[:2]] == ["cancelled", "cancelled"]
    assert [order.status for order in engine.orders[2:]] == ["open", "open"]


def test_max_drawdown_includes_initial_zero_pnl_anchor() -> None:
    assert max_drawdown([-2.0, -1.0, 1.0]) == pytest.approx(2.0)
