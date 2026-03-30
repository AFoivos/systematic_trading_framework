from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

import src.experiments.runner as runner_mod
import src.src_data.storage as storage_mod
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
    assert metadata["verified_fingerprint"] is True


def test_load_dataset_snapshot_accepts_single_asset_raw_csv_with_epoch_ms(tmp_path) -> None:
    """
    Explicit load_path CSVs should support canonical single-asset OHLCV with epoch-millisecond
    timestamps instead of requiring framework snapshot format.
    """
    data_path = tmp_path / "raw_ohlcv.csv"
    pd.DataFrame(
        {
            "timestamp": [1_420_149_600_000, 1_420_153_200_000, 1_420_156_800_000],
            "open": [1.20, 1.21, 1.22],
            "high": [1.25, 1.26, 1.27],
            "low": [1.19, 1.20, 1.21],
            "close": [1.23, 1.24, 1.25],
            "volume": [100.0, 120.0, 140.0],
        }
    ).to_csv(data_path, index=False)

    loaded_frames, metadata = load_dataset_snapshot(
        stage="raw",
        load_path=data_path,
        requested_assets=["EURUSD"],
    )

    assert sorted(loaded_frames) == ["EURUSD"]
    df = loaded_frames["EURUSD"]
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index[0] == pd.Timestamp("2015-01-01 22:00:00")
    assert metadata["format"] == "external_single_asset_ohlcv_csv"
    assert metadata["requires_pit_hardening"] is True


def test_load_dataset_snapshot_applies_start_end_window_to_external_csv(tmp_path) -> None:
    """
    Explicit load_path CSVs should honor data.start/data.end like live providers do, using the
    same UTC-naive timestamp convention after epoch-millisecond normalization.
    """
    data_path = tmp_path / "dukas_like_ohlcv.csv"
    pd.DataFrame(
        {
            "timestamp": [
                1_420_149_600_000,
                1_420_153_200_000,
                1_420_156_800_000,
                1_420_160_400_000,
            ],
            "open": [119.746, 119.824, 119.885, 120.072],
            "high": [119.841, 119.967, 120.074, 120.426],
            "low": [119.701, 119.804, 119.835, 120.052],
            "close": [119.824, 119.885, 120.074, 120.274],
            "volume": [702.65, 3082.5, 2144.8899, 3877.04],
        }
    ).to_csv(data_path, index=False)

    loaded_frames, metadata = load_dataset_snapshot(
        stage="raw",
        load_path=data_path,
        requested_assets=["USDJPY"],
        start="2015-01-02 00:00:00",
        end="2015-01-02 01:00:00",
    )

    df = loaded_frames["USDJPY"]
    assert len(df) == 1
    assert df.index[0] == pd.Timestamp("2015-01-02 00:00:00")
    assert float(df.iloc[0]["volume"]) == pytest.approx(2144.8899)
    assert metadata["requested_start"] == "2015-01-02 00:00:00"
    assert metadata["requested_end"] == "2015-01-02 01:00:00"


def test_dataset_snapshot_rejects_path_traversal_in_dataset_id(tmp_path) -> None:
    """
    Dataset snapshot helpers should reject dataset ids that escape the configured root.
    """
    asset_frames = {"AAA": _synthetic_ohlcv(periods=10, seed=1)}

    with pytest.raises(ValueError):
        save_dataset_snapshot(
            asset_frames,
            dataset_id="../../escape",
            stage="raw",
            root_dir=tmp_path,
            context={},
        )


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


def test_load_dataset_snapshot_rejects_fingerprint_mismatch(tmp_path) -> None:
    """
    Cached snapshots should fail loudly when on-disk data no longer matches stored metadata.
    """
    asset_frames = {"AAA": _synthetic_ohlcv(periods=20, seed=1)}
    saved = save_dataset_snapshot(
        asset_frames,
        dataset_id="demo_dataset",
        stage="raw",
        root_dir=tmp_path,
        context={"source": "synthetic"},
    )

    data_path = Path(saved["data_path"])
    data_path.write_text(
        "timestamp,asset,open,high,low,close,volume\n2020-01-01,AAA,999,999,999,999,999\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_dataset_snapshot(
            stage="raw",
            root_dir=tmp_path,
            dataset_id="demo_dataset",
        )


def test_load_dataset_snapshot_filters_cached_snapshot_by_assets_and_window(tmp_path) -> None:
    asset_frames = {
        "AAA": _synthetic_ohlcv(periods=8, seed=1),
        "BBB": _synthetic_ohlcv(periods=8, seed=2),
    }
    save_dataset_snapshot(
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
        requested_assets=["BBB"],
        start="2020-01-03",
        end="2020-01-06",
    )

    assert sorted(loaded_frames) == ["BBB"]
    df = loaded_frames["BBB"]
    assert df.index.min() == pd.Timestamp("2020-01-03")
    assert df.index.max() == pd.Timestamp("2020-01-05")
    assert metadata["verified_fingerprint"] is True


