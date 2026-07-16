from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.run_market_making_paper import (
    load_orderbook_events,
    resolve_output_dir,
    run_csv_orderbook_replay,
    run_synthetic_paper,
)


def _config(output_dir: str) -> dict[str, object]:
    return {
        "execution": {
            "mode": "data_only",
            "stale_order_book_ms": 10_000,
        },
        "market_making": {
            "fair_price_model": "mid_price",
            "spread_model": "fixed",
            "base_spread_bps": 100,
            "min_spread_bps": 100,
            "max_spread_bps": 100,
            "inventory_skew_strength": 0.0,
            "order_size": 1.0,
            "max_inventory": 10.0,
            "tick_size": 0.01,
            "lot_size": 0.1,
            "min_order_size": 0.1,
            "min_notional": 1.0,
        },
        "fees": {
            "maker_fee_bps": 0,
            "taker_fee_bps": 0,
        },
        "risk": {
            "max_daily_loss": 1_000,
            "max_position_value": 10_000,
            "max_open_orders": 2,
            "max_order_size": 2.0,
            "max_allowed_spread_bps": 500,
            "kill_on_websocket_disconnect": True,
            "kill_on_stale_order_book": True,
            "kill_on_spread_widening": True,
        },
        "logging": {
            "level": "INFO",
            "output_dir": output_dir,
        },
    }


