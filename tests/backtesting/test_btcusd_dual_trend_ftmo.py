from __future__ import annotations

import pandas as pd
import pandas.testing as pdt
import pytest

from src.backtesting.btcusd_dual_trend_ftmo import run_btcusd_dual_trend_backtest
from src.evaluation.btcusd_dual_trend_ftmo import simulate_ftmo_phase, simulate_ftmo_two_step


def _backtest_frame() -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=3, freq="30min", tz="UTC")
    return pd.DataFrame(
        {
            "signal_position": [1.0, 1.0, 0.5],
            "dual_execution_return": [0.01, -0.01, 0.02],
        },
        index=index,
    )


def _ftmo_frame(index: pd.DatetimeIndex, returns: list[float], adverse: list[float] | None = None) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "dual_trend_score": 1.0,
            "dual_volatility_ann_336": 0.22,
            "dual_execution_return": returns,
            "dual_adverse_long_return": adverse or [0.0] * len(index),
            "dual_adverse_short_price_return": [0.0] * len(index),
        },
        index=index,
    )


def test_one_way_cost_is_four_bps_per_unit_turnover() -> None:
    result = run_btcusd_dual_trend_backtest(_backtest_frame(), liquidate_at_end=False)
    assert result.accounting["turnover"].tolist() == pytest.approx([1.0, 0.0, 0.5])
    assert result.accounting["cost_return"].tolist() == pytest.approx([0.0004, 0.0, 0.0002])


def test_forced_liquidation_charges_terminal_one_way_cost() -> None:
    result = run_btcusd_dual_trend_backtest(_backtest_frame(), liquidate_at_end=True)
    assert result.accounting["liquidation_turnover"].iloc[-1] == pytest.approx(0.5)
    assert result.accounting["cost_return"].iloc[-1] == pytest.approx(0.0004)
    assert result.accounting["ending_position"].iloc[-1] == 0.0
    assert result.metrics["exit_trade_cost"] == pytest.approx(0.0002)


def test_ftmo_phases_restart_from_normalized_equity() -> None:
    index = pd.date_range("2026-01-01", periods=12, freq="1D", tz="UTC")
    frame = _ftmo_frame(index, [0.03] * len(index))
    result = simulate_ftmo_two_step(
        frame,
        start=index[0],
        end_exclusive=index[-1] + pd.Timedelta(days=1),
        minimum_trading_days=4,
        cost_per_turnover=0.0,
    )
    assert result["status"] == "passed"
    assert result["phase1"]["ending_equity"] == pytest.approx(1.03**4)
    # Phase 2 starts again at 1.0 and applies its lower 16% target-vol sleeve.
    assert result["phase2"]["ending_equity"] == pytest.approx((1.0 + 0.03 * 0.16 / 0.22) ** 4)


def test_ftmo_daily_loss_resets_at_utc_midnight() -> None:
    index = pd.DatetimeIndex(
        [pd.Timestamp("2026-01-01 23:30", tz="UTC"), pd.Timestamp("2026-01-02 00:00", tz="UTC")]
    )
    frame = _ftmo_frame(index, [-0.04, -0.04])
    phase = simulate_ftmo_phase(
        frame,
        profit_target=0.50,
        target_volatility=0.22,
        max_leverage=1.0,
        cost_per_turnover=0.0,
    )
    assert phase.status == "incomplete"
    assert phase.worst_daily_loss == pytest.approx(-0.04)


def test_ftmo_intrabar_high_low_breach_fails_phase() -> None:
    index = pd.date_range("2026-01-01", periods=2, freq="30min", tz="UTC")
    frame = _ftmo_frame(index, [0.0, 0.0], adverse=[-0.06, 0.0])
    phase = simulate_ftmo_phase(
        frame,
        profit_target=0.50,
        target_volatility=0.22,
        max_leverage=1.0,
        cost_per_turnover=0.0,
    )
    assert phase.status == "failed"
    assert phase.failure_reason == "maximum_daily_loss"


def test_profit_target_requires_closing_cost_and_minimum_trading_days() -> None:
    one_day = pd.date_range("2026-01-01", periods=1, freq="1D", tz="UTC")
    below_after_close = _ftmo_frame(one_day, [0.1005])
    phase = simulate_ftmo_phase(
        below_after_close,
        profit_target=0.10,
        target_volatility=0.22,
        max_leverage=1.0,
        minimum_trading_days=1,
        cost_per_turnover=0.0004,
    )
    assert phase.status == "incomplete"

    index = pd.date_range("2026-01-01", periods=4, freq="1D", tz="UTC")
    target_early = _ftmo_frame(index, [0.11, 0.0, 0.0, 0.0])
    phase = simulate_ftmo_phase(
        target_early,
        profit_target=0.10,
        target_volatility=0.22,
        max_leverage=1.0,
        minimum_trading_days=4,
        cost_per_turnover=0.0,
    )
    assert phase.status == "passed"
    assert phase.completion_timestamp == index[-1]


def test_repeated_backtest_is_deterministic() -> None:
    first = run_btcusd_dual_trend_backtest(_backtest_frame())
    second = run_btcusd_dual_trend_backtest(_backtest_frame())
    pdt.assert_frame_equal(first.accounting, second.accounting)
    pdt.assert_frame_equal(first.trades, second.trades)
    assert first.metrics == second.metrics
