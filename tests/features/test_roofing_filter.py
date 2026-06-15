from __future__ import annotations

import pytest

from src.features.roofing_filter import add_roofing_filter

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_roofing_filter_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_roofing_filter(df, high_pass_period=32, low_pass_period=8, output_col="roof")

    assert "roof" in out.columns
    assert_no_mutation(add_roofing_filter, df, high_pass_period=32, low_pass_period=8, output_col="roof")
    assert_has_finite_values(out["roof"])


def test_roofing_filter_emits_stable_strategy_derived_columns() -> None:
    out = add_roofing_filter(
        synthetic_ohlcv(),
        high_pass_period=48,
        low_pass_period=10,
        slope_bars=3,
        output_col="roofing_filter",
    )

    expected = {
        "roofing_filter",
        "roofing_slope",
        "roofing_positive",
        "roofing_negative",
        "roofing_slope_positive",
        "roofing_slope_negative",
        "roofing_cross_up_zero",
        "roofing_cross_down_zero",
    }
    assert expected.issubset(out.columns)
    assert_has_finite_values(out["roofing_slope"])
    for column in expected - {"roofing_filter", "roofing_slope"}:
        assert out[column].dtype == bool


def test_roofing_filter_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_roofing_filter(synthetic_ohlcv().drop(columns=["close"]))


def test_roofing_filter_invalid_params() -> None:
    with pytest.raises(ValueError, match="greater"):
        add_roofing_filter(synthetic_ohlcv(), high_pass_period=8, low_pass_period=8)


def test_roofing_filter_is_causal() -> None:
    assert_causal(
        add_roofing_filter,
        synthetic_ohlcv(),
        output_cols=[
            "roofing_filter_32_8",
            "roofing_filter_32_8_slope",
            "roofing_filter_32_8_positive",
            "roofing_filter_32_8_negative",
            "roofing_filter_32_8_slope_positive",
            "roofing_filter_32_8_slope_negative",
            "roofing_filter_32_8_cross_up_zero",
            "roofing_filter_32_8_cross_down_zero",
        ],
        params={"high_pass_period": 32, "low_pass_period": 8},
    )
