from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from scripts.run_market_making_moment_experiment import run_experiment
from src.market_making.moment_dataset import (
    assert_no_target_leakage,
    build_market_making_moment_dataset,
    chronological_split,
    feature_columns,
)
from src.market_making.moment_model import MomentDependencyError, MomentModelConfig, MomentResearchModel
from src.market_making.moment_quote_filter import MomentQuoteFilter, MomentQuoteFilterConfig


def _write_fixture_inputs(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    orderbook = root / "orderbook_events.csv"
    quotes = root / "quote_events.csv"
    trades = root / "trades.csv"
    rows = []
    for idx in range(12):
        mid = 100.0 + idx * 0.1
        rows.append(
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
    pd.DataFrame(rows).to_csv(orderbook, index=False)
    quote_rows = []
    for idx in range(10):
        mid = 100.0 + idx * 0.1
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
                "inventory": 0.1 if idx % 3 == 0 else 0.0,
                "inventory_ratio": 0.1 if idx % 3 == 0 else 0.0,
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


def test_moment_dataset_construction_and_leakage_guard(tmp_path: Path) -> None:
    paths = _write_fixture_inputs(tmp_path)
    dataset_path = tmp_path / "moment_dataset.parquet"

    dataset = build_market_making_moment_dataset(
        orderbook_events_path=paths["orderbook"],
        quote_events_paths=[paths["quotes"]],
        output_path=dataset_path,
        horizons=(1, 5),
        maker_fee_bps=2.0,
        max_inventory=1.0,
    )

    assert dataset_path.exists()
    assert len(dataset) == 10
    assert {"book_best_bid", "book_best_ask", "book_imbalance_1", "buy_markout_bps_h5", "sell_good_after_fees_h5"}.issubset(dataset.columns)
    inputs = feature_columns(dataset)
    assert "future_mid_return_h5" not in inputs
    assert_no_target_leakage(inputs)


def test_chronological_split_preserves_temporal_order(tmp_path: Path) -> None:
    paths = _write_fixture_inputs(tmp_path)
    dataset = build_market_making_moment_dataset(
        orderbook_events_path=paths["orderbook"],
        quote_events_paths=[paths["quotes"]],
        output_path=tmp_path / "moment_dataset.parquet",
        horizons=(1, 5),
    )

    splits = chronological_split(dataset, train_fraction=0.5, validation_fraction=0.2)

    assert splits["train"]["timestamp"].max() < splits["validation"]["timestamp"].min()
    assert splits["validation"]["timestamp"].max() < splits["test"]["timestamp"].min()


def test_moment_quote_filter_allows_positive_edge_and_blocks_negative() -> None:
    quote_filter = MomentQuoteFilter(
        MomentQuoteFilterConfig(maker_fee_bps=2.0, expected_spread_capture_bps=1.0, safety_buffer_bps=0.5)
    )

    positive = quote_filter.decide({"moment_buy_score": 3.0, "moment_sell_score": -1.0, "moment_uncertainty": 0.1})
    negative = quote_filter.decide({"moment_buy_score": 0.2, "moment_sell_score": 0.1, "moment_uncertainty": 0.1})

    assert positive.allow_buy is True
    assert positive.moment_decision == "allow_buy"
    assert negative.allow_buy is False
    assert negative.allow_sell is False
    assert negative.moment_reason == "non_positive_fee_adjusted_edge"


def test_moment_backend_missing_dependency_error_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    model = MomentResearchModel(MomentModelConfig(backend="moment"))

    def _raise() -> None:
        raise MomentDependencyError("missing test dependency")

    monkeypatch.setattr(model, "_load_moment_dependencies", _raise)
    with pytest.raises(MomentDependencyError, match="missing test dependency"):
        model.fit(pd.DataFrame({"buy_markout_bps_h5": [1.0], "sell_markout_bps_h5": [1.0]}), feature_columns=[])


def test_moment_backend_uses_frozen_embeddings_with_ridge_head(monkeypatch: pytest.MonkeyPatch) -> None:
    torch = pytest.importorskip("torch")

    class FakeMomentModel:
        def __call__(self, *, x_enc, input_mask):
            del input_mask
            return SimpleNamespace(embeddings=x_enc.mean(dim=2))

    model = MomentResearchModel(
        MomentModelConfig(
            backend="moment",
            lookback_length=3,
            batch_size=2,
            ridge_alpha=0.01,
        )
    )

    def _fake_load() -> None:
        model._torch = torch
        model._moment_model = FakeMomentModel()

    frame = pd.DataFrame(
        {
            "book_imbalance_1": [0.40, 0.45, 0.50, 0.55, 0.60, 0.65],
            "recent_mid_slope": [0.0, 0.01, 0.02, 0.03, 0.04, 0.05],
            "recent_volatility": [0.001] * 6,
            "book_spread_bps": [10.0] * 6,
            "buy_markout_bps_h5": [-2.0, -1.0, 0.0, 1.0, 2.0, 3.0],
            "sell_markout_bps_h5": [3.0, 2.0, 1.0, 0.0, -1.0, -2.0],
        }
    )

    monkeypatch.setattr(model, "_load_moment_dependencies", _fake_load)
    model.fit(frame, feature_columns=["book_imbalance_1", "recent_mid_slope"])
    predictions = model.predict(frame)

    assert predictions["model_backend"].eq("moment").all()
    assert predictions["moment_buy_score"].notna().all()
    assert predictions["moment_sell_score"].notna().all()
    assert model.metadata()["moment_embedding_dim"] == 2


def test_deterministic_fixture_run_writes_experiment_artifact_schema(tmp_path: Path) -> None:
    paths = _write_fixture_inputs(tmp_path / "source")
    cfg = {
        "data": {
            "orderbook_events_path": str(paths["orderbook"]),
            "quote_events_paths": [str(paths["quotes"])],
            "trades_path": str(paths["trades"]),
            "dataset_path": str(tmp_path / "cache" / "moment_dataset.parquet"),
            "reuse_dataset": False,
            "horizons": [1, 5, 10, 30],
        },
        "market_making": {"maker_fee_bps": 1.0, "max_inventory": 1.0},
        "model": {
            "backend": "deterministic_fixture",
            "checkpoint": "AutonLab/MOMENT-1-large",
            "frozen_encoder": True,
            "fine_tune": False,
            "lookback_length": 8,
            "target_horizon": "h5",
        },
        "filter": {"expected_spread_capture_bps": 1.0, "safety_buffer_bps": 0.1, "max_uncertainty": 100.0},
        "split": {"train_fraction": 0.5, "validation_fraction": 0.2},
        "output": {"root": str(tmp_path / "logs" / "experiments"), "run_name": "market_making_moment_fixture", "write_report": True},
        "runtime": {"random_seed": 7, "deterministic": True},
    }

    artifacts = run_experiment(cfg, config_path=tmp_path / "config.yaml")
    run_dir = Path(artifacts["run_dir"])
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "artifact_manifest.json").read_text(encoding="utf-8"))

    assert (run_dir / "run_metadata.json").exists()
    assert (run_dir / "config_used.yaml").exists()
    assert (run_dir / "moment_predictions.csv").exists()
    assert (run_dir / "moment_dataset.parquet").exists()
    assert (run_dir / "baseline_vs_moment.csv").exists()
    assert {"summary", "market_making_summary", "markout_summary", "risk_summary", "moment_summary"}.issubset(summary)
    assert {"returns.csv", "equity_curve.csv", "gross_returns.csv", "costs.csv", "turnover.csv", "positions.csv"}.issubset(
        {path.name for path in run_dir.glob("*.csv")}
    )
    assert "summary" in manifest["files"]
    assert not list(run_dir.rglob("*.html"))
    assert not list(run_dir.rglob("*.pptx"))
