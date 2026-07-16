from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from scripts.run_market_making_moment_experiment import (
    _baseline_vs_moment,
    _selected_gross_edge,
    run_experiment,
)
from src.market_making.experiment_artifacts import _max_drawdown
from src.market_making.moment_dataset import (
    assert_no_target_leakage,
    build_market_making_moment_dataset,
    chronological_split,
    feature_columns,
)
from src.market_making.moment_model import (
    MomentDependencyError,
    MomentModelConfig,
    MomentResearchModel,
    _feature_matrix,
    _window_batch,
)
from src.market_making.moment_quote_filter import MomentQuoteFilter, MomentQuoteFilterConfig
from tests.optional_dependencies import optional_dependency_stack_available


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


def test_moment_dataset_accepts_mixed_iso8601_timestamps(tmp_path: Path) -> None:
    paths = _write_fixture_inputs(tmp_path)
    orderbook = pd.read_csv(paths["orderbook"])
    quotes = pd.read_csv(paths["quotes"])
    orderbook.loc[0, "timestamp"] = "2026-07-03T15:28:28.123456+00:00"
    orderbook.loc[1, "timestamp"] = "2026-07-03T15:28:29+00:00"
    quotes.loc[0, "timestamp"] = "2026-07-03T15:28:28.500000+00:00"
    quotes.loc[1, "timestamp"] = "2026-07-03T15:28:29+00:00"
    orderbook.to_csv(paths["orderbook"], index=False)
    quotes.to_csv(paths["quotes"], index=False)

    dataset = build_market_making_moment_dataset(
        orderbook_events_path=paths["orderbook"],
        quote_events_paths=[paths["quotes"]],
        output_path=tmp_path / "mixed_timestamp_dataset.parquet",
        horizons=(1, 5),
        maker_fee_bps=2.0,
        max_inventory=1.0,
    )

    assert str(dataset["timestamp"].dtype) == "datetime64[ns, UTC]"
    assert dataset["timestamp"].is_monotonic_increasing


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


