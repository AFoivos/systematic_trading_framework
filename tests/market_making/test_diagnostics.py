from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.market_making.diagnostics import (
    _to_datetime,
    build_market_making_diagnostics,
    discover_market_making_runs,
    write_market_making_comparison,
    write_market_making_diagnostics,
)


def _write_run(path: Path, *, with_quote_events: bool = True) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "summary.json").write_text(
        json.dumps(
            {
                "total_pnl": 1.5,
                "realized_pnl": 1.0,
                "unrealized_pnl": 0.5,
                "fees": 0.1,
                "number_of_fills": 2,
                "number_of_quotes": 3,
                "number_of_cancels": 1,
                "fill_ratio": 0.5,
                "average_spread_quoted": 10.0,
                "average_inventory": 0.1,
                "max_inventory": 0.2,
                "max_drawdown": 0.3,
                "kill_switch_events": [],
                "runtime_errors": 0,
                "reconnects": 0,
                "input_events": 4,
                "quoted_events": 3,
                "skipped_events": 1,
                "fill_model": "top_of_book_crossing",
                "data_source": "kraken_orderbook_csv",
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {"order_id": "paper-1", "symbol": "BTC/USD", "side": "buy", "price": 100.0, "quantity": 1.0, "timestamp": "2026-07-01T00:00:00+00:00", "status": "open", "parent_quote_event_id": "quote-1"},
            {"order_id": "paper-2", "symbol": "BTC/USD", "side": "sell", "price": 102.0, "quantity": 1.0, "timestamp": "2026-07-01T00:00:01+00:00", "status": "open", "parent_quote_event_id": "quote-2"},
        ]
    ).to_csv(path / "orders.csv", index=False)
    pd.DataFrame(
        [
            {"order_id": "paper-1", "symbol": "BTC/USD", "side": "buy", "price": 100.0, "quantity": 1.0, "fee": 0.01, "timestamp": "2026-07-01T00:00:02+00:00", "parent_quote_event_id": "quote-1"},
            {"order_id": "paper-2", "symbol": "BTC/USD", "side": "sell", "price": 102.0, "quantity": 1.0, "fee": 0.01, "timestamp": "2026-07-01T00:00:03+00:00", "parent_quote_event_id": "quote-2"},
        ]
    ).to_csv(path / "trades.csv", index=False)
    pd.DataFrame(
        [
            {"timestamp": "2026-07-01T00:00:00+00:00", "realized_pnl": 0.0, "unrealized_pnl": 0.0, "total_pnl": 0.0, "fees": 0.0},
            {"timestamp": "2026-07-01T00:00:03+00:00", "realized_pnl": 1.0, "unrealized_pnl": 0.5, "total_pnl": 1.5, "fees": 0.1},
        ]
    ).to_csv(path / "pnl_timeseries.csv", index=False)
    pd.DataFrame(
        [
            {"timestamp": "2026-07-01T00:00:00+00:00", "inventory": 0.0, "mark_price": 101.0},
            {"timestamp": "2026-07-01T00:00:01+00:00", "inventory": 1.0, "mark_price": 101.0},
            {"timestamp": "2026-07-01T00:00:03+00:00", "inventory": 0.0, "mark_price": 102.0},
        ]
    ).to_csv(path / "inventory_timeseries.csv", index=False)
    pd.DataFrame(
        [
            {"timestamp": "2026-07-01T00:00:00+00:00", "symbol": "BTC/USD", "event_type": "snapshot", "best_bid": 100.0, "best_ask": 101.0, "mid_price": 100.5, "spread": 1.0, "spread_bps": 99.5, "imbalance_1": 0.5, "imbalance_5": 0.5, "bid_depth_5": 2.0, "ask_depth_5": 2.0, "sequence": 1},
            {"timestamp": "2026-07-01T00:00:01+00:00", "symbol": "BTC/USD", "event_type": "update", "best_bid": 100.5, "best_ask": 101.5, "mid_price": 101.0, "spread": 1.0, "spread_bps": 99.0, "imbalance_1": 0.6, "imbalance_5": 0.6, "bid_depth_5": 3.0, "ask_depth_5": 2.0, "sequence": 2},
            {"timestamp": "2026-07-01T00:00:02+00:00", "symbol": "BTC/USD", "event_type": "update", "best_bid": 101.0, "best_ask": 100.8, "mid_price": 100.9, "spread": -0.2, "spread_bps": -19.8, "imbalance_1": 0.7, "imbalance_5": 0.7, "bid_depth_5": 3.0, "ask_depth_5": 1.0, "sequence": 3},
            {"timestamp": "2026-07-01T00:00:03+00:00", "symbol": "BTC/USD", "event_type": "update", "best_bid": None, "best_ask": 102.0, "mid_price": None, "spread": None, "spread_bps": None, "imbalance_1": None, "imbalance_5": None, "bid_depth_5": 0.0, "ask_depth_5": 1.0, "sequence": 4},
            {"timestamp": "2026-07-01T00:00:04+00:00", "symbol": "BTC/USD", "event_type": "update", "best_bid": 102.0, "best_ask": 103.0, "mid_price": 102.5, "spread": 1.0, "spread_bps": 97.5, "imbalance_1": 0.5, "imbalance_5": 0.5, "bid_depth_5": 1.0, "ask_depth_5": 1.0, "sequence": 6},
        ]
    ).to_csv(path / "orderbook_events.csv", index=False)
    if with_quote_events:
        pd.DataFrame(
            [
                {"quote_event_id": "quote-1", "timestamp": "2026-07-01T00:00:00+00:00", "symbol": "BTC/USD", "fair_price": 100.5, "bid_price": 100.0, "ask_price": 101.0, "bid_size": 1.0, "ask_size": 1.0, "spread_bps": 99.5, "inventory": 0.0, "inventory_ratio": 0.0, "book_best_bid": 100.0, "book_best_ask": 101.0, "book_mid_price": 100.5, "book_spread_bps": 99.5, "book_imbalance_1": 0.5, "book_imbalance_5": 0.5, "should_quote": True, "quote_reason": "ok", "risk_allowed": True, "risk_reason": "ok", "risk_cancel_all": False, "risk_kill_switch": False, "placed": True, "bid_order_id": "paper-1", "ask_order_id": None},
                {"quote_event_id": "quote-2", "timestamp": "2026-07-01T00:00:01+00:00", "symbol": "BTC/USD", "fair_price": 101.0, "bid_price": None, "ask_price": None, "bid_size": 0.0, "ask_size": 0.0, "spread_bps": 99.0, "inventory": 1.0, "inventory_ratio": 1.0, "book_best_bid": 100.5, "book_best_ask": 101.5, "book_mid_price": 101.0, "book_spread_bps": 99.0, "book_imbalance_1": 0.6, "book_imbalance_5": 0.6, "should_quote": False, "quote_reason": "invalid quote prices", "risk_allowed": False, "risk_reason": "max open orders exceeded", "risk_cancel_all": False, "risk_kill_switch": False, "placed": False, "bid_order_id": None, "ask_order_id": None},
            ]
        ).to_csv(path / "quote_events.csv", index=False)


def test_diagnostics_handles_missing_optional_files_with_warnings(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "summary.json").write_text("{}", encoding="utf-8")

    diagnostics = build_market_making_diagnostics(run)

    assert diagnostics["quote"]["quote_event_logging_missing"] is True
    assert diagnostics["gaps"]["quote_events_missing"] is True
    assert diagnostics["warnings"]


def test_to_datetime_accepts_mixed_iso_timestamp_formats() -> None:
    parsed = _to_datetime(
        pd.Series(
            [
                "2026-07-01T20:27:01.284919+00:00",
                "2026-07-01T20:27:23+00:00",
            ]
        )
    )

    assert parsed.notna().all()


def test_diagnostics_reads_artifacts_and_writes_summary(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_run(run)

    diagnostics = write_market_making_diagnostics(run, max_inventory=2.0, make_plots=False)

    assert set(["run", "quote", "fill", "pnl", "inventory", "market_quality", "risk", "markout", "adverse_selection", "gaps", "warnings", "artifacts"]).issubset(diagnostics)
    assert (run / "diagnostics" / "summary.json").exists()
    assert (run / "diagnostics" / "gaps.json").exists()
    assert (run / "diagnostics" / "quote_diagnostics.csv").exists()
    assert not list(run.rglob("*.pptx"))


def test_saved_summary_contains_plot_artifact_paths(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_run(run)

    write_market_making_diagnostics(run, max_inventory=2.0, make_plots=True)
    saved = json.loads((run / "diagnostics" / "summary.json").read_text(encoding="utf-8"))

    assert "event_funnel.png" in saved["artifacts"]
    assert "pnl_curve.png" in saved["artifacts"]
    assert "inventory_timeseries.png" in saved["artifacts"]


def test_quote_and_risk_diagnostics_compute_reject_rates(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_run(run)

    diagnostics = build_market_making_diagnostics(run)

    assert diagnostics["quote"]["placed_quote_count"] == 1
    assert diagnostics["quote"]["rejected_quote_count"] == 1
    assert diagnostics["risk"]["max_open_orders_reject_count"] == 1


def test_fill_diagnostics_counts_sides(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_run(run)

    diagnostics = build_market_making_diagnostics(run)

    assert diagnostics["fill"]["buy_fill_count"] == 1
    assert diagnostics["fill"]["sell_fill_count"] == 1


def test_markout_signs_for_buy_and_sell(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_run(run)

    diagnostics = build_market_making_diagnostics(run, markout_horizons=(1,))

    assert diagnostics["markout"]["markout_unavailable"] is False
    assert diagnostics["markout"]["avg_markout_bps_h1"] is not None


def test_markout_expected_values_and_adverse_selection_rate(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "summary.json").write_text("{}", encoding="utf-8")
    pd.DataFrame(
        [
            {"order_id": "b1", "symbol": "BTC/USD", "side": "buy", "price": 100.0, "quantity": 1.0, "fee": 0.0, "timestamp": "2026-07-01T00:00:00+00:00", "parent_quote_event_id": "q1"},
            {"order_id": "b2", "symbol": "BTC/USD", "side": "buy", "price": 100.0, "quantity": 1.0, "fee": 0.0, "timestamp": "2026-07-01T00:00:01+00:00", "parent_quote_event_id": "q2"},
            {"order_id": "s1", "symbol": "BTC/USD", "side": "sell", "price": 100.0, "quantity": 1.0, "fee": 0.0, "timestamp": "2026-07-01T00:00:02+00:00", "parent_quote_event_id": "q3"},
            {"order_id": "s2", "symbol": "BTC/USD", "side": "sell", "price": 100.0, "quantity": 1.0, "fee": 0.0, "timestamp": "2026-07-01T00:00:03+00:00", "parent_quote_event_id": "q4"},
        ]
    ).to_csv(run / "trades.csv", index=False)
    pd.DataFrame(
        [
            {"timestamp": "2026-07-01T00:00:00.500000+00:00", "symbol": "BTC/USD", "event_type": "update", "best_bid": 100.5, "best_ask": 101.5, "mid_price": 101.0, "spread": 1.0, "spread_bps": 99.0, "imbalance_1": 0.5, "imbalance_5": 0.5, "bid_depth_5": 1.0, "ask_depth_5": 1.0},
            {"timestamp": "2026-07-01T00:00:01.500000+00:00", "symbol": "BTC/USD", "event_type": "update", "best_bid": 98.5, "best_ask": 99.5, "mid_price": 99.0, "spread": 1.0, "spread_bps": 101.0, "imbalance_1": 0.5, "imbalance_5": 0.5, "bid_depth_5": 1.0, "ask_depth_5": 1.0},
            {"timestamp": "2026-07-01T00:00:02.500000+00:00", "symbol": "BTC/USD", "event_type": "update", "best_bid": 98.5, "best_ask": 99.5, "mid_price": 99.0, "spread": 1.0, "spread_bps": 101.0, "imbalance_1": 0.5, "imbalance_5": 0.5, "bid_depth_5": 1.0, "ask_depth_5": 1.0},
            {"timestamp": "2026-07-01T00:00:03.500000+00:00", "symbol": "BTC/USD", "event_type": "update", "best_bid": 100.5, "best_ask": 101.5, "mid_price": 101.0, "spread": 1.0, "spread_bps": 99.0, "imbalance_1": 0.5, "imbalance_5": 0.5, "bid_depth_5": 1.0, "ask_depth_5": 1.0},
        ]
    ).to_csv(run / "orderbook_events.csv", index=False)

    diagnostics = build_market_making_diagnostics(run, markout_horizons=(1,))

    assert diagnostics["markout"]["avg_markout_bps_h1"] == 0.0
    assert diagnostics["markout"]["adverse_selection_rate_h1"] == 0.5


def test_adverse_selection_diagnostics_attach_fill_context(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_run(run)

    diagnostics = build_market_making_diagnostics(run, markout_horizons=(1, 5))
    context = diagnostics["_tables"]["adverse_selection_diagnostics"]

    assert diagnostics["adverse_selection"]["adverse_selection_context_available"] is True
    assert diagnostics["gaps"]["missing_adverse_selection_filter_diagnostics"] is False
    assert not context.empty
    assert {
        "quote_reason",
        "risk_reason",
        "filter_decision",
        "book_imbalance_1",
        "recent_mid_slope_bps_5",
        "recent_mid_volatility_bps_5",
        "markout_bps_h1",
    }.issubset(context.columns)


def test_comparison_uses_saved_diagnostics_summary_for_external_orderbook_context(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports"
    run = reports_root / "market_making" / "runs" / "20260701_000000_test"
    _write_run(run)
    external_orderbook = tmp_path / "external_orderbook_events.csv"
    (run / "orderbook_events.csv").replace(external_orderbook)
    write_market_making_diagnostics(run, orderbook_events_path=external_orderbook, make_plots=False)

    artifacts = write_market_making_comparison([run], reports_root / "market_making_comparison")
    frame = pd.read_csv(artifacts["summary"])

    assert len(frame) == 1
    assert pd.notna(frame.loc[0, "avg_markout_bps_h1"])
    assert "fee_drag_ratio" in frame.columns
    assert "inventory_limit_utilization" in frame.columns


def test_comparison_writes_all_discovered_runs(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports"
    top_level = reports_root / "market_making"
    run_a = top_level / "runs" / "20260701_010101_run_a"
    run_b = top_level / "runs" / "20260701_020202_run_b"
    _write_run(top_level)
    _write_run(run_a)
    _write_run(run_b)

    artifacts = write_market_making_comparison(discover_market_making_runs(reports_root), reports_root / "market_making_comparison")
    frame = pd.read_csv(artifacts["summary"])

    assert len(frame) == 3
    assert set(["avg_markout_bps_h5", "adverse_selection_rate_h5", "quoted_event_rate", "fills_per_placed_quote"]).issubset(frame.columns)


def test_market_quality_detects_crossed_and_missing_books(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_run(run)

    diagnostics = build_market_making_diagnostics(run)

    assert diagnostics["market_quality"]["crossed_book_count"] == 1
    assert diagnostics["market_quality"]["missing_top_of_book_count"] == 1
    assert diagnostics["market_quality"]["possible_sequence_gap_count"] == 1


def test_gap_detector_flags_low_fill_count_and_missing_quote_events(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_run(run, with_quote_events=False)

    diagnostics = build_market_making_diagnostics(run)

    assert diagnostics["gaps"]["fill_count_too_low_for_edge_evaluation"] is True
    assert diagnostics["gaps"]["quote_events_missing"] is True


def test_discover_market_making_runs_finds_report_dirs(tmp_path: Path) -> None:
    run = tmp_path / "reports" / "market_making"
    _write_run(run)

    runs = discover_market_making_runs(tmp_path / "reports")

    assert run in runs
