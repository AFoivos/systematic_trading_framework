from __future__ import annotations

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from src.features.btcusd_dual_trend_ftmo import (
    add_btcusd_dual_trend_30m_features,
    aggregate_btcusd_1m_to_30m,
    validate_btcusd_1m_data,
)


def _minute_frame(periods: int = 61) -> pd.DataFrame:
    index = pd.date_range("2026-01-01 00:00", periods=periods, freq="1min", tz="UTC")
    close = 100.0 + np.arange(periods, dtype=float)
    return pd.DataFrame(
        {
            "open": close - 0.25,
            "high": close + 0.50,
            "low": close - 0.50,
            "close": close,
            "volume": np.arange(1, periods + 1, dtype=float),
        },
        index=index,
    )


def _bars(periods: int = 800) -> pd.DataFrame:
    index = pd.date_range("2025-12-01", periods=periods, freq="30min", tz="UTC")
    close = 100.0 * np.exp(np.linspace(0.0, 0.30, periods) + 0.01 * np.sin(np.arange(periods) / 9.0))
    return pd.DataFrame(
        {
            "open": close * 0.999,
            "high": close * 1.002,
            "low": close * 0.998,
            "close": close,
            "volume": np.ones(periods),
            "source_rows": np.full(periods, 30),
        },
        index=index,
    )


def test_exact_1m_to_30m_aggregation() -> None:
    source = _minute_frame()
    result = aggregate_btcusd_1m_to_30m(source)

    first = result.loc[pd.Timestamp("2026-01-01 00:00", tz="UTC")]
    assert first.to_dict() == {
        "open": 99.75,
        "high": 100.5,
        "low": 99.5,
        "close": 100.0,
        "volume": 1.0,
        "source_rows": 1.0,
    }
    second = result.loc[pd.Timestamp("2026-01-01 00:30", tz="UTC")]
    assert second["open"] == pytest.approx(source["open"].iloc[1])
    assert second["high"] == pytest.approx(source["high"].iloc[1:31].max())
    assert second["low"] == pytest.approx(source["low"].iloc[1:31].min())
    assert second["close"] == pytest.approx(source["close"].iloc[30])
    assert second["volume"] == pytest.approx(source["volume"].iloc[1:31].sum())
    assert second["source_rows"] == 30


def test_source_validation_fails_closed_without_sorting_or_filling() -> None:
    duplicate = _minute_frame(3)
    duplicate.index = pd.DatetimeIndex([duplicate.index[0], duplicate.index[0], duplicate.index[2]])
    with pytest.raises(ValueError, match="unique"):
        validate_btcusd_1m_data(duplicate)

    reversed_frame = _minute_frame(3).iloc[::-1]
    with pytest.raises(ValueError, match="chronological"):
        validate_btcusd_1m_data(reversed_frame)

    invalid = _minute_frame(3)
    invalid.loc[invalid.index[1], "low"] = invalid.loc[invalid.index[1], "high"] + 1.0
    with pytest.raises(ValueError, match="low exceeds high"):
        validate_btcusd_1m_data(invalid)


def test_donchian_boundaries_are_prior_only_and_state_is_persistent() -> None:
    bars = _bars(12)
    bars["close"] = [10, 10, 10, 11, 10.5, 10.8, 9, 9.5, 9.7, 12, 11.5, 11.0]
    bars["open"] = bars["close"]
    bars["high"] = bars["close"] + 0.1
    bars["low"] = bars["close"] - 0.1
    result = add_btcusd_dual_trend_30m_features(
        bars,
        ema_fast_span=2,
        ema_slow_span=3,
        donchian_window=3,
        volatility_ewma_span=3,
    )

    expected_high = bars["high"].shift(1).rolling(3).max()
    expected_low = bars["low"].shift(1).rolling(3).min()
    pdt.assert_series_equal(result["prior_high"], expected_high, check_names=False)
    pdt.assert_series_equal(result["prior_low"], expected_low, check_names=False)
    # Long at index 3, retain long through non-breakout bars, then short at index 6.
    assert result["donchian_state"].iloc[3:6].tolist() == [1.0, 1.0, 1.0]
    assert result["donchian_state"].iloc[6:9].tolist() == [-1.0, -1.0, -1.0]


def test_ensemble_preserves_all_agreement_and_disagreement_values() -> None:
    bars = _bars(10)
    result = add_btcusd_dual_trend_30m_features(
        bars,
        ema_fast_span=2,
        ema_slow_span=3,
        donchian_window=2,
        volatility_ewma_span=2,
    )
    combinations = pd.DataFrame(
        {
            "ema": [1.0, -1.0, 1.0, -1.0],
            "donchian": [1.0, -1.0, -1.0, 1.0],
        }
    )
    values = (0.60 * combinations["ema"] + 0.40 * combinations["donchian"]).clip(-1.0, 1.0)
    assert values.tolist() == pytest.approx([1.0, -1.0, 0.2, -0.2])
    initialized = result.loc[
        result["ema_signal"].ne(0.0) & result["donchian_state"].ne(0.0),
        "ensemble_signal",
    ]
    assert set(np.round(initialized.unique(), 10)).issubset({-1.0, -0.2, 0.2, 1.0})


def test_features_are_causal_when_future_rows_change() -> None:
    bars = _bars()
    baseline = add_btcusd_dual_trend_30m_features(bars)
    changed = bars.copy()
    cutoff = 650
    changed.iloc[cutoff:, changed.columns.get_loc("close")] *= 1.5
    changed.iloc[cutoff:, changed.columns.get_loc("open")] *= 1.5
    changed.iloc[cutoff:, changed.columns.get_loc("high")] *= 1.5
    changed.iloc[cutoff:, changed.columns.get_loc("low")] *= 1.5
    modified = add_btcusd_dual_trend_30m_features(changed)
    causal_columns = [
        "log_close",
        "ema_fast",
        "ema_slow",
        "ema_signal",
        "prior_high",
        "prior_low",
        "donchian_state",
        "ensemble_signal",
        "close_log_return",
        "volatility_ann",
    ]
    pdt.assert_frame_equal(
        baseline.iloc[:cutoff][causal_columns],
        modified.iloc[:cutoff][causal_columns],
    )


def test_ema_adjust_false_and_exact_volatility_annualization() -> None:
    bars = _bars(30)
    result = add_btcusd_dual_trend_30m_features(
        bars,
        ema_fast_span=4,
        ema_slow_span=8,
        donchian_window=3,
        volatility_ewma_span=5,
    )
    log_close = np.log(bars["close"])
    pdt.assert_series_equal(
        result["ema_fast"],
        log_close.ewm(span=4, adjust=False).mean(),
        check_names=False,
    )
    expected_vol = log_close.diff().ewm(span=5, adjust=False).std() * np.sqrt(365 * 48)
    pdt.assert_series_equal(result["volatility_ann"], expected_vol, check_names=False)
