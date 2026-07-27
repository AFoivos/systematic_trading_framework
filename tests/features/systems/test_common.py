from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.systems.common import compute_gap_diagnostics, prepare_market_data


def test_bid_ask_mode_constructs_midpoint(quoted_m1: pd.DataFrame) -> None:
    market = prepare_market_data(quoted_m1)

    assert market.source_mode == "bid_ask"
    np.testing.assert_allclose(
        market.close,
        (quoted_m1["bid_close"] + quoted_m1["ask_close"]) / 2.0,
    )


def test_fallback_mode_preserves_missing_values(fallback_m1: pd.DataFrame) -> None:
    frame = fallback_m1.copy()
    frame.loc[frame.index[20], ["open", "high", "low", "close"]] = np.nan

    market = prepare_market_data(frame)

    assert market.source_mode == "fallback"
    assert np.isnan(market.close.iloc[20])


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda frame: frame.rename(index={frame.index[2]: frame.index[1]}), "unique"),
        (lambda frame: frame.iloc[::-1], "monotonic"),
    ],
)
def test_invalid_timestamp_index_is_rejected(
    fallback_m1: pd.DataFrame,
    mutation,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        prepare_market_data(mutation(fallback_m1))


def test_non_timestamp_index_is_rejected(fallback_m1: pd.DataFrame) -> None:
    frame = fallback_m1.reset_index(drop=True)
    with pytest.raises(TypeError, match="DatetimeIndex"):
        prepare_market_data(frame)


def test_structurally_invalid_ohlc_is_not_repaired(fallback_m1: pd.DataFrame) -> None:
    frame = fallback_m1.copy()
    frame.loc[frame.index[10], "high"] = frame.loc[frame.index[10], "low"] * 0.9
    with pytest.raises(ValueError, match="high"):
        prepare_market_data(frame)


def test_invalid_bid_ask_relationship_is_rejected(quoted_m1: pd.DataFrame) -> None:
    frame = quoted_m1.copy()
    frame.loc[frame.index[15], "ask_close"] = frame.loc[frame.index[15], "bid_close"] - 0.01
    with pytest.raises(ValueError, match="ask_close"):
        prepare_market_data(frame)


def test_all_nan_ohlc_is_preserved() -> None:
    index = pd.date_range("2025-01-01", periods=5, freq="min", tz="UTC")
    frame = pd.DataFrame(np.nan, index=index, columns=["open", "high", "low", "close"])

    market = prepare_market_data(frame)

    assert market.as_frame().drop(columns=["spread_bps"]).isna().all().all()


def test_gap_diagnostics_use_explicit_fifteen_minute_bar_steps() -> None:
    index = pd.date_range("2025-01-01", periods=8, freq="15min", tz="UTC")

    gaps = compute_gap_diagnostics(index, expected_bar_minutes=15.0)

    assert not gaps.is_gap.any()
    assert not gaps.is_hard_gap.any()
    np.testing.assert_array_equal(gaps.elapsed_minutes.to_numpy(), np.full(8, 15.0))
    np.testing.assert_array_equal(gaps.elapsed_bars.to_numpy(), np.ones(8))
    np.testing.assert_array_equal(gaps.contiguous_bars.to_numpy(), np.arange(1, 9))


def test_gap_diagnostics_scale_default_gap_thresholds_with_bar_duration() -> None:
    index = pd.DatetimeIndex(
        [
            "2025-01-01 00:00:00+00:00",
            "2025-01-01 00:15:00+00:00",
            "2025-01-01 00:45:00+00:00",
            "2025-01-01 08:45:00+00:00",
        ]
    )

    gaps = compute_gap_diagnostics(index, expected_bar_minutes=15.0)

    assert gaps.is_gap.tolist() == [False, False, True, True]
    assert gaps.is_small_gap.tolist() == [False, False, True, False]
    assert gaps.is_hard_gap.tolist() == [False, False, False, True]
    assert gaps.elapsed_bars.tolist() == [1.0, 1.0, 2.0, 32.0]
