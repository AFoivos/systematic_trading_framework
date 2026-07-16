from __future__ import annotations

import pandas as pd

from src.backtesting.portfolio_barrier import run_portfolio_barrier_backtest


def _frame(index: pd.DatetimeIndex, *, signals: list[int]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [100.0] * len(index),
            "high": [101.0] * len(index),
            "low": [99.0] * len(index),
            "close": [100.0] * len(index),
            "atr_14": [1.0] * len(index),
            "signal": signals,
            "bid_open": [100.0] * len(index),
            "ask_open": [100.1] * len(index),
        },
        index=index,
    )


def test_portfolio_barrier_rejects_entry_above_asset_spread_limit() -> None:
    index = pd.date_range("2026-06-15", periods=4, freq="30min", tz="UTC")
    frame = _frame(index, signals=[1, 0, 0, 0])
    frame.loc[index[1], "ask_open"] = 100.8

    performance, _, _, meta = run_portfolio_barrier_backtest(
        {"SPX500": frame},
        signal_col="signal",
        vertical_barrier_bars=2,
        asset_params={
            "SPX500": {
                "volatility_col": "atr_14",
                "point_size": 0.01,
                "max_spread_points": 70,
                "spread_bid_col": "bid_open",
                "spread_ask_col": "ask_open",
            }
        },
    )

    assert performance.trades is not None
    assert performance.trades.empty
    assert meta["skipped_spread_filter"] == 1


def test_portfolio_barrier_executes_observed_bid_ask_spread() -> None:
    index = pd.date_range("2026-06-15", periods=4, freq="30min", tz="UTC")
    narrow = _frame(index, signals=[1, 0, 0, 0])
    wide = narrow.copy()
    narrow.loc[index[1], "low"] = 100.0
    wide.loc[index[1], "low"] = 100.0
    narrow[["bid_open", "ask_open"]] = [99.9, 100.1]
    wide[["bid_open", "ask_open"]] = [99.8, 100.2]
    params = {
        "SPX500": {
            "volatility_col": "atr_14",
            "point_size": 0.01,
            "max_spread_points": 50,
            "spread_bid_col": "bid_open",
            "spread_ask_col": "ask_open",
        }
    }

    narrow_result, _, _, _ = run_portfolio_barrier_backtest(
        {"SPX500": narrow},
        signal_col="signal",
        profit_barrier_r=1.0,
        stop_barrier_r=2.0,
        vertical_barrier_bars=2,
        asset_params=params,
    )
    wide_result, _, _, _ = run_portfolio_barrier_backtest(
        {"SPX500": wide},
        signal_col="signal",
        profit_barrier_r=1.0,
        stop_barrier_r=2.0,
        vertical_barrier_bars=2,
        asset_params=params,
    )

    narrow_trade = narrow_result.trades.iloc[0]
    wide_trade = wide_result.trades.iloc[0]
    assert narrow_trade["entry_price"] == 100.1
    assert narrow_trade["exit_price"] == 100.9
    assert wide_trade["net_return"] < narrow_trade["net_return"]
    assert wide_trade["observed_spread_cost"] > narrow_trade["observed_spread_cost"]


def test_portfolio_barrier_daily_loss_blocks_only_current_day() -> None:
    index = pd.DatetimeIndex(
        [
            "2026-06-15T00:00:00Z",
            "2026-06-15T00:30:00Z",
            "2026-06-16T00:00:00Z",
            "2026-06-16T00:30:00Z",
        ]
    )
    frame = _frame(index, signals=[1, 1, 1, 0])
    frame.loc[index[1], "low"] = 98.0
    frame.loc[index[3], "high"] = 102.0
    frame.loc[index[3], "low"] = 100.0

    performance, _, _, meta = run_portfolio_barrier_backtest(
        {"SPX500": frame},
        signal_col="signal",
        profit_barrier_r=1.0,
        stop_barrier_r=1.0,
        vertical_barrier_bars=1,
        portfolio_guard={
            "enabled": True,
            "max_daily_loss_pct": 0.005,
            "equity_source": "mark_to_market",
        },
    )

    assert performance.trades is not None
    assert len(performance.trades.index) == 2
    assert meta["skipped_daily_loss"] == 1
    assert meta["daily_loss_trigger_count"] == 1


def test_portfolio_barrier_weekend_gate_skips_weekend_signal() -> None:
    index = pd.DatetimeIndex(
        [
            "2026-06-13T00:00:00Z",
            "2026-06-13T00:30:00Z",
            "2026-06-15T00:00:00Z",
            "2026-06-15T00:30:00Z",
        ]
    )
    frame = _frame(index, signals=[1, 0, 1, 0])

    performance, _, _, meta = run_portfolio_barrier_backtest(
        {"ETHUSD": frame},
        signal_col="signal",
        vertical_barrier_bars=1,
        portfolio_guard={"enabled": True, "disable_weekend_trading": True},
    )

    assert performance.trades is not None
    assert len(performance.trades.index) == 1
    assert meta["skipped_weekend"] == 1
