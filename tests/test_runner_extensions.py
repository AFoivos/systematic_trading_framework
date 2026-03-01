from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import src.experiments.runner as runner_mod
from src.execution.paper import build_rebalance_orders
from src.experiments.models import train_logistic_regression_classifier
from src.portfolio.construction import PortfolioPerformance
from src.src_data.storage import load_dataset_snapshot, save_dataset_snapshot


def _synthetic_ohlcv(
    *,
    periods: int = 180,
    seed: int = 0,
    amplitude: float = 0.01,
) -> pd.DataFrame:
    """
    Verify that synthetic OHLCV behaves as expected under a representative regression scenario.
    The test protects the intended contract of the surrounding component and makes failures
    easier to localize.
    """
    rng = np.random.default_rng(seed)
    base = np.where(np.arange(periods) % 2 == 0, amplitude, -amplitude)
    returns = base + rng.normal(0.0, amplitude / 5.0, size=periods)
    close = 100.0 * np.exp(np.cumsum(returns))

    idx = pd.date_range("2020-01-01", periods=periods, freq="D")
    df = pd.DataFrame(index=idx)
    df["close"] = close
    df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0] * 0.999)
    df["high"] = np.maximum(df["open"], df["close"]) * 1.002
    df["low"] = np.minimum(df["open"], df["close"]) * 0.998
    df["volume"] = 1_000_000 + rng.integers(0, 10_000, size=periods)
    return df[["open", "high", "low", "close", "volume"]]


def test_dataset_snapshot_roundtrip(tmp_path) -> None:
    """
    Verify that dataset snapshot roundtrip behaves as expected under a representative regression
    scenario. The test protects the intended contract of the surrounding component and makes
    failures easier to localize.
    """
    asset_frames = {
        "AAA": _synthetic_ohlcv(periods=20, seed=1),
        "BBB": _synthetic_ohlcv(periods=20, seed=2),
    }

    saved = save_dataset_snapshot(
        asset_frames,
        dataset_id="demo_dataset",
        stage="raw",
        root_dir=tmp_path,
        context={"source": "synthetic"},
    )
    loaded_frames, metadata = load_dataset_snapshot(
        stage="raw",
        root_dir=tmp_path,
        dataset_id="demo_dataset",
    )

    assert Path(saved["data_path"]).exists()
    assert metadata["dataset_id"] == "demo_dataset"
    assert metadata["context"]["source"] == "synthetic"
    assert sorted(loaded_frames) == ["AAA", "BBB"]
    assert loaded_frames["AAA"].index.equals(asset_frames["AAA"].index)
    assert list(loaded_frames["AAA"].columns) == list(asset_frames["AAA"].columns)


def test_load_asset_frames_rejects_cached_snapshot_with_mismatched_pit_context(tmp_path) -> None:
    """
    Verify that load asset frames rejects cached snapshot with mismatched PIT context behaves as
    expected under a representative regression scenario. The test protects the intended
    contract of the surrounding component and makes failures easier to localize.
    """
    save_dataset_snapshot(
        {"AAA": _synthetic_ohlcv(periods=20, seed=1)},
        dataset_id="demo_dataset",
        stage="raw",
        root_dir=tmp_path,
        context={"source": "synthetic"},
    )

    with pytest.raises(ValueError):
        runner_mod._load_asset_frames(
            {
                "symbol": "AAA",
                "source": "yahoo",
                "interval": "1d",
                "start": "2020-01-01",
                "storage": {
                    "mode": "cached_only",
                    "dataset_id": "demo_dataset",
                    "raw_dir": str(tmp_path),
                },
                "pit": {
                    "corporate_actions": {
                        "policy": "adj_close_replace_close",
                    }
                },
            }
        )


def test_build_rebalance_orders_reports_share_deltas() -> None:
    """
    Verify that rebalance orders reports share deltas behaves as expected under a representative
    regression scenario. The test protects the intended contract of the surrounding component
    and makes failures easier to localize.
    """
    orders = build_rebalance_orders(
        pd.Series({"AAA": 0.6, "BBB": -0.2}, dtype=float),
        prices=pd.Series({"AAA": 50.0, "BBB": 25.0}, dtype=float),
        capital=100_000.0,
        current_weights=pd.Series({"AAA": 0.1, "BBB": 0.0}, dtype=float),
    )

    assert "delta_notional" in orders.columns
    assert "delta_shares" in orders.columns
    assert orders.loc["AAA", "delta_notional"] > 0
    assert orders.loc["BBB", "delta_shares"] < 0


def test_build_rebalance_orders_ignores_flat_assets_with_missing_prices() -> None:
    """
    Verify that rebalance orders ignores flat assets with missing prices behaves as expected
    under a representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    orders = build_rebalance_orders(
        pd.Series({"AAA": 0.6, "BBB": 0.0}, dtype=float),
        prices=pd.Series({"AAA": 50.0, "BBB": np.nan}, dtype=float),
        capital=100_000.0,
        current_weights=pd.Series({"AAA": 0.1, "BBB": 0.0}, dtype=float),
    )

    assert list(orders.index) == ["AAA"]
    assert "BBB" not in orders.index


def test_build_rebalance_orders_emits_liquidation_for_current_only_asset() -> None:
    """
    Verify that rebalance orders emits liquidation for current only asset behaves as expected
    under a representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    orders = build_rebalance_orders(
        pd.Series({"AAA": 0.5}, dtype=float),
        prices=pd.Series({"AAA": 100.0, "BBB": 50.0}, dtype=float),
        capital=100_000.0,
        current_weights=pd.Series({"AAA": 0.0, "BBB": 0.2}, dtype=float),
    )

    assert {"AAA", "BBB"} == set(orders.index)
    assert np.isclose(orders.loc["BBB", "target_weight"], 0.0)
    assert orders.loc["BBB", "delta_notional"] < 0
    assert orders.loc["BBB", "delta_shares"] < 0


