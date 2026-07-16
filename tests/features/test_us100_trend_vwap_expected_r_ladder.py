"""Integration contracts for the US100 Trend-VWAP expected-R ladder."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.generate_us100_trend_vwap_expected_r_ladder import (
    CONFIG_DIR,
    FILENAMES,
    model_features_for_stage,
)
from src.backtesting.manual_barrier import run_manual_barrier_backtest
from src.features.trend_vwap_pullback_candidate import trend_vwap_pullback_candidate_feature
from src.risk.controls import event_risk_guard_multiplier
from src.signals.forecast_threshold_candidate_signal import forecast_threshold_candidate_signal
from src.targets.triple_barrier import build_triple_barrier_target
from src.utils.config import load_experiment_config


def test_all_eleven_yaml_configs_parse_and_have_cumulative_explicit_features() -> None:
    paths = [CONFIG_DIR / filename for filename in FILENAMES]
    assert all(path.exists() for path in paths)
    configs = [load_experiment_config(path) for path in paths]
    assert len(configs) == 11
    for stage, cfg in enumerate(configs):
        assert cfg["data"]["symbol"] == "US100"
        assert cfg["data"]["interval"] == "30m"
        assert cfg["model"]["kind"] == "lightgbm_regressor"
        assert cfg["model"]["feature_cols"] == model_features_for_stage(stage)
        assert len(cfg["model"]["feature_cols"]) == len(set(cfg["model"]["feature_cols"]))
        feature_params = cfg["features"][-1]["params"]
        assert feature_params["session_open"] == "09:30"
        assert feature_params["session_close"] == "16:00"
        assert feature_params["timestamp_convention"] == "bar_start"
        assert "trend_vwap_candidate_side" not in cfg["model"]["feature_cols"]
        assert "trend_vwap_base_candidate" not in cfg["model"]["feature_cols"]
        expected_threshold = 0.25 if stage >= 9 else 0.0
        assert cfg["signals"]["params"]["upper"] == pytest.approx(expected_threshold)
        assert cfg["model"]["split"]["purge_bars"] >= 16
        assert cfg["model"]["split"]["embargo_bars"] >= 16

    for stage in range(1, 9):
        previous = set(configs[stage - 1]["model"]["feature_cols"])
        current = set(configs[stage]["model"]["feature_cols"])
        assert previous < current
    assert configs[9]["model"]["feature_cols"] == configs[8]["model"]["feature_cols"]
    assert configs[10]["model"]["feature_cols"] == configs[9]["model"]["feature_cols"]
    assert "max_entry_gap_atr" not in configs[9]["backtest"]
    assert configs[10]["backtest"]["max_entry_gap_atr"] == pytest.approx(0.35)
    assert "atr_20" not in configs[10]["model"]["feature_cols"]


@pytest.mark.parametrize("stage", range(9))
def test_every_feature_stage_generates_all_requested_model_columns(stage: int) -> None:
    index = pd.date_range("2024-01-01", periods=600, freq="30min", tz="UTC")
    close = pd.Series(
        100.0 + np.linspace(0.0, 3.0, len(index)) + np.sin(np.arange(len(index)) / 7),
        index=index,
    )
    frame = pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0]),
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1.0 + np.arange(len(index)) % 20,
        },
        index=index,
    )
    out = trend_vwap_pullback_candidate_feature(frame, stage=stage)
    assert not (set(model_features_for_stage(stage)) - set(out.columns))
    if stage >= 3:
        assert out["d_vwap_atr_robust_z96"].notna().any()
        assert out["d_vwap_atr_percent_rank_252"].notna().any()


def test_triple_barrier_uses_next_open_lower_first_and_long_oriented_r() -> None:
    index = pd.date_range("2024-01-01", periods=20, freq="30min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "atr_over_price_20": 0.01,
            "trend_vwap_base_candidate": [1] + [0] * 19,
            "trend_vwap_candidate_side": [1] + [0] * 19,
        },
        index=index,
    )
    frame.loc[index[1], "high"] = 104.0
    frame.loc[index[1], "low"] = 98.0
    out, _, _, meta = build_triple_barrier_target(
        frame,
        {
            "kind": "triple_barrier",
            "label_mode": "meta",
            "candidate_col": "trend_vwap_base_candidate",
            "side_col": "trend_vwap_candidate_side",
            "entry_price_mode": "next_open",
            "volatility_col": "atr_over_price_20",
            "lower_mult": 1.5,
            "upper_mult": 3.0,
            "max_holding": 16,
            "add_r_multiple": True,
            "oriented_r_col": "tb_oriented_r",
            "tie_break": "lower",
            "neutral_label": "lower",
        },
    )
    assert meta["entry_price_mode"] == "next_open"
    assert meta["max_holding"] == 16
    assert out.loc[index[0], "label_hit_step"] == pytest.approx(1.0)
    assert out.loc[index[0], "label_hit_type"] == "stop"
    assert out.loc[index[0], "tb_oriented_r"] == pytest.approx(-1.0)


@pytest.mark.parametrize("threshold", [0.0, 0.25])
def test_executable_signal_is_oos_candidate_gated_and_threshold_inclusive(threshold: float) -> None:
    frame = pd.DataFrame(
        {
            "pred_tb_oriented_r": [threshold, threshold + 0.1, threshold + 0.2],
            "pred_is_oos": [False, True, True],
            "trend_vwap_base_candidate": [1, 0, 1],
        }
    )
    out = forecast_threshold_candidate_signal(
        frame,
        forecast_col="pred_tb_oriented_r",
        pred_is_oos_col="pred_is_oos",
        signal_col="signal",
        upper=threshold,
        lower=-999.0,
        inclusive=True,
        mode="long_only",
        activation_filters=[
            {"col": "trend_vwap_base_candidate", "op": "ge", "value": 1.0},
            {"col": "pred_is_oos", "op": "ge", "value": 1.0},
        ],
    )
    assert out["signal"].tolist() == [0.0, 0.0, 1.0]


def _execution_frame() -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=15, freq="30min", tz="UTC")
    return pd.DataFrame(
        {
            "signal": [
                1.0,
                0.0,
                1.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                0.0,
                0.0,
                0.0,
            ],
            "open": 100.0,
            "high": 100.5,
            "low": [100.0, 98.0] + [100.0] * 13,
            "close": 100.0,
            "atr_over_price_20": 0.01,
            "atr_20": 1.0,
        },
        index=index,
    )


def test_next_open_gap_filter_rejects_adverse_long_gap_over_point_three_five_atr() -> None:
    frame = _execution_frame().iloc[:5].copy()
    frame["signal"] = [1.0, 0.0, 0.0, 0.0, 0.0]
    frame.iloc[1, frame.columns.get_loc("open")] = 99.64
    result = run_manual_barrier_backtest(
        frame,
        signal_col="signal",
        take_profit_r=3.0,
        stop_loss_r=1.5,
        risk_per_trade=0.003,
        max_holding_bars=2,
        stop_mode="volatility_stop",
        vol_col="atr_over_price_20",
        max_entry_gap_atr=0.35,
        entry_gap_atr_col="atr_20",
    )
    assert result.trades.empty
    assert result.summary["rejected_gap_filter"] == 1


def test_stopped_trade_enforces_eight_bar_cooldown_without_pyramiding() -> None:
    result = run_manual_barrier_backtest(
        _execution_frame(),
        signal_col="signal",
        take_profit_r=3.0,
        stop_loss_r=1.5,
        risk_per_trade=0.003,
        max_holding_bars=2,
        stop_mode="volatility_stop",
        vol_col="atr_over_price_20",
        stop_cooldown_bars=8,
    )
    assert len(result.trades) == 2
    assert result.summary["rejected_cooldown"] == 1


def test_manual_barrier_ignores_signals_while_a_trade_is_active() -> None:
    index = pd.date_range("2024-01-01", periods=15, freq="30min", tz="UTC")
    frame = pd.DataFrame(
        {
            "signal": [1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
            "open": 100.0,
            "high": 100.1,
            "low": 99.9,
            "close": 100.0,
            "atr_over_price_20": 0.01,
        },
        index=index,
    )
    result = run_manual_barrier_backtest(
        frame,
        signal_col="signal",
        take_profit_r=3.0,
        stop_loss_r=1.5,
        risk_per_trade=0.003,
        max_holding_bars=5,
        stop_mode="volatility_stop",
        vol_col="atr_over_price_20",
    )
    assert len(result.trades) == 2
    assert pd.to_datetime(result.trades["signal_timestamp"]).tolist() == [index[0], index[10]]


def test_daily_and_weekly_event_risk_guards_use_only_prior_realized_returns() -> None:
    config = {
        "enabled": True,
        "timezone": "America/New_York",
        "daily_soft_stop": 0.012,
        "daily_soft_stop_risk_multiplier": 0.5,
        "daily_hard_stop": 0.015,
        "weekly_drawdown": 0.030,
        "weekly_anchor": "W-FRI",
    }
    same_day = pd.Series(
        [0.0, -0.013, -0.50],
        index=pd.DatetimeIndex(["2024-01-08 15:00Z", "2024-01-08 15:30Z", "2024-01-08 16:00Z"]),
    )
    multiplier, reason = event_risk_guard_multiplier(same_day, at_position=2, config=config)
    assert multiplier == pytest.approx(0.5)
    assert reason == "daily_soft_stop"

    hard_day = same_day.copy()
    hard_day.iloc[1] = -0.016
    multiplier, reason = event_risk_guard_multiplier(hard_day, at_position=2, config=config)
    assert multiplier == 0.0
    assert reason == "daily_hard_stop"

    weekly = pd.Series(
        [0.0, -0.031, 0.0],
        index=pd.DatetimeIndex(["2024-01-08 15:00Z", "2024-01-08 15:30Z", "2024-01-09 15:00Z"]),
    )
    multiplier, reason = event_risk_guard_multiplier(weekly, at_position=2, config=config)
    assert multiplier == 0.0
    assert reason == "weekly_stop"

    weekly_retracement = pd.Series(
        [0.10, -0.0455, 0.0],
        index=pd.DatetimeIndex(["2024-01-08 15:00Z", "2024-01-08 15:30Z", "2024-01-09 15:00Z"]),
    )
    multiplier, reason = event_risk_guard_multiplier(
        weekly_retracement,
        at_position=2,
        config=config,
    )
    assert multiplier == 0.0
    assert reason == "weekly_stop"

    future_only = pd.Series(
        [0.0, 0.0, -0.50],
        index=pd.DatetimeIndex(["2024-01-08 15:00Z", "2024-01-08 15:30Z", "2024-01-08 16:00Z"]),
    )
    multiplier, reason = event_risk_guard_multiplier(future_only, at_position=2, config=config)
    assert multiplier == 1.0
    assert reason is None
