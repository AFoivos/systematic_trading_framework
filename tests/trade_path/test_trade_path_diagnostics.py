from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtesting.engine import BacktestResult
from src.evaluation.trade_path_diagnostics import (
    build_trade_ledger_from_position_transitions,
    build_trade_paths,
    enrich_trade_lifecycle_columns,
    simulate_counterfactual_exits,
    summarize_probability_trade_quality,
    summarize_trade_lifecycle,
)
from src.experiments.orchestration.artifacts import enrich_evaluation_with_trade_path_diagnostics


def test_enrich_trade_lifecycle_columns_handles_thresholds_and_capture_safely() -> None:
    trades = pd.DataFrame(
        {
            "trade_r": [1.2, -0.4, -1.0, 0.0],
            "max_favorable_r": [1.5, 0.8, 0.0, np.nan],
            "max_adverse_r": [-0.2, -0.7, -1.2, np.nan],
        }
    )

    out = enrich_trade_lifecycle_columns(trades, [0.5, 1.0])

    assert out["was_ever_0_5r"].tolist() == [True, True, False, False]
    assert out["lost_but_was_positive"].tolist() == [False, True, False, False]
    assert out["lost_but_reached_0_5r"].tolist() == [False, True, False, False]
    assert out.loc[0, "giveback_r"] == pytest.approx(0.3)
    assert out.loc[0, "capture_ratio"] == pytest.approx(0.8)
    assert np.isnan(out.loc[2, "capture_ratio"])


def test_summarize_trade_lifecycle_conditional_exit_and_timing_metrics() -> None:
    trades = pd.DataFrame(
        {
            "trade_r": [1.0, -0.5, -1.0, 0.4],
            "max_favorable_r": [1.2, 0.8, 1.4, 0.3],
            "max_adverse_r": [-0.3, -0.8, -1.1, -0.1],
            "exit_reason": ["take_profit", "stop_loss", "stop_loss", "time_exit"],
            "bars_held": [2, 5, 9, 1],
            "time_to_mfe": [1, 2, 4, 1],
            "time_to_mae": [1, 3, 2, 1],
        }
    )

    summary = summarize_trade_lifecycle(trades, [0.5, 1.0], [1, 2, 4, 8, 16])

    assert summary["conditional_probabilities"]["prob_final_win"] == pytest.approx(0.5)
    assert summary["conditional_probabilities"]["prob_final_loss_given_mfe_ge_0_5r"] == pytest.approx(2 / 3)
    assert summary["exit_reason_quality"]["stop_loss"]["trade_count"] == 2
    assert summary["timing"]["prob_mfe_ge_1r_within_4_bars"] == pytest.approx(0.5)
    assert summary["timing"]["avg_r_by_bars_held_bucket"]["5-8"] == pytest.approx(-0.5)


def test_build_trade_paths_converts_long_and_short_to_r_space() -> None:
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    frame = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.0, 102.0, 103.0],
        },
        index=idx,
    )
    short_frame = pd.DataFrame(
        {
            "open": [100.0, 99.0, 98.0],
            "high": [101.0, 100.0, 99.0],
            "low": [99.0, 97.0, 96.0],
            "close": [100.0, 98.0, 97.0],
        },
        index=idx,
    )
    trades = pd.DataFrame(
        {
            "asset": ["AAA", "BBB", "AAA"],
            "side": ["long", "short", "long"],
            "signal_timestamp": [idx[0], idx[0], idx[0]],
            "entry_timestamp": [idx[0], idx[0], idx[0]],
            "exit_timestamp": [idx[2], idx[2], idx[2]],
            "entry_price": [100.0, 100.0, 100.0],
            "stop_loss_price": [98.0, 102.0, np.nan],
            "trade_r": [1.5, 1.5, 0.0],
            "exit_reason": ["time", "time", "time"],
        }
    )

    paths, diagnostics = build_trade_paths({"AAA": frame, "BBB": short_frame}, trades)

    long_last = paths.loc[(paths["trade_id"] == 0) & (paths["bar_in_trade"] == 2)].iloc[0]
    short_last = paths.loc[(paths["trade_id"] == 1) & (paths["bar_in_trade"] == 2)].iloc[0]
    assert long_last["close_r"] == pytest.approx(1.5)
    assert short_last["close_r"] == pytest.approx(1.5)
    assert short_last["high_r"] == pytest.approx(2.0)
    assert short_last["low_r"] == pytest.approx(0.5)
    assert short_last["mfe_so_far_r"] == pytest.approx(2.0)
    assert short_last["mae_so_far_r"] == pytest.approx(-0.5)
    assert diagnostics["skipped_trade_paths_missing_risk"] == 1


