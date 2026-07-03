from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.run_market_making_pipeline import run_pipeline


def _write_fixture_inputs(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    orderbook = root / "orderbook_events.csv"
    quotes = root / "quote_events.csv"
    trades = root / "trades.csv"
    orderbook_rows = []
    quote_rows = []
    for idx in range(12):
        mid = 100.0 + idx * 0.1
        orderbook_rows.append(
            {
                "timestamp": f"2026-07-01T00:00:{idx:02d}+00:00",
                "symbol": "BTC/USD",
                "event_type": "update",
                "best_bid": mid - 0.05,
                "best_ask": mid + 0.05,
                "mid_price": mid,
                "spread": 0.1,
                "spread_bps": 10.0,
                "imbalance_1": 0.55 if idx % 2 == 0 else 0.45,
                "imbalance_5": 0.54 if idx % 2 == 0 else 0.46,
                "bid_depth_1": 2.0,
                "ask_depth_1": 1.5,
                "bid_depth_5": 5.0,
                "ask_depth_5": 4.0,
                "bid_depth_10": 8.0,
                "ask_depth_10": 7.0,
                "sequence": idx,
            }
        )
        if idx < 10:
            quote_rows.append(
                {
                    "quote_event_id": f"quote-{idx}",
                    "timestamp": f"2026-07-01T00:00:{idx:02d}+00:00",
                    "symbol": "BTC/USD",
                    "fair_price": mid,
                    "bid_price": mid - 0.05,
                    "ask_price": mid + 0.05,
                    "bid_size": 1.0,
                    "ask_size": 1.0,
                    "spread_bps": 10.0,
                    "inventory": 0.0,
                    "inventory_ratio": 0.0,
                    "book_best_bid": mid - 0.05,
                    "book_best_ask": mid + 0.05,
                    "book_mid_price": mid,
                    "book_spread_bps": 10.0,
                    "book_imbalance_1": 0.55 if idx % 2 == 0 else 0.45,
                    "book_imbalance_5": 0.54 if idx % 2 == 0 else 0.46,
                    "should_quote": True,
                    "quote_reason": "ok",
                    "risk_allowed": True,
                    "risk_reason": "ok",
                    "risk_cancel_all": False,
                    "risk_kill_switch": False,
                    "placed": True,
                    "bid_order_id": f"bid-{idx}",
                    "ask_order_id": f"ask-{idx}",
                }
            )
    pd.DataFrame(orderbook_rows).to_csv(orderbook, index=False)
    pd.DataFrame(quote_rows).to_csv(quotes, index=False)
    pd.DataFrame(
        [
            {
                "order_id": "bid-1",
                "symbol": "BTC/USD",
                "side": "buy",
                "price": 100.0,
                "quantity": 1.0,
                "fee": 0.01,
                "timestamp": "2026-07-01T00:00:02+00:00",
                "parent_quote_event_id": "quote-1",
            }
        ]
    ).to_csv(trades, index=False)
    return {"orderbook": orderbook, "quotes": quotes, "trades": trades}


def test_pipeline_uses_existing_data_without_collection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pd.DataFrame,
        "to_parquet",
        lambda self, path, **_: Path(path).write_text(self.to_csv(index=False), encoding="utf-8"),
    )
    paths = _write_fixture_inputs(tmp_path / "source")
    cfg = {
        "pipeline": {
            "output_dir": str(tmp_path / "pipeline"),
            "collect_orderbook": {"enabled": False},
            "paper_replay": {"enabled": False},
            "moment_experiment": {"enabled": True},
        },
        "data": {
            "orderbook_events_path": str(paths["orderbook"]),
            "quote_events_paths": [str(paths["quotes"])],
            "trades_path": str(paths["trades"]),
            "moment_dataset": {
                "path": str(tmp_path / "cache" / "moment_dataset.parquet"),
                "reuse_existing": False,
                "horizons": [1, 5],
            },
        },
        "fees": {"maker_fee_bps": 1.0},
        "market_making": {"max_inventory": 1.0},
        "moment": {
            "enabled": True,
            "backend": "deterministic_fixture",
            "checkpoint": "AutonLab/MOMENT-1-large",
            "lookback_length": 8,
            "target_horizon": "h5",
        },
        "moment_filter": {"expected_spread_capture_bps": 1.0, "safety_buffer_bps": 0.1, "max_uncertainty": 100.0},
        "split": {"train_fraction": 0.5, "validation_fraction": 0.2},
        "moment_output": {
            "root": str(tmp_path / "logs" / "experiments"),
            "run_name": "pipeline_moment_fixture",
            "write_report": True,
        },
        "runtime": {"random_seed": 7, "deterministic": True},
    }

    result = run_pipeline(cfg, config_path=tmp_path / "pipeline.yaml")

    assert result["stages"]["collect_orderbook"]["status"] == "skipped"
    assert result["stages"]["paper_replay"]["status"] == "skipped"
    assert result["stages"]["moment_experiment"]["status"] == "completed"
    manifest_path = Path(result["manifest_path"])
    moment_run_dir = Path(result["stages"]["moment_experiment"]["run_dir"])
    summary = json.loads((moment_run_dir / "summary.json").read_text(encoding="utf-8"))

    assert manifest_path.exists()
    assert (moment_run_dir / "moment_predictions.csv").exists()
    assert summary["moment_summary"]["backend"] == "deterministic_fixture"
