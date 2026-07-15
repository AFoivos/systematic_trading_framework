from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.trend_vwap_pullback_candidate import (
    _add_path_features,
    _add_risk_state_features,
    _apply_candidate_rules,
    _session_vwap,
    transition_pulse,
    trend_vwap_pullback_candidate_feature,
)


def _ohlcv(index: pd.DatetimeIndex) -> pd.DataFrame:
    close = pd.Series(100.0 + np.linspace(0.0, 2.0, len(index)), index=index)
    return pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0]),
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": np.arange(1, len(index) + 1, dtype=float),
        },
        index=index,
    )


def test_transition_pulse_emits_only_false_to_true_events() -> None:
    state = pd.Series([False, True, True, True, False, True, True])
    assert transition_pulse(state).tolist() == [False, True, False, False, False, True, False]


def test_candidate_side_is_positive_only_on_candidate_pulse() -> None:
    frame = _ohlcv(pd.date_range("2024-01-02", periods=300, freq="30min", tz="UTC"))
    out = trend_vwap_pullback_candidate_feature(frame, stage=0)
    assert out["trend_vwap_candidate_side"].isin([0, 1]).all()
    pd.testing.assert_series_equal(
        out["trend_vwap_candidate_side"],
        out["trend_vwap_base_candidate"],
        check_names=False,
    )


def test_session_vwap_resets_excludes_premarket_and_handles_dst() -> None:
    index = pd.DatetimeIndex(
        [
            "2024-03-08 14:00:00+00:00",  # 09:00 EST, pre-market
            "2024-03-08 14:30:00+00:00",  # 09:30 EST
            "2024-03-08 15:00:00+00:00",  # 10:00 EST
            "2024-03-11 13:00:00+00:00",  # 09:00 EDT, pre-market
            "2024-03-11 13:30:00+00:00",  # 09:30 EDT
            "2024-03-11 14:00:00+00:00",  # 10:00 EDT
        ]
    )
    high = pd.Series([11, 21, 31, 101, 41, 61], index=index, dtype=float)
    low = high - 2.0
    close = high - 1.0
    volume = pd.Series([100, 1, 3, 100, 2, 2], index=index, dtype=float)

    vwap, local = _session_vwap(high, low, close, volume, timezone="America/New_York")

    assert local[1].hour == 9 and local[1].minute == 30
    assert local[4].hour == 9 and local[4].minute == 30
    assert np.isnan(vwap.iloc[0]) and np.isnan(vwap.iloc[3])
    assert vwap.iloc[1] == pytest.approx(20.0)
    assert vwap.iloc[2] == pytest.approx((20.0 * 1.0 + 30.0 * 3.0) / 4.0)
    assert vwap.iloc[4] == pytest.approx(40.0)
    assert vwap.iloc[5] == pytest.approx(50.0)


def test_session_vwap_is_unchanged_when_future_inputs_change() -> None:
    index = pd.date_range("2024-05-06 13:30", periods=6, freq="30min", tz="UTC")
    frame = _ohlcv(index)
    first, _ = _session_vwap(frame.high, frame.low, frame.close, frame.volume, timezone="America/New_York")
    changed = frame.copy()
    changed.loc[index[-2]:, ["high", "low", "close", "volume"]] *= 100.0
    second, _ = _session_vwap(
        changed.high,
        changed.low,
        changed.close,
        changed.volume,
        timezone="America/New_York",
    )
    pd.testing.assert_series_equal(first.iloc[:-2], second.iloc[:-2])


def test_expansion_memory_excludes_current_bar_and_pullback_depth_is_exact() -> None:
    distance = pd.Series([0.1, 0.2, 0.8, 1.0, 0.7, 0.6, 0.5, 0.4, 0.3, 2.0], dtype=float)
    out = _add_path_features(pd.DataFrame({"d_vwap_atr": distance}))
    assert out.loc[8, "prior_8_max_d_vwap_atr"] == pytest.approx(1.0)
    assert out.loc[8, "pullback_depth_atr"] == pytest.approx(0.7)
    assert out.loc[9, "prior_8_max_d_vwap_atr"] == pytest.approx(1.0)