def test_counterfactual_exits_use_sequential_path_state() -> None:
    paths = pd.DataFrame(
        {
            "trade_id": [0, 0, 0, 1, 1, 1, 2, 2],
            "bar_in_trade": [0, 1, 2, 0, 1, 2, 0, 1],
            "high_r": [0.1, 0.6, 0.7, 0.2, 0.6, 0.8, 1.2, 1.4],
            "low_r": [-0.1, 0.2, 0.1, -0.1, 0.2, -0.1, 0.7, 0.8],
            "close_r": [0.0, 0.4, -0.4, 0.0, 0.3, -0.5, 1.0, 0.9],
            "trade_r": [-0.4, -0.4, -0.4, -0.5, -0.5, -0.5, 0.9, 0.9],
        }
    )

    result, _ = simulate_counterfactual_exits(
        paths,
        policies=["breakeven_after_0_5r", "trail_0_5r_after_1_0r"],
    )
    pivot = result.pivot(index="trade_id", columns="policy", values="counterfactual_r")

    assert pivot.loc[0, "breakeven_after_0_5r"] == pytest.approx(-0.4)
    assert pivot.loc[1, "breakeven_after_0_5r"] == pytest.approx(0.0)
    assert pivot.loc[2, "trail_0_5r_after_1_0r"] == pytest.approx(0.7)


def test_counterfactual_same_bar_breakeven_is_conservative_and_deterministic() -> None:
    paths = pd.DataFrame(
        {
            "trade_id": [0],
            "bar_in_trade": [0],
            "high_r": [0.6],
            "low_r": [-0.2],
            "close_r": [-0.1],
            "trade_r": [-0.3],
        }
    )

    result, _ = simulate_counterfactual_exits(paths, policies=["breakeven_after_0_5r"])

    assert result.loc[0, "counterfactual_r"] == pytest.approx(0.0)


def test_probability_trade_quality_filters_to_oos_and_warns_without_marker() -> None:
    trades = pd.DataFrame(
        {
            "pred_prob": [0.1, 0.2, 0.8, 0.9],
            "pred_is_oos": [False, True, True, False],
            "trade_r": [-1.0, -0.2, 1.0, 2.0],
            "max_favorable_r": [0.1, 0.4, 1.2, 2.5],
            "max_adverse_r": [-1.0, -0.5, -0.2, -0.1],
        }
    )

    quality, diagnostics = summarize_probability_trade_quality(trades, "pred_prob", "pred_is_oos")

    assert int(quality["trade_count"].sum()) == 2
    assert diagnostics["warnings"] == []

    quality_no_oos, diagnostics_no_oos = summarize_probability_trade_quality(
        trades.drop(columns=["pred_is_oos"]),
        "pred_prob",
        "pred_is_oos",
    )
    assert int(quality_no_oos["trade_count"].sum()) == 4
    assert diagnostics_no_oos["warnings"] == ["probability_trade_quality computed without OOS marker"]


