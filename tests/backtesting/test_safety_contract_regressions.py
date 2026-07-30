from __future__ import annotations

import json

import pandas as pd
import pytest

from src.backtesting.engine import BacktestResult, run_backtest
from src.evaluation.metrics import compute_backtest_metrics
from src.evaluation.model_diagnostics import resolve_forecast_volatility_column
import src.experiments.orchestration.artifacts as artifacts_mod
from src.experiments.orchestration.artifacts import (
    canonicalize_completed_trade_accounting,
    save_artifacts,
)
from src.experiments.orchestration.backtest_stage import (
    _apply_execution_delay_with_oos_boundary,
    build_robustness_diagnostics,
    gate_predictions_to_oos,
)
from src.experiments.orchestration.consistency import (
    apply_final_trade_accounting,
    assert_run_consistency,
)
from src.experiments.orchestration.reporting import (
    build_oos_volatility_rank_diagnostic,
    build_single_asset_evaluation,
    compute_subset_metrics,
    evaluation_scope_metadata,
)
from src.experiments.orchestration.pipeline import _raw_input_fingerprint_record
from src.experiments.support.baseline_diagnostics import (
    compute_baseline_vwap_rms_ema_ppo_mfi_atr_diagnostics,
)
from src.models.artifacts import _bundle_manifest
from src.utils.config_schemas import BacktestConfig


def _performance(index: pd.DatetimeIndex) -> BacktestResult:
    returns = pd.Series([0.0, 0.02, -0.01, 0.0], index=index, name="returns")
    return BacktestResult(
        equity_curve=(1.0 + returns).cumprod(),
        returns=returns,
        gross_returns=returns.rename("gross_returns"),
        costs=pd.Series(0.0, index=index, name="costs"),
        positions=pd.Series([0.0, 1.0, 0.0, 0.0], index=index, name="positions"),
        turnover=pd.Series([0.0, 1.0, 1.0, 0.0], index=index, name="turnover"),
        summary={"profit_factor": 9.5},
        mark_to_market_summary={"profit_factor": 8.5},
        trades=pd.DataFrame(
            {
                "entry_timestamp": [index[0], index[2]],
                "exit_timestamp": [index[1], index[3]],
                "side": ["long", "long"],
                "entry_price": [100.0, 101.0],
                "exit_price": [102.0, 100.0],
                "bars_held": [2, 2],
                "gross_return": [0.21, -0.09],
                "net_return": [0.20, -0.10],
                "cost_paid": [0.01, 0.01],
                "trade_r": [2.0, -1.0],
                "max_favorable_r": [2.2, 0.3],
                "max_adverse_r": [-0.2, -1.1],
                "exit_reason": ["take_profit", "stop_loss"],
            }
        ),
    )


def test_direct_engine_and_schema_share_long_only_default() -> None:
    frame = pd.DataFrame({"signal": [-1.0, -1.0, 0.0], "ret": [0.0, 0.01, -0.01]})
    result = run_backtest(frame, signal_col="signal", returns_col="ret", dd_guard=False)

    assert BacktestConfig.from_dict({}).allow_short is False
    assert bool((result.positions < 0.0).any()) is False


def test_legacy_sharpe_is_explicit_and_conventional_sharpe_is_separate() -> None:
    returns = pd.Series([0.01, -0.005, 0.02, -0.002], dtype=float)
    metrics = compute_backtest_metrics(net_returns=returns, periods_per_year=252)

    expected_conventional = float(returns.mean() / returns.std(ddof=1) * (252 ** 0.5))
    expected_return_over_vol = float(metrics["annualized_return"] / metrics["annualized_vol"])
    assert metrics["conventional_sharpe"] == pytest.approx(expected_conventional)
    assert metrics["return_over_vol_sharpe"] == pytest.approx(expected_return_over_vol)
    assert metrics["sharpe"] == metrics["return_over_vol_sharpe"]
    assert metrics["sharpe_legacy_alias"] == "return_over_vol_sharpe"


