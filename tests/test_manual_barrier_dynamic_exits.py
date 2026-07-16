from __future__ import annotations

import pandas as pd
import pytest

from src.backtesting.manual_barrier import run_manual_barrier_backtest


def _run(
    df: pd.DataFrame,
    *,
    dynamic_exits: dict | None = None,
    partial_exits: dict | None = None,
    take_profit_r: float = 3.0,
    stop_loss_r: float = 1.0,
    max_holding_bars: int = 12,
    allow_short: bool = False,
    cost_per_unit_turnover: float = 0.0,
):
    return run_manual_barrier_backtest(
        df,
        signal_col="signal",
        take_profit_r=take_profit_r,
        stop_loss_r=stop_loss_r,
        risk_per_trade=0.01,
        max_holding_bars=max_holding_bars,
        cost_per_unit_turnover=cost_per_unit_turnover,
        slippage_per_unit_turnover=0.0,
        periods_per_year=48,
        dynamic_exits=dynamic_exits,
        partial_exits=partial_exits,
        allow_short=allow_short,
    )


def _frame(rows: int, *, signal: list[float] | None = None) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01 09:00", periods=rows, freq="30min")
    values = {
        "signal": signal if signal is not None else [1.0] * rows,
        "open": [100.0] * rows,
        "high": [100.1] * rows,
        "low": [99.5] * rows,
        "close": [100.0] * rows,
    }
    return pd.DataFrame(values, index=idx)


def test_manual_barrier_dynamic_signal_off_exits_next_open() -> None:
    df = _frame(5, signal=[1.0, 0.0, 0.0, 0.0, 0.0])
    df.loc[df.index[2], "open"] = 100.4

    result = _run(
        df,
        dynamic_exits={
            "enabled": True,
            "signal_off_exit": {"enabled": True, "min_bars_held": 1, "exit_price": "next_open"},
        },
    )

    trade = result.trades.iloc[0]
    assert trade["exit_timestamp"] == df.index[2]
    assert trade["raw_exit_price"] == pytest.approx(100.4)
    assert trade["exit_reason"] == "signal_off_exit"


def test_manual_barrier_dynamic_breakeven_stop() -> None:
    df = _frame(5)
    df.loc[df.index[1], ["high", "low", "close"]] = [100.85, 100.2, 100.4]
    df.loc[df.index[2], ["high", "low", "close"]] = [100.4, 100.0, 100.1]

    result = _run(
        df,
        dynamic_exits={
            "enabled": True,
            "breakeven": {"enabled": True, "trigger_r": 0.8, "lock_r": 0.0},
        },
    )

    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "breakeven_stop"
    assert trade["raw_exit_price"] == pytest.approx(100.0)
    assert trade["trade_r"] == pytest.approx(0.0)
    assert bool(trade["breakeven_activated"]) is True


def test_dynamic_stop_tightening_never_reprices_a_same_bar_stop() -> None:
    df = _frame(4, signal=[1.0, 0.0, 0.0, 0.0])
    df.loc[df.index[1], ["open", "high", "low", "close"]] = [100.0, 101.2, 98.0, 100.0]

    result = _run(
        df,
        dynamic_exits={
            "enabled": True,
            "breakeven": {"enabled": True, "trigger_r": 1.0, "lock_r": 0.0},
        },
    )

    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "stop_loss"
    assert trade["raw_exit_price"] == pytest.approx(99.0)
    assert bool(trade["breakeven_activated"]) is False


def test_short_dynamic_stop_tightening_never_reprices_a_same_bar_stop() -> None:
    df = _frame(4, signal=[-1.0, 0.0, 0.0, 0.0])
    df.loc[df.index[1], ["open", "high", "low", "close"]] = [100.0, 102.0, 98.8, 100.0]

    result = _run(
        df,
        dynamic_exits={
            "enabled": True,
            "breakeven": {"enabled": True, "trigger_r": 1.0, "lock_r": 0.0},
        },
        allow_short=True,
    )

    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "stop_loss"
    assert trade["raw_exit_price"] == pytest.approx(101.0)
    assert bool(trade["breakeven_activated"]) is False


