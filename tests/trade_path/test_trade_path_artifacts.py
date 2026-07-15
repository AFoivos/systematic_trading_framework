from __future__ import annotations

import json

import pandas as pd

from src.backtesting.engine import BacktestResult
import src.experiments.orchestration.pipeline as pipeline_mod
from src.experiments.orchestration.artifacts import save_artifacts


def test_trade_path_diagnostics_artifacts_and_report_are_written(tmp_path) -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    data = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 101.0],
            "high": [101.0, 103.0, 104.0, 102.0],
            "low": [99.0, 100.0, 100.0, 99.0],
            "close": [100.0, 102.0, 101.0, 100.0],
            "signal": [1.0, 0.0, 0.0, 0.0],
            "pred_prob": [0.7, 0.7, 0.7, 0.7],
            "pred_is_oos": [True, True, True, True],
        },
        index=idx,
    )
    returns = pd.Series([0.0, 0.01, -0.005, 0.0], index=idx, name="returns")
    performance = BacktestResult(
        equity_curve=(1.0 + returns).cumprod(),
        returns=returns,
        gross_returns=returns.copy().rename("gross_returns"),
        costs=pd.Series(0.0, index=idx, name="costs"),
        positions=pd.Series([0.0, 1.0, 1.0, 0.0], index=idx, name="positions"),
        turnover=pd.Series([0.0, 1.0, 0.0, 1.0], index=idx, name="turnover"),
        summary={"cumulative_return": float((1.0 + returns).prod() - 1.0)},
        trades=pd.DataFrame(
            {
                "asset": ["AAA"],
                "side": ["long"],
                "signal_timestamp": [idx[0]],
                "entry_timestamp": [idx[0]],
                "exit_timestamp": [idx[-1]],
                "entry_price": [100.0],
                "exit_price": [100.0],
                "stop_loss_price": [98.0],
                "trade_r": [-0.1],
                "max_favorable_r": [2.0],
                "max_adverse_r": [-0.5],
                "bars_held": [4],
                "exit_reason": ["stop_loss"],
            }
        ),
    )
    cfg = {
        "config_path": "synthetic.yaml",
        "data": {"symbol": "AAA", "source": "synthetic", "interval": "1d"},
        "model": {"kind": "none"},
        "backtest": {"signal_col": "signal", "returns_type": "simple"},
        "diagnostics": {
            "enabled": True,
            "trade_path": {
                "enabled": True,
                "plots": {"enabled": False, "max_trades": 10, "max_path_points": 1000},
            },
        },
        "logging": {"run_name": "synthetic_trade_path"},
        "runtime": {"seed": 42},
    }
    run_dir = tmp_path / "run"

    artifacts = save_artifacts(
        run_dir=run_dir,
        cfg=cfg,
        data=data,
        performance=performance,
        model_meta={"pred_prob_col": "pred_prob", "pred_is_oos_col": "pred_is_oos"},
        evaluation={
            "scope": "timeline",
            "primary_summary": dict(performance.summary),
            "timeline_summary": dict(performance.summary),
            "trade_diagnostics": {"trade_count": 1},
        },
        monitoring={},
        execution={},
        execution_orders=None,
        portfolio_weights=None,
        portfolio_diagnostics=None,
        portfolio_meta={},
        storage_meta={},
        run_metadata={"runtime": {"seed": 42}, "model_meta": {}},
        config_hash_sha256="cfg",
        data_fingerprint={"sha256": "data"},
        stage_tails=None,
    )

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    trade_path_summary = json.loads((run_dir / "report_assets" / "trade_path_summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    report = (run_dir / "report.md").read_text(encoding="utf-8")

    assert "trade_path" in summary["evaluation"]["trade_diagnostics"]
    assert "could_have_been_profitable" in trade_path_summary
    assert "path_construction" in trade_path_summary
    assert "trade_path_summary" in manifest["files"]
    assert "trade_events" in manifest["files"]
    assert "## Trade Path Diagnostics" in report
    assert (run_dir / "report_assets" / "trades_enriched.csv").exists()
    assert (
        (run_dir / "report_assets" / "trade_paths.parquet").exists()
        or (run_dir / "report_assets" / "trade_paths.csv").exists()
    )
    assert (run_dir / "report_assets" / "probability_trade_quality.csv").exists()
    assert (run_dir / "report_assets" / "counterfactual_exit_summary.csv").exists()
    assert not list((run_dir / "report_assets").glob("trade_diagnostics_*.html"))
    assert "trades_enriched" in artifacts
    events = pd.read_csv(run_dir / "trade_events.csv")
    assert len(events) == 1
    assert {"asset", "signal_time", "entry_time", "exit_time", "exit_reason"}.issubset(events.columns)


def test_target_only_trade_path_diagnostics_without_executed_trades(tmp_path) -> None:
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    data = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.0, 102.0, 103.0],
            "target_candidate": [1, 0, 1],
            "target_trade_r": [0.8, 0.0, -0.4],
            "target_mfe_r": [1.2, 0.0, 0.6],
            "target_mae_r": [-0.2, 0.0, -0.8],
            "target_bars_held": [3, 0, 2],
            "target_exit_reason": ["take_profit", "", "stop_loss"],
        },
        index=idx,
    )
    returns = pd.Series([0.0, 0.0, 0.0], index=idx, name="returns")
    performance = BacktestResult(
        equity_curve=(1.0 + returns).cumprod(),
        returns=returns,
        gross_returns=returns.copy().rename("gross_returns"),
        costs=pd.Series(0.0, index=idx, name="costs"),
        positions=pd.Series(0.0, index=idx, name="positions"),
        turnover=pd.Series(0.0, index=idx, name="turnover"),
        summary={"cumulative_return": 0.0},
        trades=pd.DataFrame(),
    )
    cfg = {
        "config_path": "synthetic_target_only.yaml",
        "data": {"symbol": "AAA", "source": "synthetic", "interval": "1d"},
        "model": {"kind": "none"},
        "backtest": {"signal_col": "signal", "returns_type": "simple"},
        "diagnostics": {"enabled": True, "trade_path": {"enabled": True}},
        "logging": {"run_name": "synthetic_target_only"},
        "runtime": {"seed": 42},
    }
    run_dir = tmp_path / "target_only_run"

    save_artifacts(
        run_dir=run_dir,
        cfg=cfg,
        data=data,
        performance=performance,
        model_meta={},
        evaluation={
            "scope": "timeline",
            "primary_summary": dict(performance.summary),
            "timeline_summary": dict(performance.summary),
            "trade_diagnostics": {"trade_count": 0},
        },
        monitoring={},
        execution={},
        execution_orders=None,
        portfolio_weights=None,
        portfolio_diagnostics=None,
        portfolio_meta={},
        storage_meta={},
        run_metadata={"runtime": {"seed": 42}, "model_meta": {}},
        config_hash_sha256="cfg",
        data_fingerprint={"sha256": "data"},
        stage_tails=None,
    )

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    trade_path_summary = json.loads((run_dir / "report_assets" / "trade_path_summary.json").read_text(encoding="utf-8"))

    assert "target_candidates" in summary["evaluation"]["trade_diagnostics"]["trade_path"]
    assert "target_candidates" in trade_path_summary
    assert "path_construction" in trade_path_summary
    assert (run_dir / "report_assets" / "target_trades_enriched.csv").exists()
    assert not (run_dir / "report_assets" / "trades_enriched.csv").exists()
    assert not list((run_dir / "report_assets").glob("*.html"))


