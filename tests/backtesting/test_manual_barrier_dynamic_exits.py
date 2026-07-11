from __future__ import annotations

import pandas as pd
import pytest

from src.backtesting.manual_barrier import run_manual_barrier_backtest


def _frame(
    *,
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    signals: list[float],
    forecasts: list[float] | None = None,
) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=len(opens), freq="30min")
    data = pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "signal": signals,
            "forecast": forecasts if forecasts is not None else [1.0] * len(opens),
        },
        index=index,
    )
    for col in [
        "mama_minus_fama_over_atr",
        "roofing_filter_over_atr",
        "decycler_slope_over_atr",
        "instantaneous_trendline_slope_over_atr",
        "frama_slope_over_atr",
    ]:
        data[col] = 1.0
    return data


def _forecast_decay(long_exit: float = 0.10, short_exit: float = -0.10) -> dict[str, object]:
    return {
        "enabled": True,
        "forecast_decay": {
            "enabled": True,
            "long_hold_threshold": 0.70,
            "long_exit_threshold": long_exit,
            "short_hold_threshold": -0.85,
            "short_exit_threshold": short_exit,
            "exit_price": "next_open",
            "min_bars_held": 1,
        },
    }


def _run(
    frame: pd.DataFrame,
    *,
    dynamic_exits: dict[str, object] | None = None,
    partial_exits: dict[str, object] | None = None,
    take_profit_r: float = 10.0,
    stop_loss_r: float = 10.0,
    max_holding_bars: int = 4,
    cost_per_unit_turnover: float = 0.0,
) -> pd.DataFrame:
    result = run_manual_barrier_backtest(
        frame,
        signal_col="signal",
        take_profit_r=take_profit_r,
        stop_loss_r=stop_loss_r,
        risk_per_trade=0.01,
        max_holding_bars=max_holding_bars,
        cost_per_unit_turnover=cost_per_unit_turnover,
        dynamic_exits=dynamic_exits,
        partial_exits=partial_exits,
        allow_short=True,
        forecast_col="forecast" if dynamic_exits else None,
    )
    assert result.trades is not None
    return result.trades


def test_forecast_decay_exit_uses_next_open_timing_without_same_bar_execution() -> None:
    frame = _frame(
        opens=[100.0, 100.0, 101.0, 101.0],
        highs=[100.0, 101.0, 102.0, 102.0],
        lows=[100.0, 99.0, 100.5, 100.5],
        closes=[100.0, 99.5, 101.0, 101.0],
        signals=[1.0, 0.0, 0.0, 0.0],
        forecasts=[0.8, 0.05, 0.05, 0.05],
    )

    trades = _run(frame, dynamic_exits=_forecast_decay())

    trade = trades.iloc[0]
    assert trade["exit_reason"] == "forecast_decay_exit"
    assert trade["exit_timestamp"] == frame.index[2]
    assert trade["raw_exit_price"] == pytest.approx(101.0)
    assert trade["raw_exit_price"] != pytest.approx(frame.loc[frame.index[1], "close"])


def test_forecast_decay_long_exit_condition_waits_for_threshold_cross() -> None:
    frame = _frame(
        opens=[100.0, 100.0, 100.5, 101.0, 101.0],
        highs=[100.0, 101.0, 101.0, 101.5, 101.5],
        lows=[100.0, 99.5, 100.0, 100.5, 100.5],
        closes=[100.0, 100.5, 100.8, 101.0, 101.0],
        signals=[1.0, 0.0, 0.0, 0.0, 0.0],
        forecasts=[0.8, 0.20, 0.05, 0.05, 0.05],
    )

    trades = _run(frame, dynamic_exits=_forecast_decay(long_exit=0.10), max_holding_bars=4)

    assert trades.iloc[0]["exit_reason"] == "forecast_decay_exit"
    assert trades.iloc[0]["exit_timestamp"] == frame.index[3]


def test_forecast_decay_short_exit_condition_waits_for_threshold_cross() -> None:
    frame = _frame(
        opens=[100.0, 100.0, 99.5, 99.0, 99.0],
        highs=[100.0, 100.5, 100.0, 99.5, 99.5],
        lows=[100.0, 99.0, 99.0, 98.5, 98.5],
        closes=[100.0, 99.5, 99.2, 99.0, 99.0],
        signals=[-1.0, 0.0, 0.0, 0.0, 0.0],
        forecasts=[-1.0, -0.20, -0.05, -0.05, -0.05],
    )

    trades = _run(frame, dynamic_exits=_forecast_decay(short_exit=-0.10), max_holding_bars=4)

    assert trades.iloc[0]["side"] == "short"
    assert trades.iloc[0]["exit_reason"] == "forecast_decay_exit"
    assert trades.iloc[0]["exit_timestamp"] == frame.index[3]


