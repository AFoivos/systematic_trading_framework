from __future__ import annotations

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from src.features.multi_asset_trend_breakout import add_multi_asset_trend_breakout_features


def _frame(periods: int = 120, *, breakout_side: int = 1) -> pd.DataFrame:
    index = pd.date_range("2024-01-01 00:00", periods=periods, freq="30min", tz="UTC")
    base = 100.0 + 0.02 * np.sin(np.arange(periods) / 3.0)
    frame = pd.DataFrame(index=index)
    frame["close"] = base
    frame["open"] = frame["close"].shift(1).fillna(frame["close"])
    frame["high"] = 200.0
    frame["low"] = 99.0
    frame["spread_bps"] = 1.0 + 0.01 * np.cos(np.arange(periods) / 5.0)
    decision_positions = np.flatnonzero((index.hour == 19) & (index.minute == 30))
    position = int(decision_positions[-1])
    if breakout_side > 0:
        frame.iloc[position, frame.columns.get_loc("close")] = 201.0
        frame.iloc[position, frame.columns.get_loc("open")] = 100.0
        frame.iloc[position, frame.columns.get_loc("high")] = 201.1
    else:
        mirrored = 300.0 - frame[["open", "high", "low", "close"]]
        frame["open"] = mirrored["open"]
        frame["high"] = mirrored["low"]
        frame["low"] = mirrored["high"]
        frame["close"] = mirrored["close"]
        frame.iloc[position, frame.columns.get_loc("close")] = 99.0
        frame.iloc[position, frame.columns.get_loc("open")] = 200.0
        frame.iloc[position, frame.columns.get_loc("low")] = 98.9
    return frame


def _features(frame: pd.DataFrame, **overrides: object) -> pd.DataFrame:
    params: dict[str, object] = {
        "bars_per_day": 1,
        "atr_window": 3,
        "short_vol_days": 5,
        "long_vol_days": 60,
        "donchian_days": 20,
        "spread_median_days": 20,
        "trend_threshold": 0.0,
        "minimum_channel_width_atr": 0.0,
        "minimum_volatility_ratio": 0.0,
        "maximum_volatility_ratio": 100.0,
        "maximum_breakout_distance_atr": 2.0,
    }
    params.update(overrides)
    return add_multi_asset_trend_breakout_features(frame, **params)


def test_matb_feature_preserves_index_and_row_count() -> None:
    frame = _frame()
    out = _features(frame)

    assert len(out) == len(frame)
    assert out.index.equals(frame.index)


def test_matb_donchian_extrema_strictly_exclude_current_bar() -> None:
    frame = _frame()
    position = int(np.flatnonzero((frame.index.hour == 19) & (frame.index.minute == 30))[-1])
    out = _features(frame)

    assert out["matb_prior_high"].iloc[position] == pytest.approx(200.0)
    assert frame["high"].iloc[position] == pytest.approx(201.1)


def test_matb_future_mutation_does_not_change_past_features() -> None:
    frame = _frame()
    original = _features(frame)
    cut = 90
    mutated = frame.copy()
    mutated.iloc[cut:, mutated.columns.get_loc("close")] *= 5.0
    mutated.iloc[cut:, mutated.columns.get_loc("high")] *= 5.0
    mutated.iloc[cut:, mutated.columns.get_loc("low")] *= 0.1
    changed = _features(mutated)

    pdt.assert_frame_equal(
        original.iloc[:cut],
        changed.iloc[:cut],
        check_dtype=True,
        check_exact=True,
    )


def test_matb_long_short_symmetry_and_no_ambiguous_candidate() -> None:
    long_out = _features(_frame(breakout_side=1))
    short_out = _features(_frame(breakout_side=-1))

    assert int(long_out["matb_long_candidate"].sum()) == 1
    assert int(long_out["matb_short_candidate"].sum()) == 0
    assert int(short_out["matb_long_candidate"].sum()) == 0
    assert int(short_out["matb_short_candidate"].sum()) == 1
    assert not bool(
        (long_out["matb_long_candidate"].astype(bool) & long_out["matb_short_candidate"].astype(bool)).any()
    )
    assert not bool(
        (short_out["matb_long_candidate"].astype(bool) & short_out["matb_short_candidate"].astype(bool)).any()
    )


def test_matb_breakout_crossing_is_a_single_event() -> None:
    out = _features(_frame())
    candidate_rows = out.index[out["matb_candidate"].eq(1)]

    assert len(candidate_rows) == 1
    assert out.loc[candidate_rows[0], "matb_side"] == 1


def test_matb_decision_bars_match_bar_start_four_hour_closes() -> None:
    out = _features(_frame())
    decision_index = out.index[out["matb_decision_bar"].eq(1)]

    assert len(decision_index) > 0
    assert set((timestamp.hour, timestamp.minute) for timestamp in decision_index) <= {
        (3, 30),
        (7, 30),
        (11, 30),
        (15, 30),
        (19, 30),
        (23, 30),
    }


def test_matb_atr_does_not_bridge_abnormal_timestamp_gap() -> None:
    index = pd.DatetimeIndex(
        [
            "2024-01-01 00:00:00+00:00",
            "2024-01-01 00:30:00+00:00",
            "2024-01-01 01:00:00+00:00",
            "2024-01-01 04:00:00+00:00",
            "2024-01-01 04:30:00+00:00",
        ]
    )
    frame = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0, 200.0, 200.0],
            "high": [101.0, 101.0, 101.0, 201.0, 201.0],
            "low": [99.0, 99.0, 99.0, 199.0, 199.0],
            "close": [100.0, 100.0, 100.0, 200.0, 200.0],
        },
        index=index,
    )
    out = add_multi_asset_trend_breakout_features(
        frame,
        bars_per_day=1,
        atr_window=2,
        short_vol_days=1,
        long_vol_days=2,
        donchian_days=1,
        spread_median_days=1,
    )

    assert out["matb_atr"].iloc[3] == pytest.approx(2.0)
    assert out.attrs["matb_feature_audit"]["abnormal_gap_count"] == 1


def test_matb_missing_spread_remains_nan_and_is_audited() -> None:
    frame = _frame().drop(columns=["spread_bps"])
    out = _features(frame)

    assert out["matb_spread_to_median"].isna().all()
    assert out.attrs["matb_feature_audit"]["spread_available"] is False