def test_pipeline_result_primary_summary_includes_trade_path_diagnostics(tmp_path, monkeypatch) -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    frame = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 101.0],
            "high": [101.0, 103.0, 104.0, 102.0],
            "low": [99.0, 100.0, 100.0, 99.0],
            "close": [100.0, 102.0, 101.0, 100.0],
            "close_ret": [0.0, 0.02, -0.01, -0.01],
            "signal": [1.0, 0.0, 0.0, 0.0],
        },
        index=idx,
    )
    returns = pd.Series([0.0, 0.01, -0.005, 0.0], index=idx, name="returns")
    performance = BacktestResult(
        equity_curve=(1.0 + returns).cumprod(),
        returns=returns,
        gross_returns=returns.copy().rename("gross_returns"),
        costs=pd.Series(0.0, index=idx, name="costs"),
        positions=pd.Series([0.0, 1.0, 1.0, 0.0], index=idx, name="positions"),
        turnover=pd.Series([0.0, 1.0, 0.0, 1.0], index=idx, name="turnover"),
        summary={"cumulative_return": float((1.0 + returns).prod() - 1.0)},
        trades=pd.DataFrame(
            {
                "side": ["long"],
                "signal_timestamp": [idx[0]],
                "entry_timestamp": [idx[0]],
                "exit_timestamp": [idx[-1]],
                "entry_price": [100.0],
                "exit_price": [100.0],
                "stop_loss_price": [98.0],
                "trade_r": [-0.1],
                "max_favorable_r": [2.0],
                "max_adverse_r": [-0.5],
                "bars_held": [4],
                "exit_reason": ["stop_loss"],
            }
        ),
    )
    config_path = tmp_path / "pipeline_trade_path.yaml"
    config_path.write_text(
        json.dumps(
            {
                "data": {"symbol": "AAA", "source": "yahoo", "interval": "1d"},
                "features": [],
                "model": {"kind": "none"},
                "signals": {"kind": "none"},
                "backtest": {"returns_col": "close_ret", "signal_col": "signal", "returns_type": "simple"},
                "diagnostics": {"enabled": True},
                "monitoring": {"enabled": False},
                "execution": {"enabled": False},
                "logging": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(pipeline_mod, "apply_steps_to_assets", lambda raw, feature_steps: raw)
    monkeypatch.setattr(
        pipeline_mod,
        "apply_model_pipeline_to_assets",
        lambda frames, model_cfg, model_stages, returns_col: (
            {asset: data.assign(pred_ret=0.25) for asset, data in frames.items()},
            None,
            {},
        ),
    )
    monkeypatch.setattr(
        pipeline_mod,
        "apply_signals_to_assets",
        lambda frames, signals_cfg: {asset: data.assign(signal_entry=1.0) for asset, data in frames.items()},
    )
    monkeypatch.setattr(
        pipeline_mod,
        "apply_post_signal_target_to_assets",
        lambda frames, model_cfg, backtest_cfg: (
            {asset: data.assign(target_future_return=0.01) for asset, data in frames.items()},
            {"target": {"kind": "forward_return"}},
        ),
    )
    monkeypatch.setattr(pipeline_mod, "run_single_asset_backtest", lambda asset, data, cfg, model_meta: performance)
    monkeypatch.setattr(
        pipeline_mod,
        "build_single_asset_evaluation",
        lambda asset, data, performance, model_meta, periods_per_year, backtest_cfg: {
            "scope": "timeline",
            "primary_summary": dict(performance.summary),
            "timeline_summary": dict(performance.summary),
            "trade_diagnostics": {"trade_count": 1},
        },
    )
    monkeypatch.setattr(pipeline_mod, "build_robustness_diagnostics", lambda *args, **kwargs: {})
    monkeypatch.setattr(pipeline_mod, "compute_monitoring_report", lambda *args, **kwargs: {})
    monkeypatch.setattr(pipeline_mod, "build_execution_output", lambda *args, **kwargs: ({}, None))

    saved_processed_frames = []

    def _save_processed_snapshot(asset_frames, **kwargs):
        saved_processed_frames.append({asset: data.copy() for asset, data in asset_frames.items()})
        return {"data_path": "processed/dataset.csv"}

    result = pipeline_mod.run_experiment_pipeline(
        config_path,
        load_asset_frames_fn=lambda data_cfg: ({"AAA": frame.copy()}, {}),
        save_processed_snapshot_fn=_save_processed_snapshot,
    )

    primary = result.evaluation["primary_summary"]
    assert primary["avg_max_favorable_r"] == 2.0
    assert primary["loser_was_positive_rate"] == 1.0
    assert primary["avg_giveback_r"] == 2.1
    assert "trade_path" in result.evaluation["trade_diagnostics"]
    assert len(saved_processed_frames) == 1
    assert {"pred_ret", "signal_entry", "target_future_return"}.issubset(saved_processed_frames[0]["AAA"].columns)
