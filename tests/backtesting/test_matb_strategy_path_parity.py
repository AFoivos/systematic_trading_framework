from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import pytest

from src.backtesting.portfolio_barrier import run_portfolio_barrier_backtest
from src.targets.strategy_path_r import build_strategy_path_r_target


def _frame(*, side: int, periods: int = 8) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=periods, freq="30min", tz="UTC")
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
            "matb_candidate": [1] + [0] * (periods - 1),
            "matb_side": [side] + [0] * (periods - 1),
            "signal": [float(side)] + [0.0] * (periods - 1),
        },
        index=index,
    )


def _long_stop(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[1], "bid_low"] = 97.5


def _short_stop(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[1], "ask_high"] = 102.5


def _long_trailing(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[1], ["bid_high", "bid_low", "bid_close"]] = [104.0, 99.0, 103.0]
    frame.loc[frame.index[2], ["bid_open", "bid_high", "bid_low", "bid_close"]] = [
        103.0,
        103.2,
        101.4,
        101.6,
    ]


def _short_trailing(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[1], ["ask_high", "ask_low", "ask_close"]] = [100.5, 96.0, 97.0]
    frame.loc[frame.index[2], ["ask_open", "ask_high", "ask_low", "ask_close"]] = [
        97.0,
        98.6,
        96.8,
        98.4,
    ]


def _trend_flip(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[1], "matb_trend_score"] = 0.0
    frame.loc[frame.index[2], "bid_open"] = 101.0


def _max_holding(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[2], "bid_close"] = 101.1


def _emergency(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[1], "bid_high"] = 117.0


def _gap_stop(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[2], ["bid_open", "bid_high", "bid_low", "bid_close"]] = [
        97.0,
        97.5,
        96.5,
        97.0,
    ]


def _same_bar_tie(frame: pd.DataFrame) -> None:
    frame.loc[frame.index[1], ["bid_open", "bid_high", "bid_low"]] = [100.0, 117.0, 97.0]


@pytest.mark.parametrize(
    ("side", "mutate", "max_holding_bars"),
    [
        (1, _long_stop, 4),
        (-1, _short_stop, 4),
        (1, _long_trailing, 4),
        (-1, _short_trailing, 4),
        (1, _trend_flip, 4),
        (1, _max_holding, 2),
        (1, _emergency, 4),
        (1, _gap_stop, 4),
        (1, _same_bar_tie, 4),
    ],
    ids=[
        "long-stop",
        "short-stop",
        "long-trailing",
        "short-trailing",
        "trend-flip",
        "max-holding",
        "emergency-profit",
        "gap-through-stop",
        "same-bar-tie",
    ],
)
def test_strategy_path_target_and_portfolio_r_are_identical(
    side: int,
    mutate: Callable[[pd.DataFrame], None],
    max_holding_bars: int,
) -> None:
    frame = _frame(side=side)
    mutate(frame)
    path = {
        "entry_price_mode": "next_open",
        "stop_loss_r": 2.0,
        "emergency_profit_r": 8.0,
        "trailing_activation_r": 1.5,
        "trailing_distance_atr": 2.5,
        "max_holding_bars": max_holding_bars,
        "tie_break": "closest_to_open",
        "strict_bid_ask": True,
        "allow_partial_horizon": False,
        "cost_per_unit_turnover": 0.0003,
        "slippage_per_unit_turnover": 0.0002,
    }
    target, _, _, _ = build_strategy_path_r_target(frame, path)
    performance, _, _, _ = run_portfolio_barrier_backtest(
        {"asset": frame},
        signal_col="signal",
        volatility_col="matb_atr",
        entry_price_mode="next_open",
        cost_per_turnover=0.0003,
        slippage_per_turnover=0.0002,
        strategy_path={"kind": "matb", **path},
    )

    assert len(performance.trades) == 1
    trade = performance.trades.iloc[0]
    assert float(trade["realized_r"]) == pytest.approx(
        float(target["matb_net_trade_r"].iloc[0]), abs=1e-12, rel=0.0
    )
    assert float(trade["entry_price"]) == float(target["matb_entry_price"].iloc[0])
    assert float(trade["exit_price"]) == float(target["matb_exit_price"].iloc[0])
    assert trade["exit_reason"] == target["matb_exit_reason"].iloc[0]
    assert trade["execution_source"] == target["matb_execution_source"].iloc[0]


def test_strategy_path_midpoint_fallback_is_identical_and_audited() -> None:
    frame = _frame(side=1).drop(
        columns=[
            "bid_open",
            "bid_high",
            "bid_low",
            "bid_close",
            "ask_open",
            "ask_high",
            "ask_low",
            "ask_close",
        ]
    )
    frame.loc[frame.index[1], "low"] = 97.5
    path = {"max_holding_bars": 4, "strict_bid_ask": True}
    target, _, _, _ = build_strategy_path_r_target(frame, path)
    performance, _, _, _ = run_portfolio_barrier_backtest(
        {"asset": frame},
        signal_col="signal",
        volatility_col="matb_atr",
        strategy_path={"kind": "matb", **path},
    )
    trade = performance.trades.iloc[0]
    assert trade["realized_r"] == pytest.approx(target["matb_net_trade_r"].iloc[0], abs=1e-12)
    assert trade["execution_source"] == "midpoint_fallback"
    assert not bool(trade["spread_embedded_in_gross_return"])
