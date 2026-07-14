from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtesting.portfolio_barrier import run_portfolio_barrier_backtest


def _bar_frame(index: pd.DatetimeIndex, signal: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": 100.0,
            "high": 100.1,
            "low": 99.9,
            "close": 100.0,
            "atr_20": 1.0,
            "close_ret": np.linspace(-0.01, 0.01, len(index)),
            "signal": signal.reindex(index).fillna(0.0),
        },
        index=index,
    )


def test_dynamic_exit_executes_at_next_real_open_before_intrabar_stop() -> None:
    index = pd.date_range("2024-01-02", periods=5, freq="30min")
    frame = _bar_frame(index, pd.Series([1.0, 0.0, 0.0, 0.0, 0.0], index=index))
    frame["dynamic_long"] = [False, True, False, False, False]
    frame["dynamic_short"] = False
    frame["dynamic_reason"] = [pd.NA, "convergence", pd.NA, pd.NA, pd.NA]
    frame.loc[index[2], ["open", "high", "low"]] = [101.0, 102.0, 80.0]
    performance, _, _, _ = run_portfolio_barrier_backtest(
        {"A": frame}, signal_col="signal", volatility_col="atr_20", profit_barrier_r=10.0,
        stop_barrier_r=10.0, vertical_barrier_bars=3, tie_break="stop",
        dynamic_exit={"enabled": True, "long_exit_col": "dynamic_long", "short_exit_col": "dynamic_short", "reason_col": "dynamic_reason", "execution": "next_open"},
    )
    trade = performance.trades.iloc[0]
    assert trade["exit_reason"] == "convergence"
    assert trade["exit_price"] == 101.0
    assert trade["dynamic_exit_signal_time"] == index[1]
    assert trade["dynamic_exit_execution_time"] == index[2]


def test_same_side_correlation_guard_rejects_using_t_minus_one_intersection() -> None:
    index = pd.date_range("2024-01-02", periods=270, freq="30min")
    a_signal = pd.Series(0.0, index=index)
    b_signal = pd.Series(0.0, index=index)
    a_signal.iloc[0] = 1.0
    b_signal.iloc[250] = 1.0
    a = _bar_frame(index, a_signal)
    b = _bar_frame(index, b_signal)
    b["close_ret"] = a["close_ret"]
    performance, _, _, meta = run_portfolio_barrier_backtest(
        {"A": a, "B": b}, signal_col="signal", volatility_col="atr_20", profit_barrier_r=100.0,
        stop_barrier_r=100.0, vertical_barrier_bars=260,
        correlation_guard={"enabled": True, "returns_col": "close_ret", "window_bars": 240, "minimum_observations": 100, "maximum_abs_correlation": 0.80, "same_direction_only": True, "action": "reject"},
    )
    assert len(performance.trades) == 1
    assert meta["correlation_guard"]["rejections"] == 1
    assert meta["correlation_guard_events"][0]["entry_correlation_rejected_against"] == "A"