def test_probability_trade_quality_expected_r_after_cost_uses_only_r_unit_costs() -> None:
    trades = pd.DataFrame(
        {
            "pred_prob": [0.2, 0.8],
            "pred_is_oos": [True, True],
            "trade_r": [1.0, -0.5],
            "total_cost_r": [0.1, 0.2],
        }
    )
    quality, diagnostics = summarize_probability_trade_quality(trades, "pred_prob", "pred_is_oos")

    assert diagnostics["warnings"] == []
    weighted = (quality["expected_r_after_cost"] * quality["trade_count"]).sum() / quality["trade_count"].sum()
    assert weighted == pytest.approx(((1.0 - 0.1) + (-0.5 - 0.2)) / 2.0)

    component_trades = trades.drop(columns=["total_cost_r"]).assign(commission_r=[0.03, 0.04], slippage_r=[0.02, 0.06])
    component_quality, _ = summarize_probability_trade_quality(component_trades, "pred_prob", "pred_is_oos")
    component_weighted = (
        component_quality["expected_r_after_cost"] * component_quality["trade_count"]
    ).sum() / component_quality["trade_count"].sum()
    assert component_weighted == pytest.approx(((1.0 - 0.05) + (-0.5 - 0.10)) / 2.0)

    non_r_cost_trades = trades.drop(columns=["total_cost_r"]).assign(cost_paid=[1.0, 2.0])
    non_r_quality, non_r_diag = summarize_probability_trade_quality(non_r_cost_trades, "pred_prob", "pred_is_oos")
    assert non_r_quality["expected_r_after_cost"].isna().all()
    assert non_r_diag["warnings"] == [
        "probability_trade_quality expected_r_after_cost skipped: cost columns are not in R units"
    ]


def test_build_trade_ledger_from_position_transitions_long_trade() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    frame = pd.DataFrame(
        {
            "open": [100.0, 100.0, 105.0, 110.0],
            "high": [101.0, 101.0, 108.0, 112.0],
            "low": [99.0, 99.0, 97.0, 109.0],
            "close": [100.0, 100.0, 105.0, 110.0],
            "atr_48": [5.0, 5.0, 5.0, 5.0],
        },
        index=idx,
    )
    positions = pd.Series([0.0, 1.0, 1.0, 0.0], index=idx)
    asset_returns = frame["close"].pct_change().fillna(0.0)
    gross_returns = positions.shift(1).fillna(0.0) * asset_returns

    ledger, diagnostics = build_trade_ledger_from_position_transitions(
        {"AAA": frame},
        positions=positions,
        gross_returns=gross_returns,
        net_returns=gross_returns,
        costs=pd.Series(0.0, index=idx),
        turnover=positions.diff().abs().fillna(0.0),
        cfg={"backtest": {"volatility_col": "atr_48"}},
    )

    trade = ledger.iloc[0]
    assert diagnostics["warnings"] == []
    assert trade["side"] == "long"
    assert trade["entry_timestamp"] == idx[1]
    assert trade["exit_timestamp"] == idx[3]
    assert trade["bars_held"] == 2
    assert trade["gross_return"] == pytest.approx(0.10)
    assert trade["gross_trade_r"] == pytest.approx(2.0)
    assert trade["trade_r"] == pytest.approx(2.0)
    assert trade["max_favorable_r"] == pytest.approx(2.4)
    assert trade["max_adverse_r"] == pytest.approx(-0.6)
    assert trade["time_to_mfe"] == 2
    assert trade["time_to_mae"] == 1
    assert trade["risk_distance_source"] == "atr_48"


def test_build_trade_ledger_from_position_transitions_short_trade() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    frame = pd.DataFrame(
        {
            "open": [100.0, 100.0, 95.0, 90.0],
            "high": [101.0, 101.0, 104.0, 92.0],
            "low": [99.0, 99.0, 94.0, 88.0],
            "close": [100.0, 100.0, 95.0, 90.0],
            "atr_48": [5.0, 5.0, 5.0, 5.0],
        },
        index=idx,
    )
    positions = pd.Series([0.0, -1.0, -1.0, 0.0], index=idx)
    asset_returns = frame["close"].pct_change().fillna(0.0)
    gross_returns = positions.shift(1).fillna(0.0) * asset_returns

    ledger, diagnostics = build_trade_ledger_from_position_transitions(
        {"AAA": frame},
        positions=positions,
        gross_returns=gross_returns,
        net_returns=gross_returns,
        costs=pd.Series(0.0, index=idx),
        turnover=positions.diff().abs().fillna(0.0),
        cfg={"backtest": {"volatility_col": "atr_48"}},
    )

    trade = ledger.iloc[0]
    assert diagnostics["warnings"] == []
    assert trade["side"] == "short"
    assert trade["gross_return"] == pytest.approx((1.0 + 0.05) * (1.0 + 0.05263157894736836) - 1.0)
    assert trade["gross_trade_r"] == pytest.approx(2.0)
    assert trade["trade_r"] == pytest.approx(2.0)
    assert trade["max_favorable_r"] == pytest.approx(2.4)
    assert trade["max_adverse_r"] == pytest.approx(-0.8)
    assert trade["time_to_mfe"] == 2
    assert trade["time_to_mae"] == 1