def test_gap_through_stop_fills_at_executable_open() -> None:
    df = _frame(4, signal=[1.0, 0.0, 0.0, 0.0])
    df.loc[df.index[2], ["open", "high", "low", "close"]] = [90.0, 91.0, 89.0, 90.0]

    result = _run(df)

    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "stop_loss"
    assert trade["raw_exit_price"] == pytest.approx(90.0)


def test_gap_through_take_profit_receives_open_price_improvement() -> None:
    df = _frame(4, signal=[1.0, 0.0, 0.0, 0.0])
    df.loc[df.index[2], ["open", "high", "low", "close"]] = [102.0, 103.0, 101.5, 102.5]

    result = _run(df, take_profit_r=1.0)

    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "take_profit"
    assert trade["raw_exit_price"] == pytest.approx(102.0)


def test_manual_barrier_dynamic_profit_lock_stop() -> None:
    df = _frame(5)
    df.loc[df.index[1], ["high", "low", "close"]] = [101.25, 100.5, 100.9]
    df.loc[df.index[2], ["high", "low", "close"]] = [100.8, 100.3, 100.4]

    result = _run(
        df,
        dynamic_exits={
            "enabled": True,
            "profit_lock": {"enabled": True, "trigger_r": 1.2, "lock_r": 0.3},
        },
    )

    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "profit_lock_stop"
    assert trade["raw_exit_price"] == pytest.approx(100.0)
    assert trade["trade_r"] == pytest.approx(0.0)
    assert bool(trade["profit_lock_activated"]) is True
    assert trade["effective_stop_price"] == pytest.approx(100.3)


def test_manual_barrier_dynamic_no_progress_exit() -> None:
    df = _frame(10)
    df.loc[df.index[1:7], "high"] = 100.1
    df.loc[df.index[1:7], "low"] = 99.6
    df.loc[df.index[6], "close"] = 100.05

    result = _run(
        df,
        dynamic_exits={
            "enabled": True,
            "no_progress": {"enabled": True, "bars": 6, "min_favorable_r": 0.2, "exit_price": "close"},
        },
    )

    trade = result.trades.iloc[0]
    assert trade["exit_timestamp"] == df.index[6]
    assert trade["exit_reason"] == "no_progress_exit"
    assert trade["bars_held"] == 6
    assert trade["max_favorable_r"] < 0.2


def test_manual_barrier_dynamic_disabled_preserves_legacy_behavior() -> None:
    df = _frame(5)
    df.loc[df.index[1], ["high", "low", "close"]] = [101.5, 99.8, 101.0]

    legacy = _run(df, take_profit_r=1.0, max_holding_bars=3)
    disabled = _run(
        df,
        take_profit_r=1.0,
        max_holding_bars=3,
        dynamic_exits={"enabled": False, "signal_off_exit": {"exit_price": "ignored_when_disabled"}},
    )

    pd.testing.assert_series_equal(legacy.returns, disabled.returns)
    pd.testing.assert_series_equal(legacy.positions, disabled.positions)
    legacy_trade = legacy.trades.iloc[0]
    disabled_trade = disabled.trades.iloc[0]
    for col in [
        "signal_timestamp",
        "entry_timestamp",
        "exit_timestamp",
        "entry_price",
        "exit_price",
        "raw_entry_price",
        "raw_exit_price",
        "take_profit_price",
        "stop_loss_price",
        "trade_r",
        "exit_reason",
    ]:
        assert disabled_trade[col] == legacy_trade[col]


def test_manual_barrier_partial_absent_and_disabled_preserve_legacy_behavior() -> None:
    df = _frame(5)
    df.loc[df.index[1], ["high", "low", "close"]] = [101.5, 99.8, 101.0]

    legacy = _run(df, take_profit_r=1.0, max_holding_bars=3)
    disabled = _run(
        df,
        take_profit_r=1.0,
        max_holding_bars=3,
        partial_exits={"enabled": False, "rules": [{"trigger_r": 0.5, "fraction": 0.5}]},
    )

    pd.testing.assert_series_equal(legacy.returns, disabled.returns)
    pd.testing.assert_series_equal(legacy.gross_returns, disabled.gross_returns)
    pd.testing.assert_series_equal(legacy.costs, disabled.costs)
    pd.testing.assert_series_equal(legacy.positions, disabled.positions)
    pd.testing.assert_series_equal(legacy.turnover, disabled.turnover)
    pd.testing.assert_frame_equal(legacy.trades, disabled.trades)