def test_oos_gating_uses_configured_custom_output_not_pred_name_heuristics() -> None:
    index = pd.date_range("2025-01-01", periods=3, freq="h")
    frame = pd.DataFrame(
        {
            "custom_model_score": [pd.NA, 0.4, 0.6],
            "custom_oos": [False, True, True],
            "pred_unconfigured_noise": [99.0, 99.0, 99.0],
            "signal": [1.0, 1.0, 1.0],
        },
        index=index,
    )
    cfg = {
        "model": {"outputs": {"pred_ret_col": "custom_model_score", "pred_is_oos_col": "custom_oos"}},
        "signals": {"params": {"forecast_col": "custom_model_score", "pred_is_oos_col": "custom_oos"}},
        "backtest": {"oos_mode": "strict"},
    }

    gated, mask = gate_predictions_to_oos(
        frame, cfg=cfg, model_meta={}, signal_col="signal", asset="AAA"
    )

    assert mask is not None and mask.tolist() == [False, True, True]
    assert gated["signal"].tolist() == [0.0, 1.0, 1.0]
    assert gated["pred_unconfigured_noise"].tolist() == [99.0, 99.0, 99.0]


def test_strict_oos_rejects_configured_non_oos_prediction() -> None:
    frame = pd.DataFrame(
        {"score": [0.2, 0.3], "is_oos": [False, True], "signal": [1.0, 1.0]},
        index=pd.date_range("2025-01-01", periods=2, freq="h"),
    )
    cfg = {
        "model": {"pred_ret_col": "score", "pred_is_oos_col": "is_oos"},
        "signals": {"params": {"forecast_col": "score"}},
        "backtest": {"oos_mode": "strict"},
    }

    with pytest.raises(ValueError, match="non-OOS predictions"):
        gate_predictions_to_oos(frame, cfg=cfg, model_meta={}, signal_col="signal", asset="AAA")


def test_canonical_ledger_preserves_bar_profit_factor_and_separates_units() -> None:
    index = pd.date_range("2025-01-01", periods=4, freq="h")
    performance = _performance(index)
    ledger, metrics = canonicalize_completed_trade_accounting(
        data=pd.DataFrame(index=index),
        cfg={"data": {"symbol": "AAA"}, "backtest": {}},
        performance=performance,
    )

    assert performance.summary["profit_factor"] == 9.5
    assert performance.mark_to_market_summary["profit_factor"] == 8.5
    assert metrics["trade_profit_factor"] == pytest.approx(2.0)
    assert metrics["trade_count"] == 2
    assert {
        "gross_return", "net_return", "cost_return",
        "gross_pnl_currency", "net_pnl_currency", "cost_currency",
        "gross_r_multiple", "net_r_multiple", "return_unit", "r_multiple_unit",
    }.issubset(ledger.columns)
    assert ledger["cost_return"].tolist() == pytest.approx([0.01, 0.01])


def test_canonical_ledger_is_not_rebuilt_during_artifact_saving(tmp_path, monkeypatch) -> None:
    index = pd.date_range("2025-01-01", periods=4, freq="h")
    data = pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "signal": 0.0},
        index=index,
    )
    performance = _performance(index)
    original = artifacts_mod._canonical_completed_trade_ledger
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(artifacts_mod, "_canonical_completed_trade_ledger", counted)
    canonicalize_completed_trade_accounting(
        data=data,
        cfg={"data": {"symbol": "AAA"}, "backtest": {}},
        performance=performance,
    )
    cfg = {
        "config_path": "synthetic.yaml",
        "data": {"symbol": "AAA", "source": "synthetic", "interval": "1h"},
        "model": {"kind": "none", "final_refit": False},
        "backtest": {"signal_col": "signal", "returns_col": "ret", "returns_type": "simple"},
        "diagnostics": {"enabled": False},
        "logging": {"run_name": "single_ledger", "save_model": False},
        "runtime": {"seed": 7},
    }
    final_evaluation = apply_final_trade_accounting(
        {"primary_summary": dict(performance.summary), "timeline_summary": dict(performance.summary)},
        trade_metrics={key: performance.summary[key] for key in (
            "trade_count", "completed_trade_count", "win_rate", "trade_return_profit_factor",
            "trade_r_profit_factor", "trade_profit_factor", "entry_trade_cost", "exit_trade_cost",
            "holding_trade_cost", "total_trade_cost",
        )},
    )
    save_artifacts(
        run_dir=tmp_path / "run",
        cfg=cfg,
        data=data,
        performance=performance,
        model_meta={},
        evaluation=final_evaluation,
        monitoring={},
        execution={},
        execution_orders=None,
        portfolio_weights=None,
        portfolio_diagnostics=None,
        portfolio_meta={},
        storage_meta={},
        run_metadata={"runtime": {"seed": 7}},
        config_hash_sha256="config",
        data_fingerprint={"sha256": "data"},
        lifecycle_context={},
    )

    assert calls == 1
    assert len(pd.read_csv(tmp_path / "run" / "trade_events.csv")) == 2
    saved = json.loads((tmp_path / "run" / "summary.json").read_text(encoding="utf-8"))
    assert saved["summary"] == final_evaluation["primary_summary"]
    assert saved["evaluation"]["primary_summary"] == final_evaluation["primary_summary"]