def test_build_trade_ledger_from_position_transitions_reversal_closes_and_reopens() -> None:
    idx = pd.date_range("2024-01-01", periods=6, freq="D")
    frame = pd.DataFrame(
        {
            "open": [100.0, 100.0, 105.0, 103.0, 100.0, 95.0],
            "high": [101.0, 101.0, 106.0, 104.0, 101.0, 96.0],
            "low": [99.0, 99.0, 104.0, 102.0, 99.0, 94.0],
            "close": [100.0, 100.0, 105.0, 103.0, 100.0, 95.0],
            "atr_48": [5.0] * 6,
        },
        index=idx,
    )
    positions = pd.Series([0.0, 1.0, 1.0, -1.0, -1.0, 0.0], index=idx)
    asset_returns = frame["close"].pct_change().fillna(0.0)
    gross_returns = positions.shift(1).fillna(0.0) * asset_returns

    ledger, diagnostics = build_trade_ledger_from_position_transitions(
        {"AAA": frame},
        positions=positions,
        gross_returns=gross_returns,
        net_returns=gross_returns,
        costs=pd.Series(0.0, index=idx),
        turnover=positions.diff().abs().fillna(0.0),
        cfg={"backtest": {"volatility_col": "atr_48"}},
    )

    assert diagnostics["position_transition_count"] == 4
    assert ledger["side"].tolist() == ["long", "short"]
    assert ledger.loc[0, "exit_timestamp"] == idx[3]
    assert ledger.loc[0, "exit_reason"] == "reversal"
    assert ledger.loc[1, "entry_timestamp"] == idx[3]
    assert ledger.loc[1, "exit_timestamp"] == idx[5]
    assert ledger.loc[1, "exit_reason"] == "position_exit"


def test_build_trade_ledger_trade_r_signs_and_costs() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    base = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0, 100.0],
            "high": [101.0, 101.0, 101.0, 101.0],
            "low": [99.0, 99.0, 99.0, 99.0],
            "atr_48": [5.0, 5.0, 5.0, 5.0],
        },
        index=idx,
    )

    def trade_r_for(close: list[float], position_value: float, final_cost: float = 0.0) -> float:
        frame = base.assign(close=close)
        positions = pd.Series([0.0, position_value, position_value, 0.0], index=idx)
        asset_returns = frame["close"].pct_change().fillna(0.0)
        gross_returns = positions.shift(1).fillna(0.0) * asset_returns
        costs = pd.Series([0.0, 0.0, 0.0, final_cost], index=idx)
        ledger, _ = build_trade_ledger_from_position_transitions(
            {"AAA": frame},
            positions=positions,
            gross_returns=gross_returns,
            net_returns=gross_returns - costs,
            costs=costs,
            turnover=positions.diff().abs().fillna(0.0),
            cfg={"backtest": {"volatility_col": "atr_48"}},
        )
        return float(ledger.loc[0, "trade_r"])

    profitable_long = trade_r_for([100.0, 100.0, 105.0, 110.0], 1.0)
    losing_long = trade_r_for([100.0, 100.0, 98.0, 95.0], 1.0)
    profitable_short = trade_r_for([100.0, 100.0, 95.0, 90.0], -1.0)
    losing_short = trade_r_for([100.0, 100.0, 103.0, 105.0], -1.0)
    profitable_long_after_cost = trade_r_for([100.0, 100.0, 105.0, 110.0], 1.0, final_cost=0.01)

    assert profitable_long > 0.0
    assert losing_long < 0.0
    assert profitable_short > 0.0
    assert losing_short < 0.0
    assert profitable_long_after_cost == pytest.approx(profitable_long - 0.2)