def test_multi_symbol_dataset_never_uses_another_symbols_book_or_future(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orderbook_path = tmp_path / "orderbook.csv"
    quotes_path = tmp_path / "quotes.csv"
    output_path = tmp_path / "dataset.parquet"
    orderbook = pd.DataFrame(
        [
            {"timestamp": "2026-07-01T00:00:00Z", "symbol": "A", "best_bid": 99.0, "best_ask": 101.0, "mid_price": 100.0},
            {"timestamp": "2026-07-01T00:00:01Z", "symbol": "B", "best_bid": 999.0, "best_ask": 1001.0, "mid_price": 1000.0},
            {"timestamp": "2026-07-01T00:00:02Z", "symbol": "A", "best_bid": 100.0, "best_ask": 102.0, "mid_price": 101.0},
            {"timestamp": "2026-07-01T00:00:03Z", "symbol": "B", "best_bid": 1009.0, "best_ask": 1011.0, "mid_price": 1010.0},
        ]
    )
    quotes = pd.DataFrame(
        [
            {"timestamp": row["timestamp"], "symbol": row["symbol"], "bid_price": row["best_bid"], "ask_price": row["best_ask"], "bid_size": 1.0, "ask_size": 1.0, "placed": True}
            for row in orderbook.to_dict(orient="records")
        ]
    )
    orderbook.to_csv(orderbook_path, index=False)
    quotes.to_csv(quotes_path, index=False)
    monkeypatch.setattr(
        pd.DataFrame,
        "to_parquet",
        lambda self, path, index=False: Path(path).write_bytes(b"test"),
    )

    dataset = build_market_making_moment_dataset(
        orderbook_events_path=orderbook_path,
        quote_events_paths=[quotes_path],
        output_path=output_path,
        horizons=(1,),
    )

    first_a = dataset.loc[dataset["symbol"].eq("A")].iloc[0]
    first_b = dataset.loc[dataset["symbol"].eq("B")].iloc[0]
    second_a = dataset.loc[dataset["symbol"].eq("A")].iloc[1]
    assert first_a["book_mid"] == 100.0
    assert first_b["book_mid"] == 1000.0
    assert first_a["future_mid_return_h1"] == pytest.approx(0.01)
    assert first_b["future_mid_return_h1"] == pytest.approx(0.01)
    assert second_a["recent_mid_return_1"] == pytest.approx(0.01)
    assert {"buy_good_h1", "sell_good_h1", "buy_good_after_fees_h1", "sell_good_after_fees_h1"}.issubset(
        dataset.columns
    )


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


def test_selected_edge_averages_allowed_sides_and_uses_configured_horizon() -> None:
    row = pd.Series(
        {
            "allow_buy": True,
            "allow_sell": True,
            "buy_markout_bps_h1": 10.0,
            "sell_markout_bps_h1": -2.0,
            "buy_markout_bps_h5": 999.0,
            "sell_markout_bps_h5": 999.0,
        }
    )

    assert _selected_gross_edge(row, horizon="h1") == pytest.approx(4.0)


def test_baseline_comparison_uses_placed_rows_without_oracle_side_selection() -> None:
    predictions = pd.DataFrame(
        {
            "placed": [True, False],
            "quoted_side_candidate": ["both", "both"],
            "buy_markout_bps_h1": [10.0, 100.0],
            "sell_markout_bps_h1": [-2.0, 100.0],
            "maker_fee_bps": [2.0, 2.0],
            "moment_realized_edge_bps": [2.0, 0.0],
            "moment_allowed": [True, False],
        }
    )

    comparison = _baseline_vs_moment(predictions, horizon="h1")
    baseline = comparison.loc[comparison["strategy"].eq("baseline")].iloc[0]

    assert baseline["allowed_event_count"] == 1
    assert baseline["net_edge_bps"] == pytest.approx(2.0)


def test_deterministic_model_predicts_with_default_features_after_empty_feature_fit() -> None:
    frame = pd.DataFrame(
        {
            "buy_markout_bps_h1": [1.0, 2.0],
            "sell_markout_bps_h1": [2.0, 1.0],
        }
    )
    model = MomentResearchModel(
        MomentModelConfig(
            backend="deterministic_fixture",
            target_horizon="h1",
        )
    ).fit(frame, feature_columns=[])

    predictions = model.predict(frame)

    assert predictions["moment_buy_score"].notna().all()
    assert predictions["moment_sell_score"].notna().all()


def test_moment_feature_fill_and_windows_do_not_cross_symbols() -> None:
    frame = pd.DataFrame(
        {
            "symbol": ["A", "B", "A", "B"],
            "signal": [1.0, 100.0, np.nan, np.nan],
        }
    )
    matrix = _feature_matrix(frame, ["signal"])
    windows, masks = _window_batch(
        np.asarray([[1.0], [100.0], [2.0], [200.0]], dtype="float32"),
        start=0,
        stop=4,
        lookback=2,
        group_ids=np.asarray(["A", "B", "A", "B"]),
    )

    assert matrix[:, 0].tolist() == [1.0, 100.0, 1.0, 100.0]
    assert windows[2, 0].tolist() == [1.0, 2.0]
    assert windows[3, 0].tolist() == [100.0, 200.0]
    assert masks[2].tolist() == [1.0, 1.0]


def test_experiment_max_drawdown_uses_zero_anchor_and_positive_magnitude() -> None:
    assert _max_drawdown(pd.Series([-2.0, -1.0, 1.0])) == pytest.approx(2.0)


def test_moment_backend_missing_dependency_error_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    model = MomentResearchModel(MomentModelConfig(backend="moment"))

    def _raise() -> None:
        raise MomentDependencyError("missing test dependency")

    monkeypatch.setattr(model, "_load_moment_dependencies", _raise)
    with pytest.raises(MomentDependencyError, match="missing test dependency"):
        model.fit(pd.DataFrame({"buy_markout_bps_h5": [1.0], "sell_markout_bps_h5": [1.0]}), feature_columns=[])


def test_moment_backend_uses_frozen_embeddings_with_ridge_head(monkeypatch: pytest.MonkeyPatch) -> None:
    if not optional_dependency_stack_available("torch"):
        pytest.skip("torch is unavailable or unstable in this environment.")
    import torch

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


def test_deterministic_fixture_run_writes_experiment_artifact_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pd.DataFrame,
        "to_parquet",
        lambda self, path, index=False: Path(path).write_bytes(b"test"),
    )
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
    predictions = pd.read_csv(run_dir / "moment_predictions.csv")
    generated_trades = pd.read_csv(run_dir / "trades.csv")
    source_trades = pd.read_csv(run_dir / "source_trades.csv")

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
    assert len(predictions) == summary["moment_summary"]["split"]["test"]["rows"]
    assert len(predictions) == summary["timeline_summary"]["rows"]
    assert len(predictions) < 10
    assert summary["market_making_summary"]["fill_observations_available"] is False
    assert "buy_markout_bps_h5" in generated_trades.columns
    assert "order_id" not in generated_trades.columns
    assert "order_id" in source_trades.columns
    assert not list(run_dir.rglob("*.html"))
    assert not list(run_dir.rglob("*.pptx"))
