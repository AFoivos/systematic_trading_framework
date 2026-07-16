from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtesting.manual_barrier import run_manual_barrier_backtest
from src.signals.forecast_signal import compute_forecast_threshold_candidates
from src.targets.path_dependent_r import build_path_dependent_r_target


def _base_frame(rows: int = 6) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01 09:00", periods=rows, freq="30min")
    return pd.DataFrame(
        {
            "open": [100.0] * rows,
            "high": [100.2] * rows,
            "low": [99.8] * rows,
            "close": [100.0] * rows,
            "vol": [0.01] * rows,
            "pred_ret": [0.0] * rows,
            "pred_is_oos": [True] * rows,
            "filter_a": [1.0] * rows,
            "primary_candidate": [0.0] * rows,
            "primary_candidate_side": [0.0] * rows,
        },
        index=idx,
    )


def _target(
    frame: pd.DataFrame,
    *,
    cost_per_unit_turnover: float = 0.0,
    max_holding_bars: int = 3,
    allow_partial_horizon: bool = False,
    entry_price_mode: str = "next_open",
    stop_mode: str = "volatility_stop",
    risk_per_trade: float = 0.006,
) -> pd.DataFrame:
    out, _, _, _ = build_path_dependent_r_target(
        frame,
        {
            "candidate_col": "primary_candidate",
            "side_col": "primary_candidate_side",
            "pred_is_oos_col": "pred_is_oos",
            "open_col": "open",
            "high_col": "high",
            "low_col": "low",
            "close_col": "close",
            "volatility_col": "vol",
            "entry_price_mode": entry_price_mode,
            "stop_mode": stop_mode,
            "risk_per_trade": risk_per_trade,
            "take_profit_r": 1.0,
            "stop_loss_r": 1.0,
            "max_holding_bars": max_holding_bars,
            "cost_per_unit_turnover": cost_per_unit_turnover,
            "slippage_per_unit_turnover": 0.0,
            "allow_partial_horizon": allow_partial_horizon,
        },
    )
    return out


def _candidate(frame: pd.DataFrame, idx: int, side: int) -> pd.DataFrame:
    frame = frame.copy()
    frame.iloc[idx, frame.columns.get_loc("primary_candidate")] = 1.0
    frame.iloc[idx, frame.columns.get_loc("primary_candidate_side")] = float(side)
    return frame


def test_forecast_threshold_candidates_are_oos_only_and_filter_gated() -> None:
    frame = _base_frame(5)
    frame["pred_ret"] = [0.8, 0.9, -0.9, -0.95, 0.1]
    frame["pred_is_oos"] = [False, True, True, True, True]
    frame["filter_a"] = [1.0, 0.4, 1.0, 1.0, 1.0]

    out = compute_forecast_threshold_candidates(
        frame,
        forecast_col="pred_ret",
        pred_is_oos_col="pred_is_oos",
        upper=0.7,
        lower=-0.85,
        mode="long_short",
        activation_filters=[{"col": "filter_a", "op": "ge", "value": 0.5}],
    )

    assert out["primary_candidate"].tolist() == [0.0, 0.0, 1.0, 1.0, 0.0]
    assert out["primary_candidate_side"].tolist() == [0.0, 0.0, -1.0, -1.0, 0.0]
    assert out["primary_candidate_strength"].iloc[2] == pytest.approx(0.9)
    assert out["primary_candidate_threshold_distance"].iloc[2] == pytest.approx(0.05)
    assert out["primary_candidate_threshold_distance"].iloc[3] == pytest.approx(0.10)


def test_path_dependent_r_long_take_profit_first() -> None:
    frame = _candidate(_base_frame(), 0, 1)
    frame.loc[frame.index[1], ["high", "low", "close"]] = [101.2, 99.9, 101.0]

    out = _target(frame)

    assert out["meta_entry_price"].iloc[0] == pytest.approx(100.0)
    assert out["meta_exit_price"].iloc[0] == pytest.approx(101.0)
    assert out["meta_exit_reason"].iloc[0] == "take_profit"
    assert out["meta_gross_r"].iloc[0] == pytest.approx(1.0)
    assert out["meta_net_r"].iloc[0] == pytest.approx(1.0)
    assert out["meta_label_positive"].iloc[0] == 1.0