def test_build_trade_ledger_counts_entry_and_exit_costs() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    frame = pd.DataFrame(
        {
            "open": [100.0, 100.0, 105.0, 110.0],
            "high": [101.0, 101.0, 108.0, 112.0],
            "low": [99.0, 99.0, 97.0, 109.0],
            "close": [100.0, 100.0, 105.0, 110.0],
            "atr_48": [5.0, 5.0, 5.0, 5.0],
        },
        index=idx,
    )
    positions = pd.Series([0.0, 1.0, 1.0, 0.0], index=idx)
    gross_returns = positions.shift(1).fillna(0.0) * frame["close"].pct_change().fillna(0.0)
    costs = pd.Series([0.0, 0.01, 0.0, 0.01], index=idx)

    ledger, _ = build_trade_ledger_from_position_transitions(
        {"AAA": frame},
        positions=positions,
        gross_returns=gross_returns,
        net_returns=gross_returns - costs,
        costs=costs,
        turnover=positions.diff().abs().fillna(0.0),
        cfg={"backtest": {"volatility_col": "atr_48"}},
    )

    trade = ledger.iloc[0]
    assert trade["entry_cost"] == pytest.approx(0.01)
    assert trade["exit_cost"] == pytest.approx(0.01)
    assert trade["holding_cost"] == pytest.approx(0.0)
    assert trade["total_cost"] == pytest.approx(0.02)
    assert trade["total_cost_r"] == pytest.approx(0.4)
    assert trade["gross_trade_r"] == pytest.approx(2.0)
    assert trade["trade_r"] == pytest.approx(1.6)


def test_build_trade_ledger_counts_exit_only_cost() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    frame = pd.DataFrame(
        {
            "open": [100.0, 100.0, 105.0, 110.0],
            "high": [101.0, 101.0, 108.0, 112.0],
            "low": [99.0, 99.0, 97.0, 109.0],
            "close": [100.0, 100.0, 105.0, 110.0],
            "atr_48": [5.0, 5.0, 5.0, 5.0],
        },
        index=idx,
    )
    positions = pd.Series([0.0, 1.0, 1.0, 0.0], index=idx)
    gross_returns = positions.shift(1).fillna(0.0) * frame["close"].pct_change().fillna(0.0)
    costs = pd.Series([0.0, 0.0, 0.0, 0.01], index=idx)

    ledger, _ = build_trade_ledger_from_position_transitions(
        {"AAA": frame},
        positions=positions,
        gross_returns=gross_returns,
        net_returns=gross_returns - costs,
        costs=costs,
        turnover=positions.diff().abs().fillna(0.0),
        cfg={"backtest": {"volatility_col": "atr_48"}},
    )

    trade = ledger.iloc[0]
    assert trade["entry_cost"] == pytest.approx(0.0)
    assert trade["exit_cost"] == pytest.approx(0.01)
    assert trade["total_cost"] == pytest.approx(0.01)
    assert trade["trade_r"] == pytest.approx(1.8)


