from __future__ import annotations

import numpy as np
import pandas as pd

from src.signals.eurusd_ftmo_ml_v2_candidates import (
    generate_pullback_candidates,
    generate_session_fade_candidates,
    validate_and_prepare_market_data,
)
from src.signals.eurusd_ftmo_ml_v2_signal import aggregate_candidate_signals, score_to_confidence
from src.utils.eurusd_ftmo_ml_v2_contract import PULLBACK_COMPONENTS, PullbackComponent


def _market(index: pd.DatetimeIndex, mid: np.ndarray | None = None) -> pd.DataFrame:
    values = np.asarray(mid if mid is not None else np.full(len(index), 1.10), dtype=float)
    spread = np.full(len(index), 0.0001)
    raw = pd.DataFrame(
        {
            "timestamp": index,
            "open": values, "high": values + 0.0003, "low": values - 0.0003, "close": values,
            "volume": 100.0,
            "bid_open": values - spread / 2, "bid_high": values + 0.00025,
            "bid_low": values - 0.00035, "bid_close": values - spread / 2,
            "ask_open": values + spread / 2, "ask_high": values + 0.00035,
            "ask_low": values - 0.00025, "ask_close": values + spread / 2,
            "spread_close": spread, "spread_bps": spread / values * 10_000,
        }
    )
    prepared, audit = validate_and_prepare_market_data(raw)
    assert audit["spread_bps_semantics"] == "CANONICAL_BPS"
    assert audit["research_eligible"] is False
    assert audit["research_classifications"] == ["NOT_RESEARCH_SOURCE"]
    prepared["atr48"] = 0.001
    for span in (12, 16, 20, 192):
        prepared[f"ema_{span}"] = prepared["mid_close"]
    return prepared


def test_pullback_threshold_window_next_open_and_native_exit() -> None:
    index = pd.date_range("2024-01-02 05:30", periods=8, freq="30min")
    market = _market(index)
    component = PULLBACK_COMPONENTS[0]
    market["ema_192"] = market["mid_close"] - 0.001  # positive slow regime
    market[f"ema_{component.ema_span}"] = market["mid_close"]
    market.loc[pd.Timestamp("2024-01-02 05:30"), f"ema_{component.ema_span}"] = 1.1030
    market.loc[pd.Timestamp("2024-01-02 06:00"), f"ema_{component.ema_span}"] = 1.1026
    candidates = generate_pullback_candidates(market, components=(component,))
    assert len(candidates) == 1
    trade = candidates.iloc[0]
    assert trade.signal_timestamp == pd.Timestamp("2024-01-02 06:00")
    assert trade.entry_timestamp == pd.Timestamp("2024-01-02 06:30")
    assert trade.exit_signal_timestamp == pd.Timestamp("2024-01-02 06:30")
    assert trade.exit_timestamp == pd.Timestamp("2024-01-02 07:00")
    assert trade.direction == 1


def test_pullback_18_utc_boundary_is_inclusive_then_exits_when_illiquid() -> None:
    index = pd.date_range("2024-01-02 18:00", periods=4, freq="30min")
    market = _market(index)
    component = PULLBACK_COMPONENTS[0]
    market["ema_192"] = market["mid_close"] - 0.001
    market.loc[index[0], f"ema_{component.ema_span}"] = 1.1026
    candidates = generate_pullback_candidates(market, components=(component,))
    assert candidates.iloc[0].signal_timestamp == index[0]
    assert candidates.iloc[0].entry_timestamp == index[1]
    assert candidates.iloc[0].exit_signal_timestamp == index[1]
    assert candidates.iloc[0].exit_timestamp == index[2]


def test_pullback_max_hold_and_adverse_stop_are_native_component_exits() -> None:
    component = PullbackComponent("component_1", 16, 2.0, 0.25, 2, 4.0)
    index = pd.date_range("2024-01-02 06:00", periods=6, freq="30min")
    market = _market(index)
    market["ema_192"] = market["mid_close"] - 0.001
    market["ema_16"] = market["mid_close"] + 0.001
    market.loc[index[0], "ema_16"] = market.loc[index[0], "mid_close"] + 0.0021
    max_hold = generate_pullback_candidates(market, components=(component,)).iloc[0]
    assert max_hold.exit_signal_timestamp == index[2]
    assert max_hold.exit_timestamp == index[3]

    adverse_market = market.copy()
    adverse_market.loc[index[1], "ema_16"] = adverse_market.loc[index[1], "mid_close"] + 0.0045
    adverse = generate_pullback_candidates(adverse_market, components=(component,)).iloc[0]
    assert adverse.exit_signal_timestamp == index[1]
    assert adverse.exit_timestamp == index[2]


def test_pullback_components_keep_independent_state() -> None:
    index = pd.date_range("2024-01-02 06:00", periods=6, freq="30min")
    market = _market(index)
    market["ema_192"] = market["mid_close"] - 0.001
    market.loc[index[0], "ema_16"] = 1.1026
    market.loc[index[1], "ema_20"] = 1.10235
    candidates = generate_pullback_candidates(market, components=PULLBACK_COMPONENTS[:2])
    assert set(candidates["component_id"]) == {"component_1", "component_2"}


def test_session_fade_uses_previous_completed_daily_trend_and_exits_at_20() -> None:
    index = pd.date_range("2024-01-01", "2024-01-03 20:00", freq="30min")
    values = np.full(len(index), 1.10)
    values[index.normalize() == pd.Timestamp("2024-01-01")] = 1.09
    values[index.normalize() == pd.Timestamp("2024-01-02")] = 1.10
    day3 = index.normalize() == pd.Timestamp("2024-01-03")
    values[day3] = 1.10
    values[(index >= "2024-01-03 06:30") & day3] = 1.103
    market = _market(index, values)
    market["atr48"] = 0.001
    candidates = generate_session_fade_candidates(market)
    trade = candidates.loc[candidates["signal_timestamp"] == pd.Timestamp("2024-01-03 06:30")].iloc[0]
    assert trade.direction == -1
    assert trade.entry_timestamp == pd.Timestamp("2024-01-03 07:00")
    assert trade.exit_timestamp == pd.Timestamp("2024-01-03 20:00")
    assert (candidates["signal_timestamp"].dt.normalize() == pd.Timestamp("2024-01-03")).sum() == 1


def test_confidence_and_candidate_level_signal_aggregation() -> None:
    assert score_to_confidence(0.60) == 0.0
    assert np.isclose(score_to_confidence(0.70), 0.5)
    assert score_to_confidence(0.80) == 1.0
    index = pd.date_range("2024-01-01", periods=4, freq="30min")
    candidates = pd.DataFrame(
        {
            "entry_timestamp": [index[1], index[1]], "exit_timestamp": [index[3], index[2]],
            "direction": [1, -1], "is_session": [0, 1],
            "component_id": ["component_1", "session_fade"], "confidence": [1.0, 0.5],
        }
    )
    signals = aggregate_candidate_signals(index, candidates)
    assert np.isclose(signals.loc[index[1], "directional_signal"], 0.8 * 0.25 - 0.2 * 0.5)
    assert np.isclose(signals.loc[index[2], "directional_signal"], 0.8 * 0.25)