def _write_events(path) -> None:
    rows = [
        {
            "timestamp": "2026-07-01T12:00:00+00:00",
            "symbol": "BTC/USD",
            "event_type": "snapshot",
            "best_bid": "100.0",
            "best_ask": "101.0",
            "mid_price": "100.5",
            "spread": "1.0",
            "spread_bps": "99.5",
            "imbalance_1": "0.5",
            "imbalance_5": "0.5",
            "bid_depth_5": "2.0",
            "ask_depth_5": "3.0",
            "sequence": "1",
            "update_id": "",
            "checksum": "",
        },
        {
            "timestamp": "2026-07-01T12:00:01+00:00",
            "symbol": "BTC/USD",
            "event_type": "update",
            "best_bid": "99.0",
            "best_ask": "99.9",
            "mid_price": "99.45",
            "spread": "0.9",
            "spread_bps": "90.5",
            "imbalance_1": "0.5",
            "imbalance_5": "0.5",
            "bid_depth_5": "1.0",
            "ask_depth_5": "1.0",
            "sequence": "2",
            "update_id": "",
            "checksum": "",
        },
        {
            "timestamp": "2026-07-01T12:00:02+00:00",
            "symbol": "BTC/USD",
            "event_type": "update",
            "best_bid": "101.2",
            "best_ask": "102.0",
            "mid_price": "101.6",
            "spread": "0.8",
            "spread_bps": "78.7",
            "imbalance_1": "0.5",
            "imbalance_5": "0.5",
            "bid_depth_5": "1.0",
            "ask_depth_5": "1.0",
            "sequence": "3",
            "update_id": "",
            "checksum": "",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_load_orderbook_events_sorts_and_reconstructs_quantities(tmp_path) -> None:
    events_path = tmp_path / "orderbook_events.csv"
    _write_events(events_path)

    events, input_count, skipped = load_orderbook_events(events_path)

    assert input_count == 3
    assert skipped == 0
    assert [event.sequence for event in events] == [1, 2, 3]
    assert events[0].bid_quantity == 2.0
    assert events[0].ask_quantity == 3.0


def test_load_orderbook_events_skips_non_finite_top_of_book_values(tmp_path) -> None:
    events_path = tmp_path / "orderbook_events.csv"
    _write_events(events_path)
    with events_path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["best_bid"] = "nan"
    rows[1]["best_ask"] = "inf"
    with events_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    events, input_count, skipped = load_orderbook_events(events_path)

    assert input_count == 3
    assert skipped == 2
    assert len(events) == 1


def test_csv_replay_writes_reports_and_summary_metadata(tmp_path) -> None:
    events_path = tmp_path / "orderbook_events.csv"
    output_root = tmp_path / "reports"
    _write_events(events_path)

    config = _config(str(output_root))
    summary = run_csv_orderbook_replay(config, input_events=events_path)

    assert summary["input_events"] == 3
    assert summary["quoted_events"] == 3
    assert summary["skipped_events"] == 0
    assert summary["reconstructed_book_events"] == 3
    assert summary["fill_model"] == "top_of_book_crossing"
    assert summary["data_source"] == "kraken_orderbook_csv"
    assert summary["number_of_fills"] >= 1

    run_dirs = sorted((output_root / "runs").iterdir())
    assert len(run_dirs) == 1
    summary_path = run_dirs[0] / "summary.json"
    assert summary_path.exists()
    persisted_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert persisted_summary["fill_model"] == "top_of_book_crossing"
    assert (run_dirs[0] / "orders.csv").exists()
    assert (run_dirs[0] / "trades.csv").exists()
    assert (run_dirs[0] / "pnl_timeseries.csv").exists()
    assert (run_dirs[0] / "inventory_timeseries.csv").exists()


def test_csv_replay_with_join_top_of_book_quotes_without_breaking(tmp_path) -> None:
    events_path = tmp_path / "orderbook_events.csv"
    output_dir = tmp_path / "join_reports"
    config = _config(str(output_dir))
    config["market_making"]["quote_placement_mode"] = "join_top_of_book"
    _write_events(events_path)

    summary = run_csv_orderbook_replay(config, input_events=events_path)

    assert summary["quoted_events"] >= 1
    assert summary["data_source"] == "kraken_orderbook_csv"
    assert summary["fill_model"] == "top_of_book_crossing"


def test_csv_replay_rejects_multiple_symbols_before_cross_symbol_fills(tmp_path) -> None:
    events_path = tmp_path / "orderbook_events.csv"
    _write_events(events_path)
    with events_path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows[1]["symbol"] = "ETH/USD"
    with events_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError, match="exactly one symbol"):
        run_csv_orderbook_replay(_config(str(tmp_path / "reports")), input_events=events_path)


def test_csv_replay_rejects_configured_symbol_mismatch(tmp_path) -> None:
    events_path = tmp_path / "orderbook_events.csv"
    _write_events(events_path)
    config = _config(str(tmp_path / "reports"))
    config["execution"]["symbol"] = "ETH/USD"

    with pytest.raises(ValueError, match="does not match configured"):
        run_csv_orderbook_replay(config, input_events=events_path)


def test_timestamped_output_path_and_explicit_override(tmp_path) -> None:
    config = _config(str(tmp_path / "yaml_reports"))
    now = datetime(2026, 7, 2, 15, 30, 0, tzinfo=timezone.utc)

    explicit = resolve_output_dir(config, explicit_output_dir=str(tmp_path / "custom"), timestamped_output=True, now=now)
    timestamped = resolve_output_dir(config, timestamped_output=True, data_source="kraken_orderbook_csv", fill_model="top_of_book_crossing", now=now)
    legacy = resolve_output_dir(config, timestamped_output=False, now=now)

    assert explicit == tmp_path / "custom"
    assert timestamped == tmp_path / "yaml_reports" / "runs" / "20260702_153000_kraken_orderbook_csv_top_of_book_crossing"
    assert legacy == tmp_path / "yaml_reports"


def test_default_market_making_output_root_is_logs_experiments() -> None:
    assert resolve_output_dir({"logging": {}}) == Path("logs/experiments/market_making")


def test_csv_replay_with_adverse_filter_records_rejected_quote(tmp_path) -> None:
    events_path = tmp_path / "orderbook_events.csv"
    output_root = tmp_path / "filtered_reports"
    config = _config(str(output_root))
    config["market_making"]["quote_placement_mode"] = "join_top_of_book"
    config["filters"] = {
        "use_adverse_selection_filter": True,
        "max_imbalance": 0.8,
        "min_imbalance": 0.2,
        "disable_on_high_volatility": False,
        "disable_on_strong_trend": False,
    }
    rows = [
        {
            "timestamp": "2026-07-01T12:00:00+00:00",
            "symbol": "BTC/USD",
            "event_type": "snapshot",
            "best_bid": "100.0",
            "best_ask": "101.0",
            "mid_price": "100.5",
            "spread": "1.0",
            "spread_bps": "99.5",
            "imbalance_1": "0.95",
            "imbalance_5": "0.95",
            "bid_depth_5": "95.0",
            "ask_depth_5": "5.0",
            "sequence": "1",
            "update_id": "",
            "checksum": "",
        }
    ]
    with events_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = run_csv_orderbook_replay(config, input_events=events_path)

    assert summary["quoted_events"] == 0
    assert summary["skipped_events"] == 1
    run_dirs = sorted((output_root / "runs").iterdir())
    assert len(run_dirs) == 1
    quote_events = (run_dirs[0] / "quote_events.csv").read_text(encoding="utf-8")
    assert "extreme bid-side imbalance" in quote_events


def test_csv_replay_with_filter_disabled_places_same_book(tmp_path) -> None:
    events_path = tmp_path / "orderbook_events.csv"
    output_dir = tmp_path / "unfiltered_reports"
    config = _config(str(output_dir))
    config["market_making"]["quote_placement_mode"] = "join_top_of_book"
    config["filters"] = {"use_adverse_selection_filter": False}
    _write_events(events_path)

    summary = run_csv_orderbook_replay(config, input_events=events_path)

    assert summary["quoted_events"] >= 1


def test_synthetic_mode_still_writes_synthetic_summary(tmp_path) -> None:
    output_root = tmp_path / "synthetic_reports"
    config = _config(str(output_root))
    config["execution"]["mode"] = "paper"
    config["execution"]["symbol"] = "BTC/USD"

    summary = run_synthetic_paper(config, duration_seconds=2)

    assert summary["data_source"] == "synthetic"
    assert summary["fill_model"] == "trade_through"
    assert summary["input_events"] == 0
    run_dirs = sorted((output_root / "runs").iterdir())
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "summary.json").exists()


def test_synthetic_mode_uses_active_side_size_for_one_sided_quotes(tmp_path) -> None:
    output_root = tmp_path / "synthetic_one_sided"
    config = _config(str(output_root))
    config["execution"]["mode"] = "paper"
    config["execution"]["symbol"] = "BTC/USD"
    config["filters"] = {
        "use_side_selection_gate": True,
        "allowed_side_mode": "sell_only",
    }
    config["risk"]["max_position_value"] = 100_000

    summary = run_synthetic_paper(config, duration_seconds=2)

    assert summary["number_of_fills"] >= 1
    assert summary["data_source"] == "synthetic"