def test_same_bar_round_trip_reports_both_turnover_legs() -> None:
    df = _frame(3, signal=[1.0, 0.0, 0.0])
    df.loc[df.index[1], ["high", "low", "close"]] = [101.2, 99.5, 101.0]

    result = _run(df, take_profit_r=1.0, max_holding_bars=2)

    assert result.trades.iloc[0]["entry_timestamp"] == result.trades.iloc[0]["exit_timestamp"]
    assert result.turnover.sum() == pytest.approx(2.0)


def test_exit_bar_signal_can_schedule_the_next_open_entry() -> None:
    df = _frame(4, signal=[1.0, 1.0, 0.0, 0.0])
    df.loc[df.index[1], ["high", "low", "close"]] = [101.2, 99.5, 101.0]
    df.loc[df.index[2], ["high", "low", "close"]] = [101.2, 99.5, 101.0]

    result = _run(df, take_profit_r=1.0, max_holding_bars=2)

    assert len(result.trades) == 2
    assert result.trades.iloc[1]["signal_timestamp"] == df.index[1]
    assert result.trades.iloc[1]["entry_timestamp"] == df.index[2]


def test_primary_manual_equity_uses_open_trade_mark_to_market() -> None:
    df = _frame(5, signal=[1.0, 0.0, 0.0, 0.0, 0.0])
    df.loc[df.index[1], ["high", "low", "close"]] = [100.1, 95.0, 95.0]
    df.loc[df.index[2], ["high", "low", "close"]] = [100.1, 94.0, 100.0]

    result = _run(
        df,
        take_profit_r=10.0,
        stop_loss_r=10.0,
        max_holding_bars=3,
    )

    assert result.realized_summary is not None
    assert result.summary["equity_source"] == "mark_to_market"
    assert result.summary["max_drawdown"] < result.realized_summary["max_drawdown"]


def test_manual_barrier_partial_long_then_take_profit_weights_returns_and_costs() -> None:
    df = _frame(5, signal=[1.0, 0.0, 0.0, 0.0, 0.0])
    df.loc[df.index[1], ["high", "low", "close"]] = [100.6, 100.0, 100.4]
    df.loc[df.index[2], ["high", "low", "close"]] = [102.2, 100.8, 102.0]

    result = _run(
        df,
        take_profit_r=2.0,
        max_holding_bars=4,
        cost_per_unit_turnover=0.001,
        partial_exits={"enabled": True, "rules": [{"trigger_r": 0.5, "fraction": 0.5, "exit_price": "trigger"}]},
    )

    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "take_profit"
    assert trade["partial_exit_count"] == 1
    assert trade["partial_exit_fraction_total"] == pytest.approx(0.5)
    assert trade["remaining_fraction"] == pytest.approx(0.5)
    assert trade["partial_exit_realized_r"] == pytest.approx(0.25)
    assert trade["gross_return"] == pytest.approx(0.0125)
    assert trade["cost_paid"] == pytest.approx(0.002)
    assert trade["net_return"] == pytest.approx(0.0105)
    assert trade["trade_r"] == pytest.approx(1.05)
    assert result.turnover.sum() == pytest.approx(2.0)
    assert result.costs.sum() == pytest.approx(0.002)
    assert result.realized_gross_returns is not None
    assert result.realized_gross_returns.sum() == pytest.approx(0.0125)


def test_manual_barrier_partial_long_then_stop_reduces_loss_and_keeps_stop_reason() -> None:
    df = _frame(5, signal=[1.0, 0.0, 0.0, 0.0, 0.0])
    df.loc[df.index[1], ["high", "low", "close"]] = [100.6, 100.0, 100.4]
    df.loc[df.index[2], ["high", "low", "close"]] = [100.2, 98.8, 99.0]

    result = _run(
        df,
        take_profit_r=2.0,
        max_holding_bars=4,
        partial_exits={"enabled": True, "rules": [{"trigger_r": 0.5, "fraction": 0.5, "exit_price": "trigger"}]},
    )

    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "stop_loss"
    assert trade["partial_exit_count"] == 1
    assert trade["gross_return"] == pytest.approx(-0.0025)
    assert trade["trade_r"] == pytest.approx(-0.25)
    assert trade["trade_r"] > -1.0