def test_build_trade_ledger_splits_reversal_cost_without_double_counting() -> None:
    idx = pd.date_range("2024-01-01", periods=6, freq="D")
    frame = pd.DataFrame(
        {
            "open": [100.0, 100.0, 105.0, 103.0, 100.0, 95.0],
            "high": [101.0, 101.0, 106.0, 104.0, 101.0, 96.0],
            "low": [99.0, 99.0, 104.0, 102.0, 99.0, 94.0],
            "close": [100.0, 100.0, 105.0, 103.0, 100.0, 95.0],
            "atr_48": [5.0] * 6,
        },
        index=idx,
    )
    positions = pd.Series([0.0, 1.0, 1.0, -1.0, -1.0, 0.0], index=idx)
    turnover = positions.diff().abs().fillna(0.0)
    costs = 0.01 * turnover
    gross_returns = positions.shift(1).fillna(0.0) * frame["close"].pct_change().fillna(0.0)

    ledger, _ = build_trade_ledger_from_position_transitions(
        {"AAA": frame},
        positions=positions,
        gross_returns=gross_returns,
        net_returns=gross_returns - costs,
        costs=costs,
        turnover=turnover,
        cfg={"backtest": {"volatility_col": "atr_48"}},
    )

    assert len(ledger) == 2
    assert ledger.loc[0, "entry_cost"] == pytest.approx(0.01)
    assert ledger.loc[0, "exit_cost"] == pytest.approx(0.01)
    assert ledger.loc[0, "total_cost"] == pytest.approx(0.02)
    assert ledger.loc[1, "entry_cost"] == pytest.approx(0.01)
    assert ledger.loc[1, "exit_cost"] == pytest.approx(0.01)
    assert ledger.loc[1, "total_cost"] == pytest.approx(0.02)
    assert ledger["total_cost"].sum() == pytest.approx(float(costs.sum()))


def test_build_trade_ledger_all_flat_positions_produce_no_ledger() -> None:
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    frame = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.0, 101.0, 102.0],
            "atr_48": [5.0, 5.0, 5.0],
        },
        index=idx,
    )
    positions = pd.Series([0.0, 0.0, 0.0], index=idx)

    ledger, diagnostics = build_trade_ledger_from_position_transitions(
        {"AAA": frame},
        positions=positions,
        gross_returns=pd.Series(0.0, index=idx),
        net_returns=pd.Series(0.0, index=idx),
        costs=pd.Series(0.0, index=idx),
        turnover=pd.Series(0.0, index=idx),
        cfg={"backtest": {"volatility_col": "atr_48"}},
    )

    assert ledger.empty
    assert "fallback trade ledger skipped: no position transitions" in diagnostics["warnings"]


def test_trade_path_enrichment_builds_fallback_ledger_when_performance_trades_missing() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    data = pd.DataFrame(
        {
            "open": [100.0, 100.0, 105.0, 110.0],
            "high": [101.0, 101.0, 108.0, 112.0],
            "low": [99.0, 99.0, 97.0, 109.0],
            "close": [100.0, 100.0, 105.0, 110.0],
            "atr_48": [5.0, 5.0, 5.0, 5.0],
            "pred_prob": [0.4, 0.7, 0.8, 0.6],
            "pred_is_oos": [True, True, True, True],
        },
        index=idx,
    )
    positions = pd.Series([0.0, 1.0, 1.0, 0.0], index=idx, name="positions")
    gross_returns = positions.shift(1).fillna(0.0) * data["close"].pct_change().fillna(0.0)
    performance = BacktestResult(
        equity_curve=(1.0 + gross_returns).cumprod(),
        returns=gross_returns.rename("returns"),
        gross_returns=gross_returns.rename("gross_returns"),
        costs=pd.Series(0.0, index=idx, name="costs"),
        positions=positions,
        turnover=positions.diff().abs().fillna(0.0).rename("turnover"),
        summary={"cumulative_return": float((1.0 + gross_returns).prod() - 1.0)},
        trades=None,
    )

    updated, context = enrich_evaluation_with_trade_path_diagnostics(
        cfg={
            "data": {"symbol": "AAA"},
            "backtest": {"volatility_col": "atr_48"},
            "diagnostics": {"enabled": True, "trade_path": {"enabled": True}},
        },
        data=data,
        performance=performance,
        model_meta={"pred_prob_col": "pred_prob", "pred_is_oos_col": "pred_is_oos"},
        evaluation={"primary_summary": {}, "trade_diagnostics": {}},
    )

    warnings = updated["trade_diagnostics"]["trade_path"]["warnings"]
    assert not context["trades_enriched"].empty
    assert not context["trade_paths"].empty
    assert updated["primary_summary"]["trade_count"] == 1
    assert "trade path construction skipped: no executed trades" not in warnings
    assert "trade_path diagnostics skipped: no executed trades or target candidate trades" not in warnings
