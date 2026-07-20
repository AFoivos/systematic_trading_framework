from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.targets.strategy_path_r import build_strategy_path_r_target


def _frame(periods: int = 8, *, side: int = 1) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=periods, freq="30min", tz="UTC")
    frame = pd.DataFrame(
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
            "matb_candidate": 0,
            "matb_side": 0,
        },
        index=index,
    )
    frame.iloc[0, frame.columns.get_loc("matb_candidate")] = 1
    frame.iloc[0, frame.columns.get_loc("matb_side")] = side
    return frame


def _target(frame: pd.DataFrame, **overrides: object) -> pd.DataFrame:
    config: dict[str, object] = {
        "candidate_col": "matb_candidate",
        "side_col": "matb_side",
        "volatility_col": "matb_atr",
        "trend_score_col": "matb_trend_score",
        "stop_loss_r": 2.0,
        "emergency_profit_r": 8.0,
        "trailing_activation_r": 1.5,
        "trailing_distance_atr": 2.5,
        "max_holding_bars": 4,
        "strict_bid_ask": True,
        "allow_partial_horizon": False,
    }
    config.update(overrides)
    out, _, _, _ = build_strategy_path_r_target(frame, config)
    return out


def test_strategy_path_long_stop_and_bid_ask_entry() -> None:
    frame = _frame(side=1)
    frame.loc[frame.index[1], "bid_low"] = 97.5
    out = _target(frame)

    assert out["matb_entry_price"].iloc[0] == pytest.approx(100.1)
    assert out["matb_exit_price"].iloc[0] == pytest.approx(98.1)
    assert out["matb_net_trade_r"].iloc[0] == pytest.approx(-1.0)
    assert out["matb_execution_source"].iloc[0] == "bid_ask"


def test_strategy_path_short_stop_and_bid_ask_entry() -> None:
    frame = _frame(side=-1)
    frame.loc[frame.index[1], "ask_high"] = 102.5
    out = _target(frame)

    assert out["matb_entry_price"].iloc[0] == pytest.approx(99.9)
    assert out["matb_exit_price"].iloc[0] == pytest.approx(101.9)
    assert out["matb_net_trade_r"].iloc[0] == pytest.approx(-1.0)


def test_strategy_path_long_dynamic_trailing_stop_is_monotone() -> None:
    frame = _frame(side=1)
    frame.loc[frame.index[1], ["bid_high", "bid_low", "bid_close"]] = [104.0, 99.0, 103.0]
    frame.loc[frame.index[2], ["bid_open", "bid_high", "bid_low", "bid_close"]] = [103.0, 103.2, 101.4, 101.6]
    out = _target(frame)

    assert out["matb_exit_reason"].iloc[0] == "trailing_stop"
    assert out["matb_exit_price"].iloc[0] == pytest.approx(101.5)
    assert out["matb_net_trade_r"].iloc[0] == pytest.approx(0.7)


def test_strategy_path_short_dynamic_trailing_stop_is_symmetric() -> None:
    frame = _frame(side=-1)
    frame.loc[frame.index[1], ["ask_high", "ask_low", "ask_close"]] = [100.5, 96.0, 97.0]
    frame.loc[frame.index[2], ["ask_open", "ask_high", "ask_low", "ask_close"]] = [97.0, 98.6, 96.8, 98.4]
    out = _target(frame)

    assert out["matb_exit_reason"].iloc[0] == "trailing_stop"
    assert out["matb_exit_price"].iloc[0] == pytest.approx(98.5)
    assert out["matb_net_trade_r"].iloc[0] == pytest.approx(0.7)


def test_strategy_path_trend_flip_executes_at_next_open() -> None:
    frame = _frame(side=1)
    frame.loc[frame.index[1], "matb_trend_score"] = 0.0
    frame.loc[frame.index[2], "bid_open"] = 101.0
    out = _target(frame)

    assert out["matb_exit_reason"].iloc[0] == "trend_flip_exit"
    assert out["matb_exit_timestamp"].iloc[0] == frame.index[2]
    assert out["matb_exit_price"].iloc[0] == pytest.approx(101.0)


def test_strategy_path_max_holding_exit() -> None:
    frame = _frame(side=1)
    frame.loc[frame.index[2], "bid_close"] = 101.1
    out = _target(frame, max_holding_bars=2)

    assert out["matb_exit_reason"].iloc[0] == "max_holding_exit"
    assert out["matb_bars_held"].iloc[0] == 2
    assert out["matb_exit_price"].iloc[0] == pytest.approx(101.1)


def test_strategy_path_emergency_profit_barrier() -> None:
    frame = _frame(side=1)
    frame.loc[frame.index[1], "bid_high"] = 117.0
    out = _target(frame)

    assert out["matb_exit_reason"].iloc[0] == "emergency_profit"
    assert out["matb_exit_price"].iloc[0] == pytest.approx(116.1)
    assert out["matb_net_trade_r"].iloc[0] == pytest.approx(8.0)


def test_strategy_path_gap_through_stop_uses_executable_open() -> None:
    frame = _frame(side=1)
    frame.loc[frame.index[2], ["bid_open", "bid_high", "bid_low", "bid_close"]] = [97.0, 97.5, 96.5, 97.0]
    out = _target(frame)

    assert out["matb_exit_reason"].iloc[0] == "stop_loss"
    assert out["matb_exit_price"].iloc[0] == pytest.approx(97.0)
    assert out["matb_net_trade_r"].iloc[0] < -1.0


def test_strategy_path_same_bar_tie_uses_closest_to_open() -> None:
    frame = _frame(side=1)
    frame.loc[frame.index[1], ["bid_open", "bid_high", "bid_low"]] = [100.0, 117.0, 97.0]
    out = _target(frame)

    assert out["matb_exit_reason"].iloc[0] == "stop_loss"
    assert out["matb_net_trade_r"].iloc[0] == pytest.approx(-1.0)


def test_strategy_path_explicit_costs_reduce_net_r() -> None:
    frame = _frame(side=1)
    frame.loc[frame.index[1], "bid_low"] = 97.5
    out = _target(frame, cost_per_unit_turnover=0.001)

    assert out["matb_gross_trade_r"].iloc[0] == pytest.approx(-1.0)
    assert out["matb_transaction_cost_r"].iloc[0] > 0.0
    assert out["matb_net_trade_r"].iloc[0] < out["matb_gross_trade_r"].iloc[0]


def test_strategy_path_missing_quote_set_uses_audited_fallback() -> None:
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
    out = _target(frame)

    assert out["matb_execution_source"].iloc[0] == "midpoint_fallback"


def test_strategy_path_rejects_overlapping_candidate_for_same_asset() -> None:
    frame = _frame(side=1)
    frame.loc[frame.index[1], ["matb_candidate", "matb_side"]] = [1, 1]
    out = _target(frame)

    assert out["matb_event_available"].iloc[0] == 1
    assert out["matb_event_available"].iloc[1] == 0
    assert out["matb_exit_reason"].iloc[1] == "overlapping_open_trade"
    assert np.isnan(out["matb_label_success"].iloc[1])
