from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pandas.testing as pdt

from src.backtesting.portfolio_barrier import run_portfolio_barrier_backtest
from src.evaluation.robustness import cost_multiplier_stress
from src.experiments.orchestration import backtest_stage
from src.experiments.support.matb_diagnostics import build_target_backtest_parity_diagnostics


def test_cost_multiplier_diagnostics_apply_declared_multiplier() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    gross = pd.Series([0.01, 0.0, -0.005, 0.002], index=index)
    costs = pd.Series([0.001, 0.001, 0.001, 0.001], index=index)
    stress = cost_multiplier_stress(
        gross_returns=gross,
        costs=costs,
        periods_per_year=365,
        multipliers=[1, 2, 3, 5],
    )
    assert list(stress) == ["cost_x1", "cost_x2", "cost_x3", "cost_x5"]
    assert stress["cost_x1"]["cumulative_return"] > stress["cost_x2"]["cumulative_return"]
    assert stress["cost_x2"]["cumulative_return"] > stress["cost_x5"]["cumulative_return"]


def test_matb_entry_delay_stress_changes_execution_delay_not_candidate_time(monkeypatch) -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="30min", tz="UTC")
    frames = {"A": pd.DataFrame({"signal": [1.0, 0.0, 0.0, 0.0]}, index=index)}
    captured: dict[str, object] = {}

    def fake_run(asset_frames, *, cfg):
        captured["signals"] = asset_frames["A"]["signal"].copy()
        captured["entry_delay_bars"] = cfg["backtest"]["strategy_path"]["entry_delay_bars"]
        returns = pd.Series(0.0, index=index)
        return SimpleNamespace(mark_to_market_returns=returns, net_returns=returns), None, None, None

    monkeypatch.setattr(backtest_stage, "run_portfolio_backtest", fake_run)
    cfg = {
        "backtest": {
            "signal_col": "signal",
            "periods_per_year": 365,
            "strategy_path": {"kind": "matb", "entry_delay_bars": 0},
        }
    }
    backtest_stage._run_portfolio_delay_stress(frames, cfg=cfg, delay_bars=2)
    pdt.assert_series_equal(captured["signals"], frames["A"]["signal"])
    assert captured["entry_delay_bars"] == 2


def test_matb_repeated_backtest_is_bitwise_deterministic() -> None:
    index = pd.date_range("2024-01-01", periods=7, freq="30min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": 100.0,
            "high": 100.5,
            "low": 99.5,
            "close": 100.0,
            "matb_atr": 1.0,
            "matb_trend_score": 1.0,
            "signal": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        },
        index=index,
    )
    frame.loc[index[1], "low"] = 97.0
    kwargs = {
        "signal_col": "signal",
        "volatility_col": "matb_atr",
        "strategy_path": {"kind": "matb", "max_holding_bars": 4},
    }
    first, first_weights, first_diag, first_meta = run_portfolio_barrier_backtest({"A": frame}, **kwargs)
    second, second_weights, second_diag, second_meta = run_portfolio_barrier_backtest({"A": frame}, **kwargs)
    pdt.assert_series_equal(first.net_returns, second.net_returns, check_exact=True)
    pdt.assert_frame_equal(first.trades, second.trades, check_exact=True)
    pdt.assert_frame_equal(first_weights, second_weights, check_exact=True)
    pdt.assert_frame_equal(first_diag, second_diag, check_exact=True)
    assert first_meta == second_meta


def test_matb_parity_diagnostic_matrix_has_no_failures() -> None:
    parity = build_target_backtest_parity_diagnostics()
    assert len(parity) == 10
    assert parity["passed"].all()
    assert parity["absolute_error"].max() <= 1e-12