def test_execution_delay_reports_oos_boundary_losses() -> None:
    index = pd.date_range("2025-01-01", periods=4, freq="h")
    frame = pd.DataFrame({"signal": [1.0, 0.0, 1.0, 0.0]}, index=index)
    delayed, diagnostics = _apply_execution_delay_with_oos_boundary(
        frame,
        signal_col="signal",
        delay_bars=1,
        oos_mask=pd.Series([True, False, True, False], index=index),
    )

    assert delayed["signal"].tolist() == [0.0, 0.0, 0.0, 0.0]
    assert diagnostics["active_signals_blocked_by_oos_boundary"] == 2
    assert diagnostics["active_signals_dropped_at_data_end"] == 0


def test_volatility_resolution_and_model_manifest_are_explicit(tmp_path) -> None:
    frame = pd.DataFrame({"atr_pct_rank_192": [0.1, 0.2]})
    cfg = {
        "features": [
            {"step": "indicator_pullback", "params": {"atr_pct_col": "atr_pct", "atr_pct_rank_window": 192}}
        ],
        "diagnostics": {"forecast": {"volatility_col": "atr_pct_rank_100"}},
    }
    resolution = resolve_forecast_volatility_column({"AAA": frame}, cfg=cfg)
    manifest = _bundle_manifest(
        {
            "model_meta": {
                "feature_cols": ["a", "b"],
                "final_refit": {
                    "enabled": True,
                    "train_start_timestamp": pd.Timestamp("2024-01-01"),
                    "train_end_timestamp": pd.Timestamp("2024-02-01"),
                    "train_start_position": 0,
                    "train_end_position": 99,
                    "estimator_fit_rows": 80,
                    "train_rows_raw": 100,
                },
            },
            "model_config": {},
        },
        model_path=tmp_path / "model.pkl",
    )

    assert resolution == {
        "configured_volatility_col": "atr_pct_rank_100",
        "resolved_volatility_col": "atr_pct_rank_192",
    }
    assert manifest["feature_order"] == ["a", "b"]
    assert manifest["training_range"]["start_timestamp"] == pd.Timestamp("2024-01-01")
    assert manifest["training_range"]["end_timestamp"] == pd.Timestamp("2024-02-01")
    assert manifest["training_range"]["rows"] == 80


