from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.technical.atr import compute_atr
from src.features.eurusd_ftmo_ml_v2_contract import validate_feature_contract
from src.features.eurusd_ftmo_ml_v2 import (
    build_bar_feature_frame,
    build_candidate_feature_frame,
)
from src.signals.eurusd_ftmo_ml_v2_candidates import validate_and_prepare_market_data
from src.utils.eurusd_ftmo_ml_v2_contract import FEATURE_COLUMNS


def _raw_market(rows: int = 1100) -> pd.DataFrame:
    index = pd.date_range("2020-01-01", periods=rows, freq="30min")
    mid = 1.10 + np.linspace(0.0, 0.02, rows) + np.sin(np.arange(rows) / 17.0) * 0.001
    spread = np.full(rows, 0.0001)
    open_ = mid - 0.00002
    high = np.maximum(open_, mid) + 0.0002
    low = np.minimum(open_, mid) - 0.0002
    bid_shift = -spread / 2.0
    ask_shift = spread / 2.0
    return pd.DataFrame(
        {
            "timestamp": index,
            "open": open_, "high": high, "low": low, "close": mid,
            "volume": 100.0 + np.arange(rows) % 23,
            "bid_open": open_ + bid_shift, "bid_high": high + bid_shift,
            "bid_low": low + bid_shift, "bid_close": mid + bid_shift,
            "ask_open": open_ + ask_shift, "ask_high": high + ask_shift,
            "ask_low": low + ask_shift, "ask_close": mid + ask_shift,
            "spread_close": spread, "spread_bps": spread / mid * 10_000.0,
        }
    )


def test_atr_wilder_ewm_matches_exact_contract() -> None:
    close = pd.Series(np.linspace(1.0, 1.2, 80), name="close")
    high = close + 0.01
    low = close - 0.01
    previous = close.shift(1)
    expected = pd.concat(
        [(high - low).abs(), (high - previous).abs(), (low - previous).abs()], axis=1
    ).max(axis=1).ewm(alpha=1 / 48, adjust=False, min_periods=48).mean()
    actual = compute_atr(high, low, close, window=48, method="wilder_ewm")
    pd.testing.assert_series_equal(actual, expected.rename("atr_48"))


def test_feature_contract_is_exact_and_fail_closed() -> None:
    assert len(FEATURE_COLUMNS) == 151
    assert len(set(FEATURE_COLUMNS)) == 151
    assert validate_feature_contract(FEATURE_COLUMNS) == list(FEATURE_COLUMNS)
    reordered = list(FEATURE_COLUMNS)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    try:
        validate_feature_contract(reordered)
    except ValueError as exc:
        assert "reordered=True" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Reordered features must fail closed.")


def test_candidate_features_have_exact_order_and_strict_completed_history() -> None:
    market, _ = validate_and_prepare_market_data(_raw_market())
    times = [market.index[1000], market.index[1002]]
    candidates = pd.DataFrame(
        {
            "candidate_id": ["a", "b"],
            "signal_timestamp": times,
            "entry_timestamp": [market.index[1001], market.index[1003]],
            "exit_timestamp": [market.index[1002], market.index[1005]],
            "direction": [1, -1],
            "is_session": [0, 1],
            "amplitude": [0.25, 1.0],
            "bars_planned": [24, 26],
            "net_return": [0.001, -0.001],
            "target_positive_net": [1, 0],
        }
    )
    enriched = build_candidate_feature_frame(market, candidates)
    assert list(enriched.loc[:, list(FEATURE_COLUMNS)].columns) == list(FEATURE_COLUMNS)
    assert np.isnan(enriched.loc[0, "past_mean_all"])
    assert np.isnan(enriched.loc[1, "past_mean_all"])  # first trade completes exactly at b's signal
    assert np.isclose(enriched.loc[0, "dir_mom_1_atr"], enriched.loc[0, "mom_1_atr"])
    assert np.isclose(enriched.loc[1, "dir_mom_1_atr"], -enriched.loc[1, "mom_1_atr"])


def test_bar_features_are_unchanged_when_future_is_mutated() -> None:
    raw = _raw_market(320)
    market, _ = validate_and_prepare_market_data(raw)
    cutoff = market.index[250]
    baseline = build_bar_feature_frame(market)
    mutated = market.copy()
    future = mutated.index > cutoff
    for column in ("mid_open", "mid_high", "mid_low", "mid_close", "volume", "spread_close"):
        mutated.loc[future, column] *= 1.7
    recalculated = build_bar_feature_frame(mutated)
    columns = ["mom_8_atr", "ema_dist_32", "rsi_14", "adx14", "range_pos_48", "eff_48", "ac_48"]
    pd.testing.assert_frame_equal(baseline.loc[:cutoff, columns], recalculated.loc[:cutoff, columns])