def _rule_frame(index: pd.DatetimeIndex) -> pd.DataFrame:
    size = len(index)
    return pd.DataFrame(
        {
            "close": [100.0] * size,
            "high": [99.0] * size,
            "low": [99.5] * size,
            "atr_20": [1.0] * size,
            "ema_50": [99.0] * size,
            "ema_100": [98.0] * size,
            "ema50_slope_5_atr": [1.0] * size,
            "rolling_log_price_r2_96": [0.20] * size,
            "mama": [100.0] * size,
            "fama": [99.0] * size,
            "prior_8_max_d_vwap_atr": [1.0] * size,
            "return_4_atr": [1.0] * size,
            "d_vwap_atr": [0.0] * size,
            "pullback_depth_atr": [1.0] * size,
            "vwap_reclaim_cross": [1] * size,
            "ppo_hist_12_26_9": np.arange(size, dtype=float),
            "stoch_rsi_bullish_cross": [0] * size,
            "shock_active": [0] * size,
            "resistance_distance_atr": [-0.1] * size,
            "atr_percent_rank_252": [0.5] * size,
        },
        index=index,
    )


def test_temporary_trend_score_requires_three_of_four_and_mandatory_conditions() -> None:
    index = pd.date_range("2024-05-06 14:00", periods=2, freq="30min", tz="UTC")
    frame = _rule_frame(index)
    out = _apply_candidate_rules(frame.copy(), stage=2, local_index=index.tz_convert("America/New_York"))
    assert out["trend_vwap_trend_score"].iloc[-1] == 3
    assert out["trend_vwap_base_state"].iloc[-1] == 1

    frame.loc[index[-1], "ema_50"] = 97.0
    frame.loc[index[-1], "ema_100"] = 98.0
    out = _apply_candidate_rules(frame, stage=2, local_index=index.tz_convert("America/New_York"))
    assert out["trend_vwap_base_state"].iloc[-1] == 0


def test_final_trend_score_accepts_four_of_five() -> None:
    index = pd.date_range("2024-05-06 14:00", periods=2, freq="30min", tz="UTC")
    frame = _rule_frame(index)
    out = _apply_candidate_rules(frame, stage=6, local_index=index.tz_convert("America/New_York"))
    assert out["trend_vwap_trend_score"].iloc[-1] == 4
    assert out["trend_vwap_base_state"].iloc[-1] == 1


def test_resistance_rejects_near_level_but_allows_breakout() -> None:
    index = pd.date_range("2024-05-06 14:00", periods=2, freq="30min", tz="UTC")
    near = _rule_frame(index)
    near["resistance_distance_atr"] = 0.25
    near_out = _apply_candidate_rules(near, stage=8, local_index=index.tz_convert("America/New_York"))
    assert near_out["trend_vwap_resistance_ok"].iloc[-1] == 0

    breakout = _rule_frame(index)
    breakout["resistance_distance_atr"] = -0.01
    breakout_out = _apply_candidate_rules(breakout, stage=8, local_index=index.tz_convert("America/New_York"))
    assert breakout_out["trend_vwap_resistance_ok"].iloc[-1] == 1


def test_shock_uses_shifted_volatility_reference() -> None:
    index = pd.date_range("2024-01-01", periods=100, freq="30min", tz="UTC")
    returns = pd.Series(np.tile([-0.01, 0.01], 50), index=index)
    returns.iloc[-1] = 0.20
    frame = pd.DataFrame(
        {
            "return_1": returns,
            "true_range": 1.0,
            "atr_20": 1.0,
            "high": np.arange(100, dtype=float),
            "close": np.arange(100, dtype=float),
        },
        index=index,
    )
    out = _add_risk_state_features(frame)
    assert out["shock_active"].iloc[-1] == 1