def test_path_dependent_r_long_stop_loss_first() -> None:
    frame = _candidate(_base_frame(), 0, 1)
    frame.loc[frame.index[1], ["high", "low", "close"]] = [100.2, 98.8, 99.0]

    out = _target(frame)

    assert out["meta_exit_reason"].iloc[0] == "stop_loss"
    assert out["meta_gross_r"].iloc[0] == pytest.approx(-1.0)
    assert out["meta_net_r"].iloc[0] == pytest.approx(-1.0)
    assert out["meta_label_positive"].iloc[0] == 0.0


def test_path_dependent_r_short_take_profit_first() -> None:
    frame = _candidate(_base_frame(), 0, -1)
    frame.loc[frame.index[1], ["high", "low", "close"]] = [100.1, 98.8, 99.0]

    out = _target(frame)

    assert out["meta_side"].iloc[0] == -1.0
    assert out["meta_exit_reason"].iloc[0] == "take_profit"
    assert out["meta_gross_r"].iloc[0] == pytest.approx(1.0)
    assert out["meta_net_r"].iloc[0] == pytest.approx(1.0)


def test_path_dependent_r_short_stop_loss_first() -> None:
    frame = _candidate(_base_frame(), 0, -1)
    frame.loc[frame.index[1], ["high", "low", "close"]] = [101.2, 99.5, 101.0]

    out = _target(frame)

    assert out["meta_exit_reason"].iloc[0] == "stop_loss"
    assert out["meta_gross_r"].iloc[0] == pytest.approx(-1.0)
    assert out["meta_net_r"].iloc[0] == pytest.approx(-1.0)


def test_path_dependent_r_same_bar_take_profit_and_stop_uses_manual_conservative_tie_break() -> None:
    frame = _candidate(_base_frame(), 0, 1)
    frame.loc[frame.index[1], ["high", "low", "close"]] = [101.2, 98.8, 100.0]

    out = _target(frame)

    assert out["meta_exit_reason"].iloc[0] == "stop_and_target_same_bar_stop_first"
    assert out["meta_gross_r"].iloc[0] == pytest.approx(-1.0)


def test_path_dependent_r_time_exit_and_max_holding() -> None:
    frame = _candidate(_base_frame(), 0, 1)
    frame.loc[frame.index[1], ["high", "low", "close"]] = [100.2, 99.8, 100.3]
    frame.loc[frame.index[2], ["high", "low", "close"]] = [100.2, 99.8, 100.5]

    out = _target(frame, max_holding_bars=2)

    assert out["meta_exit_reason"].iloc[0] == "max_holding_close"
    assert out["meta_holding_bars"].iloc[0] == 2.0
    assert out["meta_hit_step"].iloc[0] == 1.0
    assert out["meta_gross_r"].iloc[0] == pytest.approx(0.5)


def test_path_dependent_r_costs_reduce_net_r() -> None:
    frame = _candidate(_base_frame(), 0, 1)
    frame.loc[frame.index[1], ["high", "low", "close"]] = [101.2, 99.9, 101.0]

    out = _target(frame, cost_per_unit_turnover=0.0001)

    assert out["meta_gross_r"].iloc[0] == pytest.approx(1.0)
    assert out["meta_net_r"].iloc[0] == pytest.approx(0.98)
    assert out["meta_label_min_1_00r"].iloc[0] == 0.0


