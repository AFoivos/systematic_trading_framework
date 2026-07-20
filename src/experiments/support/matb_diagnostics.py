from __future__ import annotations

"""Synthetic parity diagnostics for the shared MATB target/backtest path."""

from collections.abc import Callable

import pandas as pd

from src.backtesting.portfolio_barrier import run_portfolio_barrier_backtest
from src.targets.strategy_path_r import build_strategy_path_r_target


def _base_path(side: int) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=8, freq="30min", tz="UTC")
    return pd.DataFrame(
        {
            "open": 100.0,
            "high": 100.5,
            "low": 99.5,
            "close": 100.0,
            "bid_open": 99.9,
            "bid_high": 100.4,
            "bid_low": 99.4,
            "bid_close": 99.9,
            "ask_open": 100.1,
            "ask_high": 100.6,
            "ask_low": 99.6,
            "ask_close": 100.1,
            "matb_atr": 1.0,
            "matb_trend_score": 1.0 if side > 0 else -1.0,
            "matb_candidate": [1] + [0] * 7,
            "matb_side": [side] + [0] * 7,
            "signal": [float(side)] + [0.0] * 7,
        },
        index=index,
    )


def _set_long_stop(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[1], "bid_low"] = 97.5


def _set_short_stop(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[1], "ask_high"] = 102.5


def _set_long_trailing(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[1], ["bid_high", "bid_low", "bid_close"]] = [104.0, 99.0, 103.0]
    frame.loc[frame.index[2], ["bid_open", "bid_high", "bid_low", "bid_close"]] = [103.0, 103.2, 101.4, 101.6]


def _set_short_trailing(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[1], ["ask_high", "ask_low", "ask_close"]] = [100.5, 96.0, 97.0]
    frame.loc[frame.index[2], ["ask_open", "ask_high", "ask_low", "ask_close"]] = [97.0, 98.6, 96.8, 98.4]


def _set_trend_flip(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[1], "matb_trend_score"] = 0.0
    frame.loc[frame.index[2], "bid_open"] = 101.0


def _set_max_holding(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[2], "bid_close"] = 101.1


def _set_emergency(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[1], "bid_high"] = 117.0


def _set_gap_stop(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[2], ["bid_open", "bid_high", "bid_low", "bid_close"]] = [97.0, 97.5, 96.5, 97.0]


def _set_tie(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[1], ["bid_open", "bid_high", "bid_low"]] = [100.0, 117.0, 97.0]


def _set_cost_only(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[1], "bid_low"] = 97.5


def build_target_backtest_parity_diagnostics(*, tolerance: float = 1e-12) -> pd.DataFrame:
    scenarios: list[tuple[str, int, Callable[[pd.DataFrame], None], int]] = [
        ("long_stop", 1, _set_long_stop, 4),
        ("short_stop", -1, _set_short_stop, 4),
        ("long_trailing", 1, _set_long_trailing, 4),
        ("short_trailing", -1, _set_short_trailing, 4),
        ("trend_flip", 1, _set_trend_flip, 4),
        ("max_holding", 1, _set_max_holding, 2),
        ("emergency_profit", 1, _set_emergency, 4),
        ("bid_ask_costs", 1, _set_cost_only, 4),
        ("gap_through_stop", 1, _set_gap_stop, 4),
        ("same_bar_tie", 1, _set_tie, 4),
    ]
    rows: list[dict[str, object]] = []
    for name, side, mutate, max_holding in scenarios:
        frame = _base_path(side)
        mutate(frame)
        target_cfg = {
            "max_holding_bars": max_holding,
            "cost_per_unit_turnover": 0.0003,
            "slippage_per_unit_turnover": 0.0002,
        }
        target, _, _, _ = build_strategy_path_r_target(frame, target_cfg)
        performance, _, _, _ = run_portfolio_barrier_backtest(
            {"asset": frame},
            signal_col="signal",
            volatility_col="matb_atr",
            cost_per_turnover=0.0003,
            slippage_per_turnover=0.0002,
            strategy_path={"kind": "matb", "max_holding_bars": max_holding},
        )
        trade = performance.trades.iloc[0]
        target_r = float(target["matb_net_trade_r"].iloc[0])
        backtest_r = float(trade["realized_r"])
        absolute_error = abs(target_r - backtest_r)
        rows.append(
            {
                "scenario": name,
                "side": "long" if side > 0 else "short",
                "target_net_r": target_r,
                "backtest_net_r": backtest_r,
                "absolute_error": absolute_error,
                "tolerance": float(tolerance),
                "passed": bool(absolute_error <= float(tolerance)),
                "target_exit_reason": target["matb_exit_reason"].iloc[0],
                "backtest_exit_reason": trade["exit_reason"],
                "execution_source": trade["execution_source"],
            }
        )
    return pd.DataFrame(rows)


__all__ = ["build_target_backtest_parity_diagnostics"]
