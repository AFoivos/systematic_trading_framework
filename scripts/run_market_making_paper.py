from __future__ import annotations

import argparse
import csv
import logging
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import deque
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.market_data.order_book import LocalOrderBook
from src.market_data.trades import Trade
from src.market_making.paper_engine import PaperMarketMakingEngine
from src.market_making.adverse_selection_filter import AdverseSelectionConfig, AdverseSelectionFilter
from src.market_making.diagnostics import write_market_making_diagnostics
from src.market_making.quote_generator import QuoteDecision, QuoteGenerator, QuoteGeneratorConfig
from src.market_making.reporting import write_market_making_markdown_report
from src.market_making.risk import RiskEngine, RiskLimits
from src.market_making.spread_model import SpreadConfig
from src.market_making.strategy import DirectionalFeatureGate, FeeAwareGate, MarketMakingStrategy, SideSelectionGate


@dataclass(frozen=True)
class ReconstructedBookEvent:
    """Top-of-book event reconstructed from the Kraken orderbook_events.csv collector output."""

    timestamp: datetime
    symbol: str
    best_bid: float
    best_ask: float
    bid_quantity: float
    ask_quantity: float
    sequence: int | None = None
    update_id: int | None = None


@dataclass(frozen=True)
class StrategyQuoteAdapter:
    """Expose MarketMakingStrategy through the QuoteGenerator.generate call shape."""

    strategy: MarketMakingStrategy

    def generate(
        self,
        *,
        book: LocalOrderBook,
        inventory: float,
        recent_returns: list[float] | None = None,
        spread_multiplier: float = 1.0,
    ) -> QuoteDecision:
        return self.strategy.decide(book=book, inventory=inventory, recent_returns=recent_returns)


