from __future__ import annotations

import pandas as pd
import pytest

from src.backtesting.manual_barrier import run_manual_barrier_backtest


def _run(
    df: pd.DataFrame,
    *,
    dynamic_exits: dict | None = None,
    take_profit_r: float = 3.0,
    max_holding_bars: int = 12,
):
    return run_manual_barrier_backtest(
        df,
        signal_col="signal",
        take_profit_r=take_profit_r,
        stop_loss_r=1.0,
        risk_per_trade=0.01,
        max_holding_bars=max_holding_bars,
        cost_per_unit_turnover=0.0,
        slippage_per_unit_turnover=0.0,
        periods_per_year=48,
        dynamic_exits=dynamic_exits,
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
    assert trade["raw_exit_price"] == pytest.approx(100.3)
    assert trade["trade_r"] == pytest.approx(0.3)
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