def test_save_dataset_snapshot_works_without_fcntl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    asset_frames = {"AAA": _synthetic_ohlcv(periods=5, seed=1)}
    monkeypatch.setattr(storage_mod, "fcntl", None)

    saved = save_dataset_snapshot(
        asset_frames,
        dataset_id="demo_dataset_no_fcntl",
        stage="raw",
        root_dir=tmp_path,
        context={"source": "synthetic"},
    )

    assert Path(saved["data_path"]).exists()


def test_load_asset_frames_accepts_raw_csv_load_path_and_applies_pit(tmp_path) -> None:
    """
    Raw CSV load_path inputs should be normalized, PIT-hardened, and validated through the same
    data-stage path used by experiments.
    """
    data_path = tmp_path / "intraday_raw.csv"
    pd.DataFrame(
        {
            "timestamp": [
                1_420_153_200_000,
                1_420_149_600_000,
                1_420_149_600_000,
            ],
            "open": [1.21, 1.20, 1.205],
            "high": [1.26, 1.25, 1.255],
            "low": [1.20, 1.19, 1.195],
            "close": [1.24, 1.23, 1.235],
            "volume": [120.0, 100.0, 110.0],
        }
    ).to_csv(data_path, index=False)

    frames, storage_meta = runner_mod._load_asset_frames(
        {
            "symbol": "USDJPY",
            "source": "yahoo",
            "interval": "1h",
            "storage": {
                "mode": "cached_only",
                "load_path": str(data_path),
            },
            "pit": {
                "timestamp_alignment": {
                    "source_timezone": "UTC",
                    "output_timezone": "UTC",
                    "normalize_daily": False,
                    "duplicate_policy": "last",
                }
            },
        }
    )

    df = frames["USDJPY"]
    assert len(df) == 2
    assert df.index.is_monotonic_increasing
    assert not df.index.has_duplicates
    assert float(df.iloc[0]["close"]) == 1.235
    assert storage_meta["loaded_from_cache"] is True
    assert "USDJPY" in storage_meta["pit_meta_by_asset"]


def test_load_asset_frames_applies_data_window_to_external_csv_load_path(tmp_path) -> None:
    """
    The data-stage path should pass start/end through to explicit CSV load_path inputs so YAML
    windows behave consistently across local files and live providers.
    """
    data_path = tmp_path / "usdjpy_h1_dukas_like.csv"
    pd.DataFrame(
        {
            "timestamp": [
                1_420_149_600_000,
                1_420_153_200_000,
                1_420_156_800_000,
                1_420_160_400_000,
            ],
            "open": [119.746, 119.824, 119.885, 120.072],
            "high": [119.841, 119.967, 120.074, 120.426],
            "low": [119.701, 119.804, 119.835, 120.052],
            "close": [119.824, 119.885, 120.074, 120.274],
            "volume": [702.65, 3082.5, 2144.8899, 3877.04],
        }
    ).to_csv(data_path, index=False)

    frames, storage_meta = runner_mod._load_asset_frames(
        {
            "symbol": "USDJPY",
            "source": "yahoo",
            "interval": "1h",
            "start": "2015-01-02 00:00:00",
            "end": "2015-01-02 01:00:00",
            "storage": {
                "mode": "cached_only",
                "load_path": str(data_path),
            },
            "pit": {
                "timestamp_alignment": {
                    "source_timezone": "UTC",
                    "output_timezone": "UTC",
                    "normalize_daily": False,
                    "duplicate_policy": "last",
                }
            },
        }
    )

    df = frames["USDJPY"]
    assert len(df) == 1
    assert df.index[0] == pd.Timestamp("2015-01-02 00:00:00")
    assert float(df.iloc[0]["close"]) == pytest.approx(120.074)
    assert storage_meta["loaded_snapshot"]["requested_start"] == "2015-01-02 00:00:00"
    assert storage_meta["loaded_snapshot"]["requested_end"] == "2015-01-02 01:00:00"


def test_dataset_snapshot_parallel_writes_remain_loadable(tmp_path) -> None:
    """
    Concurrent writers targeting the same snapshot should not leave corrupted temp files behind.
    """
    script = """
from pathlib import Path
import sys
import numpy as np
import pandas as pd

from src.src_data.storage import save_dataset_snapshot

root = Path(sys.argv[1])
seed = int(sys.argv[2])
rng = np.random.default_rng(seed)
idx = pd.date_range("2020-01-01", periods=4000, freq="D")
close = 100.0 + np.cumsum(rng.normal(0.0, 1.0, size=len(idx)))
frame = pd.DataFrame(index=idx)
frame["open"] = close
frame["high"] = close + 1.0
frame["low"] = close - 1.0
frame["close"] = close
frame["volume"] = 1000.0
save_dataset_snapshot(
    {"AAA": frame},
    dataset_id="shared_dataset",
    stage="raw",
    root_dir=root,
    context={"seed": seed},
    overwrite=True,
)
"""
    proc_a = subprocess.Popen([sys.executable, "-c", script, str(tmp_path), "1"])
    proc_b = subprocess.Popen([sys.executable, "-c", script, str(tmp_path), "2"])

    assert proc_a.wait() == 0
    assert proc_b.wait() == 0

    loaded_frames, metadata = load_dataset_snapshot(
        stage="raw",
        root_dir=tmp_path,
        dataset_id="shared_dataset",
    )

    assert "AAA" in loaded_frames
    assert metadata["verified_fingerprint"] is True
    assert not list((tmp_path / "raw" / "shared_dataset").glob("*.tmp"))