def load_config(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def build_components(config: dict[str, Any]) -> tuple[Any, PaperMarketMakingEngine]:
    execution = config.get("execution", {})
    mm = config.get("market_making", {})
    fees = config.get("fees", {})
    risk = config.get("risk", {})
    spread = SpreadConfig(
        model=mm.get("spread_model", "fixed"),
        base_spread_bps=float(mm.get("base_spread_bps", 8)),
        min_spread_bps=float(mm.get("min_spread_bps", 5)),
        max_spread_bps=float(mm.get("max_spread_bps", 40)),
        maker_fee_bps=float(fees.get("maker_fee_bps", 0)),
        taker_fee_bps=float(fees.get("taker_fee_bps", 0)),
        volatility_multiplier=float(mm.get("volatility_multiplier", 1.0)),
    )
    quote_generator = QuoteGenerator(
        QuoteGeneratorConfig(
            fair_price_model=mm.get("fair_price_model", "microprice"),
            quote_placement_mode=mm.get("quote_placement_mode", "fair_price_bps"),
            spread=spread,
            inventory_skew_strength=float(mm.get("inventory_skew_strength", 0.5)),
            order_size=float(mm.get("order_size", 0.001)),
            max_inventory=float(mm.get("max_inventory", 0.01)),
            tick_size=float(mm.get("tick_size", 0.5)),
            lot_size=float(mm.get("lot_size", 0.0001)),
            min_order_size=float(mm.get("min_order_size", mm.get("lot_size", 0.0001))),
            min_notional=float(mm.get("min_notional", 5)),
        )
    )
    filters = config.get("filters", {})
    quote_source: Any = quote_generator
    fee_gate: FeeAwareGate | None = None
    side_gate: SideSelectionGate | None = None
    directional_gate: DirectionalFeatureGate | None = None
    if bool(filters.get("use_fee_aware_gate", False)):
        fee_gate = FeeAwareGate(
            maker_fee_bps=float(fees.get("maker_fee_bps", 0.0)),
            min_expected_edge_bps=float(filters.get("min_expected_edge_bps", 0.0)),
            adverse_selection_buffer_bps=float(filters.get("adverse_selection_buffer_bps", 0.0)),
            inventory_penalty_bps_per_unit=float(filters.get("inventory_penalty_bps_per_unit", 0.0)),
        )
    if bool(filters.get("use_side_selection_gate", False)):
        side_gate = SideSelectionGate(
            microprice_offset_threshold_bps=float(filters.get("microprice_offset_threshold_bps", 0.0)),
            inventory_soft_limit_ratio=float(filters.get("inventory_soft_limit_ratio", 1.0)),
            allowed_side_mode=str(filters.get("allowed_side_mode", "both")),
        )
    if bool(filters.get("use_directional_feature_gate", False)):
        directional_gate = DirectionalFeatureGate(
            microprice_offset_threshold_bps=float(filters.get("feature_microprice_offset_threshold_bps", 0.0)),
            imbalance_threshold=float(filters.get("feature_imbalance_threshold", 0.0)),
            trend_threshold_bps=float(filters.get("feature_trend_threshold_bps", 0.0)),
            max_volatility_bps=float(filters.get("feature_max_volatility_bps", 1.0e9)),
            edge_credit_bps=float(filters.get("feature_edge_credit_bps", 0.0)),
        )
    if bool(filters.get("use_adverse_selection_filter", False)):
        adverse_filter = AdverseSelectionFilter(
            AdverseSelectionConfig(
                max_imbalance=float(filters.get("max_imbalance", 0.8)),
                min_imbalance=float(filters.get("min_imbalance", 0.2)),
                disable_on_high_volatility=bool(filters.get("disable_on_high_volatility", True)),
                high_volatility_bps=float(filters.get("high_volatility_bps", 40.0)),
                disable_on_strong_trend=bool(filters.get("disable_on_strong_trend", True)),
            )
        )
        quote_source = StrategyQuoteAdapter(
            MarketMakingStrategy(
                quote_generator=quote_generator,
                adverse_filter=adverse_filter,
                fee_aware_gate=fee_gate,
                side_selection_gate=side_gate,
                directional_feature_gate=directional_gate,
            )
        )
    elif fee_gate is not None or side_gate is not None or directional_gate is not None:
        quote_source = StrategyQuoteAdapter(
            MarketMakingStrategy(
                quote_generator=quote_generator,
                fee_aware_gate=fee_gate,
                side_selection_gate=side_gate,
                directional_feature_gate=directional_gate,
            )
        )
    risk_engine = RiskEngine(
        RiskLimits(
            max_inventory=float(mm.get("max_inventory", 0.01)),
            max_position_value=float(risk.get("max_position_value", 500)),
            max_daily_loss=float(risk.get("max_daily_loss", 50)),
            max_open_orders=int(risk.get("max_open_orders", 2)),
            max_order_size=float(risk.get("max_order_size", 0.002)),
            max_allowed_spread_bps=float(risk.get("max_allowed_spread_bps", 80)),
            stale_order_book_ms=int(execution.get("stale_order_book_ms", 3000)),
            kill_on_websocket_disconnect=bool(risk.get("kill_on_websocket_disconnect", True)),
            kill_on_stale_order_book=bool(risk.get("kill_on_stale_order_book", True)),
            kill_on_spread_widening=bool(risk.get("kill_on_spread_widening", True)),
        )
    )
    return quote_source, PaperMarketMakingEngine(
        risk_engine=risk_engine,
        maker_fee_bps=float(fees.get("maker_fee_bps", 0)),
    )


def run_synthetic_paper(config: dict[str, Any], *, duration_seconds: int, output_dir: str | Path | None = None) -> dict[str, Any]:
    """Run the original deterministic synthetic paper simulation."""
    symbol = config.get("execution", {}).get("symbol", "PI_XBTUSD")
    output_dir = (
        Path(output_dir)
        if output_dir is not None
        else resolve_output_dir(
            config,
            timestamped_output=True,
            data_source="synthetic",
            fill_model="trade_through",
        )
    )
    quote_generator, engine = build_components(config)

    book = LocalOrderBook(symbol)
    now = datetime.now(timezone.utc)
    book.apply_snapshot(
        bids=[(50000.0, 2.0), (49999.5, 3.0)],
        asks=[(50001.0, 2.2), (50001.5, 2.8)],
        timestamp=now,
        sequence=1,
    )
    steps = max(1, min(duration_seconds, 3600))
    mark_price = 50000.5
    for step in range(steps):
        event_time = now + timedelta(seconds=step)
        book.apply_update(timestamp=event_time, sequence=step + 2)
        quote = quote_generator.generate(book=book, inventory=engine.account.inventory, recent_returns=[0.0, 0.0001])
        engine.place_quote(quote=quote, book=book, now=event_time)
        candidate_fills = (
            ((quote.bid_price, quote.bid_size), (quote.ask_price, quote.ask_size))
            if step % 2 == 0
            else ((quote.ask_price, quote.ask_size), (quote.bid_price, quote.bid_size))
        )
        trade_price, trade_quantity = next(
            (
                (price, quantity)
                for price, quantity in candidate_fills
                if price is not None and quantity > 0.0
            ),
            (None, 0.0),
        )
        if trade_price is not None and trade_quantity > 0.0:
            fills = engine.process_trade(
                Trade(
                    symbol=symbol,
                    price=float(trade_price),
                    quantity=float(trade_quantity),
                    timestamp=event_time,
                )
            )
            if fills:
                logging.info("step=%s fills=%s inventory=%.6f", step, len(fills), engine.account.inventory)
            mark_price = float(trade_price)
    summary = engine.write_report(
        output_dir,
        mark_price=mark_price,
        adverse_selection_filter_active=bool(config.get("filters", {}).get("use_adverse_selection_filter", False)),
    )
    _maybe_write_diagnostics(config, output_dir)
    logging.info("Paper run complete: %s", summary.to_dict())
    return summary.to_dict()


def run_csv_orderbook_replay(config: dict[str, Any], *, input_events: str | Path, output_dir: str | Path | None = None) -> dict[str, Any]:
    """Run paper market making on reconstructed Kraken order book CSV events."""
    events, input_event_count, skipped_events = load_orderbook_events(input_events)
    symbols = {event.symbol for event in events}
    if len(symbols) > 1:
        raise ValueError(
            "CSV market-making replay supports exactly one symbol per run; "
            f"found {sorted(symbols)}."
        )
    configured_symbol = str(config.get("execution", {}).get("symbol") or "").strip()
    if configured_symbol and symbols and symbols != {configured_symbol}:
        raise ValueError(
            f"CSV replay symbol {next(iter(symbols))!r} does not match configured "
            f"execution symbol {configured_symbol!r}."
        )
    output_dir = (
        Path(output_dir)
        if output_dir is not None
        else resolve_output_dir(
            config,
            timestamped_output=True,
            data_source="kraken_orderbook_csv",
            fill_model="top_of_book_crossing",
        )
    )
    quote_generator, engine = build_components(config)
    book: LocalOrderBook | None = None
    quoted_events = 0
    reconstructed_book_events = 0
    mark_price = 0.0
    recent_returns: deque[float] = deque(
        maxlen=int(config.get("market_making", {}).get("feature_return_lookback", 5))
    )
    previous_mid: float | None = None

    for idx, event in enumerate(events):
        if book is None or book.symbol != event.symbol:
            book = LocalOrderBook(event.symbol)
        book.apply_snapshot(
            bids=[(event.best_bid, event.bid_quantity)],
            asks=[(event.best_ask, event.ask_quantity)],
            timestamp=event.timestamp,
            sequence=event.sequence or event.update_id,
        )
        reconstructed_book_events += 1
        mark_price = book.mid_price or mark_price
        current_mid = book.mid_price
        if previous_mid is not None and current_mid is not None and previous_mid > 0:
            recent_returns.append((current_mid - previous_mid) / previous_mid)
        quote = quote_generator.generate(
            book=book,
            inventory=engine.account.inventory,
            recent_returns=list(recent_returns),
        )
        placed = engine.place_quote(quote=quote, book=book, now=event.timestamp)
        if placed:
            quoted_events += 1
        else:
            skipped_events += 1
        if idx + 1 < len(events):
            next_event = events[idx + 1]
            fills = engine.process_top_of_book_crossing(
                symbol=event.symbol,
                best_bid=next_event.best_bid,
                best_ask=next_event.best_ask,
                timestamp=next_event.timestamp,
            )
            if fills:
                logging.info("event=%s fills=%s inventory=%.6f", idx, len(fills), engine.account.inventory)
            mark_price = (next_event.best_bid + next_event.best_ask) / 2.0
        previous_mid = current_mid

    summary = engine.write_report(
        output_dir,
        mark_price=mark_price,
        input_events=input_event_count,
        quoted_events=quoted_events,
        skipped_events=skipped_events,
        reconstructed_book_events=reconstructed_book_events,
        fill_model="top_of_book_crossing",
        data_source="kraken_orderbook_csv",
        adverse_selection_filter_active=bool(config.get("filters", {}).get("use_adverse_selection_filter", False)),
    )
    _maybe_write_diagnostics(config, output_dir, orderbook_events_path=input_events)
    logging.info("Kraken CSV paper run complete: %s", summary.to_dict())
    return summary.to_dict()


def _maybe_write_diagnostics(
    config: dict[str, Any],
    output_dir: str | Path,
    *,
    orderbook_events_path: str | Path | None = None,
) -> None:
    diag_cfg = config.get("diagnostics", {})
    enabled = bool(diag_cfg.get("enabled", True))
    if not enabled:
        return
    try:
        diagnostics = write_market_making_diagnostics(
            output_dir,
            orderbook_events_path=orderbook_events_path,
            markout_horizons=diag_cfg.get("markout_horizons", [1, 5, 10, 30]),
            max_inventory=config.get("market_making", {}).get("max_inventory"),
            make_plots=bool(diag_cfg.get("make_plots", True)),
        )
        if bool(diag_cfg.get("make_report", True)):
            write_market_making_markdown_report(output_dir, diagnostics)
    except Exception as exc:
        logging.exception("Market-making diagnostics generation failed: %s", exc)


def resolve_output_dir(
    config: dict[str, Any],
    *,
    explicit_output_dir: str | None = None,
    timestamped_output: bool = False,
    data_source: str = "synthetic",
    fill_model: str = "trade_through",
    now: datetime | None = None,
) -> Path:
    """Resolve run output directory using CLI > timestamped > YAML precedence."""
    if explicit_output_dir:
        return Path(explicit_output_dir)
    yaml_output = Path(config.get("logging", {}).get("output_dir", "logs/experiments/market_making"))
    if not timestamped_output:
        return yaml_output
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d_%H%M%S")
    return yaml_output / "runs" / f"{stamp}_{data_source}_{fill_model}"


def load_orderbook_events(path: str | Path) -> tuple[list[ReconstructedBookEvent], int, int]:
    """Load collector CSV rows as timestamp-sorted reconstructed top-of-book events."""
    events: list[ReconstructedBookEvent] = []
    input_event_count = 0
    skipped_events = 0
    with Path(path).open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            input_event_count += 1
            event = _parse_orderbook_event(row)
            if event is None:
                skipped_events += 1
            else:
                events.append(event)
    events.sort(key=lambda event: event.timestamp)
    return events, input_event_count, skipped_events


def _parse_orderbook_event(row: dict[str, str]) -> ReconstructedBookEvent | None:
    try:
        symbol = (row.get("symbol") or "").strip()
        if not symbol:
            return None
        best_bid = _optional_float(row.get("best_bid"))
        best_ask = _optional_float(row.get("best_ask"))
        if best_bid is None or best_ask is None or best_bid <= 0 or best_ask <= 0 or best_bid >= best_ask:
            return None
        bid_quantity = _positive_or_fallback(_optional_float(row.get("bid_depth_5")), fallback=1.0)
        ask_quantity = _positive_or_fallback(_optional_float(row.get("ask_depth_5")), fallback=1.0)
        return ReconstructedBookEvent(
            timestamp=_parse_timestamp(row.get("timestamp")),
            symbol=symbol,
            best_bid=best_bid,
            best_ask=best_ask,
            bid_quantity=bid_quantity,
            ask_quantity=ask_quantity,
            sequence=_optional_int(row.get("sequence")),
            update_id=_optional_int(row.get("update_id")),
        )
    except (TypeError, ValueError):
        return None


def _parse_timestamp(value: str | None) -> datetime:
    if not value:
        raise ValueError("timestamp is required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _optional_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def _optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(float(value))


def _positive_or_fallback(value: float | None, *, fallback: float) -> float:
    if value is None or value <= 0:
        return fallback
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic market-making paper simulation.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--duration-seconds", type=int, default=60)
    parser.add_argument("--input-events", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--timestamped-output", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    mode = config.get("execution", {}).get("mode")
    if args.input_events is None and mode != "paper":
        raise SystemExit("Synthetic paper runner requires execution.mode: paper.")
    if args.input_events is not None and mode not in {"paper", "data_only"}:
        raise SystemExit("Kraken CSV paper runner requires execution.mode: paper or data_only.")
    logging.basicConfig(level=getattr(logging, config.get("logging", {}).get("level", "INFO")))
    if args.input_events:
        run_csv_orderbook_replay(config, input_events=args.input_events, output_dir=args.output_dir)
    else:
        run_synthetic_paper(config, duration_seconds=args.duration_seconds, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