def test_tp_sl_same_bar_uses_conservative_stop_priority() -> None:
    frame = _frame(
        opens=[100.0, 100.0, 100.0],
        highs=[100.0, 101.5, 100.0],
        lows=[100.0, 98.5, 100.0],
        closes=[100.0, 100.0, 100.0],
        signals=[1.0, 0.0, 0.0],
    )

    trades = _run(frame, take_profit_r=1.0, stop_loss_r=1.0, max_holding_bars=2)

    assert trades.iloc[0]["exit_reason"] == "stop_and_target_same_bar_stop_first"
    assert trades.iloc[0]["raw_exit_price"] == pytest.approx(99.0)


def test_barrier_exit_takes_priority_over_dynamic_exit() -> None:
    frame = _frame(
        opens=[100.0, 100.0, 101.0, 101.0],
        highs=[100.0, 101.5, 101.5, 101.5],
        lows=[100.0, 99.8, 100.5, 100.5],
        closes=[100.0, 100.5, 101.0, 101.0],
        signals=[1.0, 0.0, 0.0, 0.0],
        forecasts=[0.8, 0.00, 0.00, 0.00],
    )

    trades = _run(
        frame,
        dynamic_exits=_forecast_decay(long_exit=0.10),
        take_profit_r=1.0,
        stop_loss_r=10.0,
        max_holding_bars=3,
    )

    assert trades.iloc[0]["exit_reason"] == "take_profit"
    assert trades.iloc[0]["exit_timestamp"] == frame.index[1]
    assert trades.iloc[0]["raw_exit_price"] == pytest.approx(101.0)


def test_partial_exit_accounting_and_costs_after_partial_exits() -> None:
    frame = _frame(
        opens=[100.0, 100.0, 101.0, 102.0],
        highs=[100.0, 101.2, 101.5, 102.0],
        lows=[100.0, 99.8, 100.5, 101.5],
        closes=[100.0, 100.8, 101.5, 102.0],
        signals=[1.0, 0.0, 0.0, 0.0],
    )
    result = run_manual_barrier_backtest(
        frame,
        signal_col="signal",
        take_profit_r=5.0,
        stop_loss_r=1.0,
        risk_per_trade=0.01,
        max_holding_bars=3,
        cost_per_unit_turnover=0.001,
        partial_exits={"enabled": True, "rules": [{"trigger_r": 1.0, "fraction": 0.5}]},
        allow_short=True,
    )

    assert result.trades is not None
    trade = result.trades.iloc[0]
    assert trade["partial_exit_count"] == 1
    assert trade["partial_exit_fraction_total"] == pytest.approx(0.5)
    assert trade["gross_return"] == pytest.approx(0.015)
    assert trade["cost_paid"] == pytest.approx(0.002)
    assert result.costs.sum() == pytest.approx(0.002)
    assert result.turnover.sum() == pytest.approx(2.0)
    assert trade["trade_r"] == pytest.approx(1.3)


def test_max_holding_period_is_enforced() -> None:
    frame = _frame(
        opens=[100.0, 100.0, 100.2, 100.4],
        highs=[100.0, 100.5, 100.6, 100.8],
        lows=[100.0, 99.8, 99.9, 100.0],
        closes=[100.0, 100.2, 100.4, 100.6],
        signals=[1.0, 0.0, 0.0, 0.0],
    )

    trades = _run(frame, max_holding_bars=2)

    assert trades.iloc[0]["exit_reason"] == "max_holding_close"
    assert trades.iloc[0]["exit_timestamp"] == frame.index[2]
    assert trades.iloc[0]["bars_held"] == 2


def test_dynamic_exit_backtest_is_reproducible() -> None:
    frame = _frame(
        opens=[100.0, 100.0, 100.5, 101.0, 101.0],
        highs=[100.0, 101.0, 101.0, 101.5, 101.5],
        lows=[100.0, 99.5, 100.0, 100.5, 100.5],
        closes=[100.0, 100.5, 100.8, 101.0, 101.0],
        signals=[1.0, 0.0, 0.0, 0.0, 0.0],
        forecasts=[0.8, 0.20, 0.05, 0.05, 0.05],
    )

    first = _run(frame, dynamic_exits=_forecast_decay(long_exit=0.10), max_holding_bars=4)
    second = _run(frame, dynamic_exits=_forecast_decay(long_exit=0.10), max_holding_bars=4)

    pd.testing.assert_frame_equal(first.reset_index(drop=True), second.reset_index(drop=True))