def test_strict_oos_robustness_uses_one_scope_and_ignores_inactive_calendar_periods() -> None:
    index = pd.to_datetime([
        "2020-06-01", "2021-01-01", "2021-06-01",
        "2022-01-01", "2022-06-01", "2023-01-01",
    ])
    net = pd.Series([0.0, 0.0, 0.0, 0.02, -0.005, 0.0], index=index)
    costs = pd.Series([0.0, 0.0, 0.0, 0.001, 0.001, 0.0], index=index)
    gross = net + costs
    turnover = pd.Series([0.0, 0.0, 0.0, 1.0, 0.0, 1.0], index=index)
    positions = pd.Series([0.0, 0.0, 0.0, 1.0, 1.0, 0.0], index=index)
    performance = BacktestResult(
        equity_curve=(1.0 + net).cumprod(),
        returns=net,
        gross_returns=gross,
        costs=costs,
        positions=positions,
        turnover=turnover,
        summary={},
        mark_to_market_returns=net.copy(),
        trades=pd.DataFrame(),
    )
    oos_mask = pd.Series([False, True, True, True, True, False], index=index)
    scope = evaluation_scope_metadata(oos_mask, scope="strict_oos_only")
    primary = compute_subset_metrics(
        net_returns=net,
        turnover=turnover,
        costs=costs,
        gross_returns=gross,
        periods_per_year=252,
        mask=oos_mask,
    ) | scope
    cfg = {
        "backtest": {"periods_per_year": 252},
        "diagnostics": {"robustness": {
            "enabled": True,
            "cost_multipliers": [2.0],
            "entry_delay_bars": [],
            "walk_forward_frequency": "YE",
            "gap_loss_per_exposure": 0.0,
        }},
    }
    robustness = build_robustness_diagnostics(
        {"AAA": pd.DataFrame(index=index)},
        cfg=cfg,
        performance=performance,
        is_portfolio=False,
        evaluation_mask=oos_mask,
        evaluation_metadata=scope,
    )

    cost_x1 = robustness["cost_stress"]["cost_x1"]
    for key in (
        "cumulative_return", "annualized_return", "annualized_vol", "sharpe",
        "conventional_sharpe", "profit_factor", "bar_return_profit_factor",
        "gross_pnl", "net_pnl", "total_cost",
    ):
        assert cost_x1[key] == pytest.approx(primary[key])
    assert {key: cost_x1[key] for key in scope} == scope
    walk = robustness["walk_forward"]
    assert walk["total_calendar_periods"] == 4
    assert walk["active_oos_periods"] == 1
    assert walk["positive_active_periods"] == 1
    assert walk["positive_active_period_ratio"] == 1.0
    assert "folds" not in walk
    trade_metrics = {
        "trade_count": 0,
        "completed_trade_count": 0,
        "win_rate": 0.0,
        "trade_return_profit_factor": 0.0,
        "trade_r_profit_factor": 0.0,
        "trade_profit_factor": 0.0,
        "entry_trade_cost": 0.0,
        "exit_trade_cost": 0.0,
        "holding_trade_cost": 0.0,
        "total_trade_cost": 0.0,
    }
    evaluation = apply_final_trade_accounting(
            {
                **scope,
                "scope": "strict_oos_only",
                "primary_summary": primary,
            "oos_only_summary": dict(primary),
            "mark_to_market_summary": robustness["mark_to_market"],
            "robustness": robustness,
        },
        trade_metrics=trade_metrics,
    )
    assert_run_consistency(
        evaluation=evaluation,
        performance=performance,
        evaluation_mask=oos_mask,
        trade_metrics=trade_metrics,
    )
    assert evaluation["oos_summary_non_oos_rows"] == 0


def test_volatility_rank_diagnostic_reports_configured_oos_rows() -> None:
    index = pd.date_range("2025-01-01", periods=4, freq="h")
    mask = pd.Series([False, True, True, True], index=index)
    scope = evaluation_scope_metadata(mask, scope="strict_oos_only")
    diagnostic = build_oos_volatility_rank_diagnostic(
        {"ETHUSD": pd.DataFrame({"atr_pct_rank_192": [0.1, 0.2, 0.7, 0.9]}, index=index)},
        model_meta={"diagnostics": {"forecast_volatility": {
            "configured_volatility_col": "atr_pct_rank_192",
            "resolved_volatility_col": "atr_pct_rank_192",
        }}},
        evaluation_mask=mask,
        evaluation_metadata_payload=scope,
    )

    assert diagnostic["status"] == "ok"
    assert diagnostic["resolved_volatility_col"] == "atr_pct_rank_192"
    assert diagnostic["evaluation_rows"] == 3
    assert diagnostic["evaluation_value_rows"] == 3