def test_logistic_regression_model_registry_outputs_oos_metrics() -> None:
    """
    Verify that logistic regression model registry outputs out-of-sample metrics behaves as
    expected under a representative regression scenario. The test protects the intended contract
    of the surrounding component and makes failures easier to localize.
    """
    df = _synthetic_ohlcv(periods=220, seed=7)
    df["close_ret"] = df["close"].pct_change()
    df["lag_close_ret_1"] = df["close_ret"].shift(1)
    df["lag_close_ret_2"] = df["close_ret"].shift(2)

    out, _, meta = train_logistic_regression_classifier(
        df,
        {
            "params": {"max_iter": 300},
            "feature_cols": ["lag_close_ret_1", "lag_close_ret_2"],
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
            "runtime": {"seed": 7, "deterministic": True, "threads": 1, "repro_mode": "strict"},
            "split": {
                "method": "walk_forward",
                "train_size": 120,
                "test_size": 20,
                "step_size": 20,
                "expanding": True,
            },
        },
    )

    assert meta["model_kind"] == "logistic_regression_clf"
    assert int(out["pred_is_oos"].sum()) > 0
    assert meta["oos_classification_summary"]["evaluation_rows"] > 0
    assert meta["folds"][0]["classification_metrics"]["evaluation_rows"] >= 0


def test_run_experiment_supports_multi_asset_portfolio_storage_monitoring_and_execution(
    tmp_path,
    monkeypatch,
) -> None:
    """
    Verify that experiment supports multi asset portfolio storage monitoring and execution
    behaves as expected under a representative regression scenario. The test protects the
    intended contract of the surrounding component and makes failures easier to localize.
    """
    symbols = ["AAA", "BBB"]
    synthetic_panel = {
        "AAA": _synthetic_ohlcv(periods=180, seed=11, amplitude=0.012),
        "BBB": _synthetic_ohlcv(periods=180, seed=19, amplitude=0.009),
    }

    def _mock_load_panel(**kwargs):
        requested = kwargs["symbols"]
        return {symbol: synthetic_panel[symbol].copy() for symbol in requested}

    monkeypatch.setattr(runner_mod, "load_ohlcv_panel", _mock_load_panel)

    config_path = tmp_path / "multi_asset_portfolio.yaml"
    config = {
        "data": {
            "symbols": symbols,
            "source": "yahoo",
            "interval": "1d",
            "start": "2020-01-01",
            "storage": {
                "mode": "live",
                "dataset_id": "multi_asset_demo",
                "save_raw": True,
                "save_processed": True,
                "raw_dir": str(tmp_path / "raw_store"),
                "processed_dir": str(tmp_path / "processed_store"),
            },
        },
        "features": [
            {"step": "returns", "params": {"log": False, "col_name": "close_ret"}},
            {"step": "lags", "params": {"cols": ["close_ret"], "lags": [1, 2]}},
        ],
        "model": {
            "kind": "logistic_regression_clf",
            "params": {"max_iter": 400},
            "feature_cols": ["lag_close_ret_1", "lag_close_ret_2"],
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
            "split": {
                "method": "walk_forward",
                "train_size": 100,
                "test_size": 20,
                "step_size": 20,
                "expanding": True,
            },
        },
        "signals": {
            "kind": "probability_conviction",
            "params": {"prob_col": "pred_prob", "signal_name": "signal_prob_size", "clip": 1.0},
        },
        "portfolio": {
            "enabled": True,
            "construction": "signal_weights",
            "gross_target": 1.0,
            "long_short": True,
            "constraints": {
                "min_weight": -0.75,
                "max_weight": 0.75,
                "max_gross_leverage": 1.0,
                "target_net_exposure": 0.0,
            },
        },
        "backtest": {
            "returns_col": "close_ret",
            "signal_col": "signal_prob_size",
            "periods_per_year": 252,
            "returns_type": "simple",
        },
        "monitoring": {"enabled": True, "psi_threshold": 0.1, "n_bins": 8},
        "execution": {
            "enabled": True,
            "capital": 100_000.0,
            "price_col": "close",
        },
        "logging": {"enabled": False},
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = runner_mod.run_experiment(config_path)

    assert isinstance(result.backtest, PortfolioPerformance)
    assert result.portfolio_weights is not None
    assert result.evaluation["scope"] == "strict_oos_only"
    assert result.monitoring["asset_count"] == 2
    assert result.execution["order_count"] > 0
    assert "per_asset" in result.model_meta
    assert all("classification_metrics" in fold for fold in result.model_meta["per_asset"]["AAA"]["folds"])
    assert (tmp_path / "raw_store" / "raw" / "multi_asset_demo" / "dataset.csv").exists()
    assert len(list((tmp_path / "processed_store" / "processed").glob("*/dataset.csv"))) == 1
