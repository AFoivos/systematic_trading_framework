from __future__ import annotations

import csv
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Any

from .metrics import PaperRunSummary, max_drawdown
from .quote_generator import QuoteDecision
from .risk import RiskEngine, RiskState
from src.market_data.order_book import LocalOrderBook
from src.market_data.trades import Trade


@dataclass(frozen=True)
class PaperOrder:
    """Virtual limit order tracked by the paper engine."""

    order_id: str
    symbol: str
    side: str
    price: float
    quantity: float
    timestamp: datetime
    status: str = "open"
    parent_quote_event_id: str | None = None


@dataclass(frozen=True)
class PaperFill:
    """Virtual fill generated from conservative trade-through rules."""

    order_id: str
    symbol: str
    side: str
    price: float
    quantity: float
    fee: float
    timestamp: datetime
    parent_quote_event_id: str | None = None


@dataclass
class PaperAccount:
    """Virtual account state for paper market making."""

    initial_cash: float = 0.0
    cash: float = 0.0
    inventory: float = 0.0
    average_entry_price: float = 0.0
    realized_pnl: float = 0.0
    fees: float = 0.0
    turnover: float = 0.0


class PaperMarketMakingEngine:
    """Conservative paper engine for market-making quotes and trade-through fills."""

    def __init__(self, *, risk_engine: RiskEngine, maker_fee_bps: float = 0.0, initial_cash: float = 0.0) -> None:
        if not math.isfinite(float(maker_fee_bps)):
            raise ValueError("maker_fee_bps must be finite.")
        if not math.isfinite(float(initial_cash)):
            raise ValueError("initial_cash must be finite.")
        self.risk_engine = risk_engine
        self.maker_fee_bps = float(maker_fee_bps)
        self.account = PaperAccount(initial_cash=initial_cash, cash=initial_cash)
        self.open_orders: dict[str, PaperOrder] = {}
        self.orders: list[PaperOrder] = []
        self.fills: list[PaperFill] = []
        self.quote_events: list[dict[str, Any]] = []
        self.pnl_timeseries: list[dict[str, float | str]] = []
        self.inventory_timeseries: list[dict[str, float | str]] = []
        self.spreads_quoted: list[float] = []
        self.number_of_quotes = 0
        self.number_of_cancels = 0
        self.runtime_errors = 0
        self.reconnects = 0
        self._next_order_id = 1
        self._next_quote_event_id = 1

    @property
    def realized_pnl(self) -> float:
        return self.account.realized_pnl

    def place_quote(self, *, quote: QuoteDecision, book: LocalOrderBook, now: datetime | None = None) -> bool:
        """Risk-check and place a two-sided virtual quote."""
        event_time = now or datetime.now(timezone.utc)
        state = RiskState(
            inventory=self.account.inventory,
            realized_pnl=self.account.realized_pnl,
            unrealized_pnl=self.unrealized_pnl(quote.fair_price),
            open_orders=self._candidate_order_count(quote),
            now=event_time,
        )
        decision = self.risk_engine.check_quote(quote=quote, book=book, state=state)
        quote_event_id = self._new_quote_event_id()
        if decision.cancel_all:
            self.cancel_all(now=event_time)
        if not decision.allowed:
            self._record_quote_event(
                quote_event_id=quote_event_id,
                quote=quote,
                book=book,
                event_time=event_time,
                risk_allowed=False,
                risk_reason=decision.reason,
                risk_cancel_all=decision.cancel_all,
                risk_kill_switch=decision.kill_switch,
                placed=False,
                bid_order_id=None,
                ask_order_id=None,
            )
            return False
        self.cancel_all(now=event_time)
        bid_order_id = (
            self._add_order(quote.symbol, "buy", quote.bid_price, quote.bid_size, event_time, quote_event_id)
            if quote.bid_price is not None and quote.bid_size > 0
            else None
        )
        ask_order_id = (
            self._add_order(quote.symbol, "sell", quote.ask_price, quote.ask_size, event_time, quote_event_id)
            if quote.ask_price is not None and quote.ask_size > 0
            else None
        )
        self.number_of_quotes += 1
        self.spreads_quoted.append(quote.spread_bps)
        self._record_quote_event(
            quote_event_id=quote_event_id,
            quote=quote,
            book=book,
            event_time=event_time,
            risk_allowed=True,
            risk_reason=decision.reason,
            risk_cancel_all=decision.cancel_all,
            risk_kill_switch=decision.kill_switch,
            placed=True,
            bid_order_id=bid_order_id,
            ask_order_id=ask_order_id,
        )
        self._mark(quote.fair_price, event_time)
        return True

    def process_trade(self, trade: Trade) -> list[PaperFill]:
        """Fill eligible virtual orders using conservative trade-through logic."""
        fills: list[PaperFill] = []
        for order in list(self.open_orders.values()):
            if order.symbol != trade.symbol:
                continue
            if order.side == "buy" and trade.price <= order.price:
                fills.append(self._fill_order(order, trade.timestamp))
            elif order.side == "sell" and trade.price >= order.price:
                fills.append(self._fill_order(order, trade.timestamp))
        self._mark(trade.price, trade.timestamp)
        return fills

    def process_top_of_book_crossing(
        self,
        *,
        symbol: str,
        best_bid: float | None,
        best_ask: float | None,
        timestamp: datetime,
    ) -> list[PaperFill]:
        """
        Fill open orders only when the next top-of-book crosses their limit price.

        This model is stricter than same-tick trade-through replay: buy limits fill only when the
        next best ask is at or below the bid order price, and sell limits fill only when the next
        best bid is at or above the ask order price.
        """
        fills: list[PaperFill] = []
        for order in list(self.open_orders.values()):
            if order.symbol != symbol:
                continue
            if order.side == "buy" and best_ask is not None and best_ask <= order.price:
                fills.append(self._fill_order(order, timestamp))
            elif order.side == "sell" and best_bid is not None and best_bid >= order.price:
                fills.append(self._fill_order(order, timestamp))
        mark_price = self._top_of_book_mark(best_bid=best_bid, best_ask=best_ask)
        if mark_price is not None:
            self._mark(mark_price, timestamp)
        return fills

    def cancel_all(self, *, now: datetime | None = None) -> int:
        """Cancel all virtual open orders."""
        order_ids = list(self.open_orders)
        count = len(order_ids)
        if count:
            self.number_of_cancels += count
            for order_id in order_ids:
                self._set_order_status(order_id, "cancelled")
        self.open_orders.clear()
        return count

    def unrealized_pnl(self, mark_price: float) -> float:
        """Mark open inventory against its average entry price."""
        inventory = self.account.inventory
        if inventory == 0.0:
            return 0.0
        return (mark_price - self.account.average_entry_price) * inventory

    def total_pnl(self, mark_price: float) -> float:
        """Return realized plus unrealized PnL net of fees."""
        return self.account.realized_pnl + self.unrealized_pnl(mark_price)

    def summary(
        self,
        mark_price: float,
        *,
        input_events: int = 0,
        quoted_events: int = 0,
        skipped_events: int = 0,
        reconstructed_book_events: int = 0,
        fill_model: str = "trade_through",
        data_source: str = "synthetic",
        adverse_selection_filter_active: bool = False,
    ) -> PaperRunSummary:
        """Return paper run metrics."""
        total_orders = max(len(self.orders), 1)
        quote_attempt_count = len(self.quote_events)
        placed_quote_count = sum(1 for event in self.quote_events if bool(event.get("placed")))
        fills_per_order = len(self.fills) / total_orders
        inventories = [float(row["inventory"]) for row in self.inventory_timeseries]
        pnl_values = [float(row["total_pnl"]) for row in self.pnl_timeseries]
        return PaperRunSummary(
            total_pnl=self.total_pnl(mark_price),
            realized_pnl=self.account.realized_pnl,
            unrealized_pnl=self.unrealized_pnl(mark_price),
            fees=self.account.fees,
            number_of_fills=len(self.fills),
            number_of_quotes=self.number_of_quotes,
            number_of_cancels=self.number_of_cancels,
            fill_ratio=fills_per_order,
            fills_per_quote_attempt=self._safe_div(len(self.fills), quote_attempt_count),
            fills_per_placed_quote=self._safe_div(len(self.fills), placed_quote_count),
            fills_per_order=fills_per_order,
            fills_per_input_event=self._safe_div(len(self.fills), input_events),
            average_spread_quoted=sum(self.spreads_quoted) / len(self.spreads_quoted) if self.spreads_quoted else 0.0,
            average_inventory=sum(inventories) / len(inventories) if inventories else self.account.inventory,
            max_inventory=max((abs(value) for value in inventories), default=abs(self.account.inventory)),
            max_drawdown=max_drawdown(pnl_values),
            kill_switch_events=list(self.risk_engine.kill_events),
            runtime_errors=self.runtime_errors,
            reconnects=self.reconnects,
            input_events=input_events,
            quoted_events=quoted_events,
            skipped_events=skipped_events,
            reconstructed_book_events=reconstructed_book_events,
            fill_model=fill_model,
            data_source=data_source,
            adverse_selection_filter_active=adverse_selection_filter_active,
        )

    def write_report(
        self,
        output_dir: str | Path,
        *,
        mark_price: float,
        input_events: int = 0,
        quoted_events: int = 0,
        skipped_events: int = 0,
        reconstructed_book_events: int = 0,
        fill_model: str = "trade_through",
        data_source: str = "synthetic",
        adverse_selection_filter_active: bool = False,
    ) -> PaperRunSummary:
        """Write JSON/CSV paper artifacts."""
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        summary = self.summary(
            mark_price,
            input_events=input_events,
            quoted_events=quoted_events,
            skipped_events=skipped_events,
            reconstructed_book_events=reconstructed_book_events,
            fill_model=fill_model,
            data_source=data_source,
            adverse_selection_filter_active=adverse_selection_filter_active,
        )
        (path / "summary.json").write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")
        self._write_csv(path / "orders.csv", [order.__dict__ for order in self.orders])
        self._write_csv(path / "trades.csv", [fill.__dict__ for fill in self.fills])
        self._write_csv(path / "quote_events.csv", self.quote_events)
        self._write_csv(path / "pnl_timeseries.csv", self.pnl_timeseries)
        self._write_csv(path / "inventory_timeseries.csv", self.inventory_timeseries)
        return summary

    def _add_order(
        self,
        symbol: str,
        side: str,
        price: float | None,
        quantity: float,
        timestamp: datetime,
        parent_quote_event_id: str | None,
    ) -> str:
        if price is None:
            raise ValueError("paper order price cannot be None.")
        order_id = f"paper-{self._next_order_id}"
        self._next_order_id += 1
        order = PaperOrder(order_id, symbol, side, float(price), float(quantity), timestamp, parent_quote_event_id=parent_quote_event_id)
        self.open_orders[order_id] = order
        self.orders.append(order)
        return order_id

    def _record_quote_event(
        self,
        *,
        quote_event_id: str,
        quote: QuoteDecision,
        book: LocalOrderBook,
        event_time: datetime,
        risk_allowed: bool,
        risk_reason: str,
        risk_cancel_all: bool,
        risk_kill_switch: bool,
        placed: bool,
        bid_order_id: str | None,
        ask_order_id: str | None,
    ) -> None:
        self.quote_events.append(
            {
                "quote_event_id": quote_event_id,
                "timestamp": event_time.isoformat(),
                "symbol": quote.symbol,
                "fair_price": quote.fair_price,
                "bid_price": quote.bid_price,
                "ask_price": quote.ask_price,
                "bid_size": quote.bid_size,
                "ask_size": quote.ask_size,
                "spread_bps": quote.spread_bps,
                "inventory": self.account.inventory,
                "inventory_ratio": quote.inventory_ratio,
                "book_best_bid": book.best_bid,
                "book_best_ask": book.best_ask,
                "book_mid_price": book.mid_price,
                "book_spread_bps": book.spread_bps,
                "book_imbalance_1": book.imbalance(1),
                "book_imbalance_5": book.imbalance(5),
                "should_quote": quote.should_quote,
                "quote_reason": quote.reason,
                "risk_allowed": risk_allowed,
                "risk_reason": risk_reason,
                "risk_cancel_all": risk_cancel_all,
                "risk_kill_switch": risk_kill_switch,
                "placed": placed,
                "bid_order_id": bid_order_id,
                "ask_order_id": ask_order_id,
            }
        )

    def _new_quote_event_id(self) -> str:
        quote_event_id = f"quote-{self._next_quote_event_id}"
        self._next_quote_event_id += 1
        return quote_event_id

    @staticmethod
    def _candidate_order_count(quote: QuoteDecision) -> int:
        count = 0
        if quote.bid_price is not None and quote.bid_size > 0:
            count += 1
        if quote.ask_price is not None and quote.ask_size > 0:
            count += 1
        return count

    def _fill_order(self, order: PaperOrder, timestamp: datetime) -> PaperFill:
        self.open_orders.pop(order.order_id, None)
        self._set_order_status(order.order_id, "filled")
        notional = order.price * order.quantity
        fee = notional * self.maker_fee_bps / 10_000.0
        signed_qty = order.quantity if order.side == "buy" else -order.quantity
        self.account.cash -= signed_qty * order.price + fee
        self.account.fees += fee
        self.account.turnover += notional
        realized_delta = self._update_position(signed_qty=signed_qty, fill_price=order.price)
        self.account.realized_pnl += realized_delta - fee
        fill = PaperFill(
            order.order_id,
            order.symbol,
            order.side,
            order.price,
            order.quantity,
            fee,
            timestamp,
            parent_quote_event_id=order.parent_quote_event_id,
        )
        self.fills.append(fill)
        return fill

    def _set_order_status(self, order_id: str, status: str) -> None:
        for index, order in enumerate(self.orders):
            if order.order_id == order_id:
                self.orders[index] = replace(order, status=status)
                return

    def _update_position(self, *, signed_qty: float, fill_price: float) -> float:
        """Update signed inventory and realize PnL only on inventory reductions."""
        inventory = self.account.inventory
        average_entry_price = self.account.average_entry_price
        realized_delta = 0.0

        if inventory == 0.0:
            self.account.inventory = signed_qty
            self.account.average_entry_price = fill_price if signed_qty != 0.0 else 0.0
            return realized_delta

        if inventory > 0.0:
            if signed_qty > 0.0:
                new_inventory = inventory + signed_qty
                self.account.average_entry_price = (
                    (inventory * average_entry_price) + (signed_qty * fill_price)
                ) / new_inventory
                self.account.inventory = new_inventory
                return realized_delta
            closing_qty = min(inventory, abs(signed_qty))
            realized_delta = (fill_price - average_entry_price) * closing_qty
            new_inventory = inventory + signed_qty
            self.account.inventory = new_inventory
            if new_inventory > 0.0:
                self.account.average_entry_price = average_entry_price
            elif new_inventory < 0.0:
                self.account.average_entry_price = fill_price
            else:
                self.account.average_entry_price = 0.0
            return realized_delta

        if signed_qty < 0.0:
            current_abs = abs(inventory)
            added_abs = abs(signed_qty)
            new_inventory = inventory + signed_qty
            self.account.average_entry_price = (
                (current_abs * average_entry_price) + (added_abs * fill_price)
            ) / abs(new_inventory)
            self.account.inventory = new_inventory
            return realized_delta

        closing_qty = min(abs(inventory), signed_qty)
        realized_delta = (average_entry_price - fill_price) * closing_qty
        new_inventory = inventory + signed_qty
        self.account.inventory = new_inventory
        if new_inventory < 0.0:
            self.account.average_entry_price = average_entry_price
        elif new_inventory > 0.0:
            self.account.average_entry_price = fill_price
        else:
            self.account.average_entry_price = 0.0
        return realized_delta

    @staticmethod
    def _safe_div(num: float, den: float) -> float | None:
        return None if den == 0 else float(num) / float(den)

    def _mark(self, mark_price: float, timestamp: datetime) -> None:
        total_pnl = self.total_pnl(mark_price)
        self.pnl_timeseries.append(
            {
                "timestamp": timestamp.isoformat(),
                "realized_pnl": self.account.realized_pnl,
                "unrealized_pnl": self.unrealized_pnl(mark_price),
                "total_pnl": total_pnl,
                "fees": self.account.fees,
            }
        )
        self.inventory_timeseries.append(
            {
                "timestamp": timestamp.isoformat(),
                "inventory": self.account.inventory,
                "mark_price": mark_price,
            }
        )

    @staticmethod
    def _top_of_book_mark(*, best_bid: float | None, best_ask: float | None) -> float | None:
        if best_bid is not None and best_ask is not None:
            return (best_bid + best_ask) / 2.0
        if best_bid is not None:
            return best_bid
        if best_ask is not None:
            return best_ask
        return None

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)


__all__ = ["PaperAccount", "PaperFill", "PaperMarketMakingEngine", "PaperOrder"]