def test_manual_barrier_partial_same_bar_stop_trigger_is_stop_first() -> None:
    df = _frame(4, signal=[1.0, 0.0, 0.0, 0.0])
    df.loc[df.index[1], ["high", "low", "close"]] = [100.6, 98.9, 99.2]

    result = _run(
        df,
        take_profit_r=2.0,
        max_holding_bars=3,
        partial_exits={"enabled": True, "rules": [{"trigger_r": 0.5, "fraction": 0.5, "exit_price": "trigger"}]},
    )

    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "stop_loss"
    assert "partial_exit_count" not in result.trades.columns
    assert trade["trade_r"] == pytest.approx(-1.0)


def test_manual_barrier_dynamic_exits_never_create_short_or_flip() -> None:
    df = _frame(8, signal=[1.0, -1.0, -1.0, 0.0, 1.0, -1.0, 0.0, 0.0])

    result = _run(
        df,
        dynamic_exits={
            "enabled": True,
            "signal_off_exit": {"enabled": True, "min_bars_held": 1, "exit_price": "next_open"},
            "no_progress": {"enabled": True, "bars": 4, "min_favorable_r": 0.2, "exit_price": "close"},
        },
    )

    assert bool(result.positions.ge(0.0).all())
    assert set(result.trades["side"]) == {"long"}


def test_manual_barrier_short_signal_off_exit_works_when_enabled() -> None:
    df = _frame(5, signal=[-1.0, -1.0, 0.0, 0.0, 0.0])
    df.loc[df.index[1], ["open", "high", "low", "close"]] = [100.0, 100.2, 99.4, 99.8]
    df.loc[df.index[2], "open"] = 99.6

    result = _run(
        df,
        dynamic_exits={
            "enabled": True,
            "signal_off_exit": {"enabled": True, "min_bars_held": 1, "exit_price": "next_open"},
        },
        allow_short=True,
    )

    trade = result.trades.iloc[0]
    assert trade["side"] == "short"
    assert trade["entry_timestamp"] == df.index[1]
    assert trade["exit_timestamp"] == df.index[3]
    assert trade["raw_exit_price"] == pytest.approx(100.0)
    assert trade["exit_reason"] == "signal_off_exit"
    assert result.positions.loc[df.index[1]] == pytest.approx(-1.0)


def test_manual_barrier_short_take_profit_records_positive_return() -> None:
    df = _frame(4, signal=[-1.0, 0.0, 0.0, 0.0])
    df.loc[df.index[1], ["open", "high", "low", "close"]] = [100.0, 100.2, 98.8, 99.1]

    result = _run(
        df,
        take_profit_r=1.0,
        max_holding_bars=3,
        allow_short=True,
    )

    trade = result.trades.iloc[0]
    assert trade["side"] == "short"
    assert trade["take_profit_price"] == pytest.approx(99.0)
    assert trade["stop_loss_price"] == pytest.approx(101.0)
    assert trade["exit_reason"] == "take_profit"
    assert trade["trade_r"] == pytest.approx(1.0)
    assert result.returns.loc[df.index[1]] == pytest.approx(0.01)


def test_manual_barrier_short_partial_then_take_profit_weights_returns() -> None:
    df = _frame(5, signal=[-1.0, 0.0, 0.0, 0.0, 0.0])
    df.loc[df.index[1], ["open", "high", "low", "close"]] = [100.0, 100.1, 99.4, 99.6]
    df.loc[df.index[2], ["high", "low", "close"]] = [99.2, 97.8, 98.0]

    result = _run(
        df,
        take_profit_r=2.0,
        max_holding_bars=4,
        allow_short=True,
        partial_exits={"enabled": True, "rules": [{"trigger_r": 0.5, "fraction": 0.5, "exit_price": "trigger"}]},
    )

    trade = result.trades.iloc[0]
    assert trade["side"] == "short"
    assert trade["exit_reason"] == "take_profit"
    assert trade["partial_exit_count"] == 1
    assert trade["gross_return"] == pytest.approx(0.0125)
    assert trade["trade_r"] == pytest.approx(1.25)