def test_path_dependent_r_labels_are_candidate_only() -> None:
    frame = _candidate(_base_frame(), 0, 1)
    frame.loc[frame.index[1], ["high", "low", "close"]] = [101.2, 99.9, 101.0]

    out = _target(frame)

    assert out["meta_candidate"].tolist() == [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert np.isnan(out["meta_net_r"].iloc[1:]).all()
    assert np.isnan(out["meta_label_positive"].iloc[1:]).all()


def test_path_dependent_r_insample_candidate_is_rejected() -> None:
    frame = _candidate(_base_frame(), 0, 1)
    frame.loc[frame.index[0], "pred_is_oos"] = False
    frame.loc[frame.index[1], ["high", "low", "close"]] = [101.2, 99.9, 101.0]

    out = _target(frame)

    assert out["meta_candidate"].iloc[0] == 0.0
    assert np.isnan(out["meta_net_r"].iloc[0])
    assert np.isnan(out["meta_label_positive"].iloc[0])


def test_path_dependent_r_exact_r_agreement_with_manual_barrier_backtest() -> None:
    frame = _candidate(_base_frame(), 0, -1)
    frame["signal"] = frame["primary_candidate_side"]
    frame.loc[frame.index[1], ["high", "low", "close"]] = [100.1, 98.8, 99.0]

    target = _target(frame)
    backtest = run_manual_barrier_backtest(
        frame,
        signal_col="signal",
        take_profit_r=1.0,
        stop_loss_r=1.0,
        risk_per_trade=0.006,
        max_holding_bars=3,
        cost_per_unit_turnover=0.0,
        slippage_per_unit_turnover=0.0,
        allow_short=True,
        stop_mode="volatility_stop",
        vol_col="vol",
    )
    trade = backtest.trades.iloc[0]
    risk_capital = float(trade["position_size"]) * 0.01

    assert target["meta_entry_price"].iloc[0] == pytest.approx(trade["entry_price"])
    assert target["meta_exit_price"].iloc[0] == pytest.approx(trade["exit_price"])
    assert target["meta_exit_reason"].iloc[0] == trade["exit_reason"]
    assert target["meta_holding_bars"].iloc[0] == trade["bars_held"]
    assert target["meta_gross_r"].iloc[0] == pytest.approx(float(trade["gross_return"]) / risk_capital)
    assert target["meta_net_r"].iloc[0] == pytest.approx(float(trade["net_return"]) / risk_capital)


def test_path_dependent_r_tail_without_full_future_path_is_unlabeled() -> None:
    frame = _candidate(_base_frame(3), 1, 1)

    out = _target(frame, max_holding_bars=3)

    assert out["meta_exit_reason"].iloc[1] == "unavailable_tail"
    assert np.isnan(out["meta_net_r"].iloc[1])
    assert np.isnan(out["meta_label_positive"].iloc[1])


def test_path_dependent_r_missing_entry_price_is_unlabeled() -> None:
    frame = _candidate(_base_frame(), 0, 1)
    frame.loc[frame.index[1], "open"] = np.nan

    out = _target(frame)

    assert out["meta_exit_reason"].iloc[0] == "invalid_entry"
    assert np.isnan(out["meta_net_r"].iloc[0])
    assert np.isnan(out["meta_label_positive"].iloc[0])


def test_path_dependent_r_invalid_volatility_is_unlabeled() -> None:
    frame = _candidate(_base_frame(), 0, 1)
    frame.loc[frame.index[0], "vol"] = 0.0

    out = _target(frame)

    assert out["meta_exit_reason"].iloc[0] == "invalid_volatility"
    assert np.isnan(out["meta_net_r"].iloc[0])
    assert np.isnan(out["meta_label_positive"].iloc[0])


def test_path_dependent_r_emits_standardized_horizon_metadata() -> None:
    _, _, _, finite_meta = build_path_dependent_r_target(
        _base_frame(),
        {
            "candidate_col": "primary_candidate",
            "side_col": "primary_candidate_side",
            "pred_is_oos_col": "pred_is_oos",
            "volatility_col": "vol",
            "max_holding_bars": 3,
        },
    )
    _, _, _, unlimited_meta = build_path_dependent_r_target(
        _base_frame(),
        {
            "candidate_col": "primary_candidate",
            "side_col": "primary_candidate_side",
            "pred_is_oos_col": "pred_is_oos",
            "volatility_col": "vol",
            "max_holding_bars": None,
            "allow_partial_horizon": True,
        },
    )

    assert finite_meta["horizon"] == 3
    assert finite_meta["max_holding"] == 3
    assert finite_meta["unlimited_horizon"] is False
    assert unlimited_meta["horizon"] is None
    assert unlimited_meta["max_holding"] is None
    assert unlimited_meta["unlimited_horizon"] is True


@pytest.mark.parametrize("side", [1, -1])
def test_path_dependent_r_current_close_ignores_pre_entry_bar_extremes(side: int) -> None:
    frame = _candidate(_base_frame(), 0, side)
    frame.loc[frame.index[0], ["open", "high", "low", "close"]] = [100.0, 120.0, 80.0, 100.0]
    frame.loc[frame.index[1:3], ["open", "high", "low", "close"]] = [100.0, 101.0, 99.0, 100.0]

    out = _target(
        frame,
        max_holding_bars=2,
        entry_price_mode="current_close",
        stop_mode="fixed_return",
        risk_per_trade=0.05,
    )

    assert out["meta_entry_price"].iloc[0] == pytest.approx(100.0)
    assert out["meta_exit_reason"].iloc[0] == "max_holding_close"
    assert out["meta_holding_bars"].iloc[0] == pytest.approx(2.0)