def test_dataset_snapshot_requires_explicit_overwrite(tmp_path) -> None:
    """
    Reusing a dataset id should fail unless overwrite intent is explicit.
    """
    asset_frames = {"AAA": _synthetic_ohlcv(periods=20, seed=1)}
    save_dataset_snapshot(
        asset_frames,
        dataset_id="demo_dataset",
        stage="raw",
        root_dir=tmp_path,
        context={"source": "synthetic"},
    )

    with pytest.raises(FileExistsError, match="overwrite=True"):
        save_dataset_snapshot(
            asset_frames,
            dataset_id="demo_dataset",
            stage="raw",
            root_dir=tmp_path,
            context={"source": "synthetic"},
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
            "params": {"prob_col": "pred_prob", "signal_col": "signal_prob_size", "clip": 1.0},
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


def test_run_experiment_portfolio_test_subset_zeroes_pre_oos_weights(tmp_path, monkeypatch) -> None:
    symbols = ["AAA", "BBB"]
    synthetic_panel = {
        "AAA": _synthetic_ohlcv(periods=180, seed=11, amplitude=0.012),
        "BBB": _synthetic_ohlcv(periods=180, seed=19, amplitude=0.009),
    }

    def _mock_load_panel(**kwargs):
        requested = kwargs["symbols"]
        return {symbol: synthetic_panel[symbol].copy() for symbol in requested}

    monkeypatch.setattr(runner_mod, "load_ohlcv_panel", _mock_load_panel)

    config_path = tmp_path / "multi_asset_portfolio_test_subset.yaml"
    config = {
        "data": {
            "symbols": symbols,
            "source": "yahoo",
            "interval": "1d",
            "start": "2020-01-01",
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
            "params": {"prob_col": "pred_prob", "signal_col": "signal_prob_size", "clip": 1.0},
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
            "subset": "test",
        },
        "logging": {"enabled": False},
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = runner_mod.run_experiment(config_path)

    assert result.portfolio_weights is not None
    first_oos_by_asset = [
        frame.index[frame["pred_is_oos"].astype(bool)][0]
        for frame in result.data.values()
    ]
    expected_first_oos = max(first_oos_by_asset)
    assert result.portfolio_weights.index.min() == expected_first_oos


def test_run_experiment_rejects_multi_asset_without_explicit_portfolio_mode(tmp_path, monkeypatch) -> None:
    """
    Multi-asset runs should fail loudly when portfolio mode is explicitly disabled.
    """
    symbols = ["AAA", "BBB"]
    synthetic_panel = {
        "AAA": _synthetic_ohlcv(periods=120, seed=11, amplitude=0.012),
        "BBB": _synthetic_ohlcv(periods=120, seed=19, amplitude=0.009),
    }

    def _mock_load_panel(**kwargs):
        requested = kwargs["symbols"]
        return {symbol: synthetic_panel[symbol].copy() for symbol in requested}

    monkeypatch.setattr(runner_mod, "load_ohlcv_panel", _mock_load_panel)

    config_path = tmp_path / "multi_asset_disabled.yaml"
    config = {
        "data": {
            "symbols": symbols,
            "source": "yahoo",
            "interval": "1d",
            "start": "2020-01-01",
        },
        "features": [
            {"step": "returns", "params": {"log": False, "col_name": "close_ret"}},
            {"step": "lags", "params": {"cols": ["close_ret"], "lags": [1, 2]}},
        ],
        "model": {
            "kind": "logistic_regression_clf",
            "params": {"max_iter": 200},
            "feature_cols": ["lag_close_ret_1", "lag_close_ret_2"],
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
            "split": {
                "method": "walk_forward",
                "train_size": 80,
                "test_size": 20,
                "step_size": 20,
                "expanding": True,
            },
        },
        "signals": {
            "kind": "probability_conviction",
            "params": {"prob_col": "pred_prob", "signal_col": "signal_prob_size", "clip": 1.0},
        },
        "portfolio": {"enabled": False},
        "backtest": {
            "returns_col": "close_ret",
            "signal_col": "signal_prob_size",
            "periods_per_year": 252,
            "returns_type": "simple",
        },
        "logging": {"enabled": False},
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="portfolio.enabled=false"):
        runner_mod.run_experiment(config_path)