def test_single_asset_evaluation_scopes_primary_mtm_and_volatility_to_same_oos_rows() -> None:
    index = pd.date_range("2025-01-01", periods=4, freq="h")
    frame = pd.DataFrame(
        {
            "pred_is_oos": [False, True, True, True],
            "atr_pct_rank_192": [0.1, 0.2, 0.7, 0.9],
        },
        index=index,
    )
    net = pd.Series([0.5, 0.01, -0.005, 0.002], index=index)
    costs = pd.Series([0.0, 0.001, 0.001, 0.0], index=index)
    performance = BacktestResult(
        equity_curve=(1.0 + net).cumprod(),
        returns=net,
        gross_returns=net + costs,
        costs=costs,
        positions=pd.Series([0.0, 1.0, 1.0, 0.0], index=index),
        turnover=pd.Series([0.0, 1.0, 0.0, 1.0], index=index),
        summary=compute_backtest_metrics(
            net_returns=net,
            periods_per_year=252,
            turnover=pd.Series([0.0, 1.0, 0.0, 1.0], index=index),
            costs=costs,
            gross_returns=net + costs,
        ),
        mark_to_market_returns=net.copy(),
        trades=pd.DataFrame(),
    )
    evaluation = build_single_asset_evaluation(
        "ETHUSD",
        frame,
        performance=performance,
        model_meta={
            "pred_is_oos_col": "pred_is_oos",
            "diagnostics": {"forecast_volatility": {
                "configured_volatility_col": "atr_pct_rank_192",
                "resolved_volatility_col": "atr_pct_rank_192",
            }},
        },
        periods_per_year=252,
        backtest_cfg={"signal_col": "signal"},
    )

    assert evaluation["evaluation_rows"] == 3
    assert evaluation["primary_summary"]["evaluation_rows"] == 3
    assert evaluation["mark_to_market_summary"]["evaluation_rows"] == 3
    assert evaluation["model_oos_volatility_summary"]["evaluation_rows"] == 3
    assert evaluation["primary_summary"]["cumulative_return"] != pytest.approx(
        performance.summary["cumulative_return"]
    )


def test_trade_breakdowns_reconcile_cost_components_and_net_pnl() -> None:
    index = pd.date_range("2025-01-01", periods=4, freq="h")
    performance = _performance(index)
    ledger, _ = canonicalize_completed_trade_accounting(
        data=pd.DataFrame(index=index),
        cfg={"data": {"symbol": "AAA"}, "backtest": {}},
        performance=performance,
    )
    ledger["asset"] = "AAA"
    performance.trades = ledger
    diagnostics = compute_baseline_vwap_rms_ema_ppo_mfi_atr_diagnostics(
        {"AAA": pd.DataFrame({"signal": 1.0}, index=index)},
        performance=performance,
        signal_col="signal",
    )
    side = diagnostics["performance_by_side"]["long"]

    assert side["entry_cost"] + side["exit_cost"] + side["holding_cost"] == pytest.approx(side["total_cost"])
    assert side["gross_pnl"] - side["total_cost"] == pytest.approx(side["net_pnl"])
    assert side["pnl_unit"] == "fractional_return"


def test_raw_input_fingerprint_distinguishes_computed_from_trusted_verification(tmp_path) -> None:
    raw_path = tmp_path / "raw.csv"
    raw_path.write_text("timestamp,close\n2025-01-01,100\n", encoding="utf-8")
    computed = _raw_input_fingerprint_record(
        asset="ETHUSD",
        path=raw_path,
        expected_trusted_sha256=None,
        repro_mode="strict",
    )
    verified = _raw_input_fingerprint_record(
        asset="ETHUSD",
        path=raw_path,
        expected_trusted_sha256=computed["sha256"],
        repro_mode="strict",
    )

    assert computed["fingerprint_status"] == "computed_not_verified"
    assert computed["verified_fingerprint"] is False
    assert computed["fingerprint_matches_expected"] is None
    assert computed["size_bytes"] == raw_path.stat().st_size
    assert computed["modification_timestamp_utc"]
    assert verified["fingerprint_status"] == "verified"
    assert verified["verified_fingerprint"] is True
