from __future__ import annotations

import pytest

from src.features.helpers import apply_feature_helpers
from src.features.roofing_filter import add_roofing_filter

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_roofing_filter_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_roofing_filter(df, high_pass_period=32, low_pass_period=8, output_col="roof")

    assert "roof" in out.columns
    assert_no_mutation(add_roofing_filter, df, high_pass_period=32, low_pass_period=8, output_col="roof")
    assert_has_finite_values(out["roof"])


def test_roofing_filter_emits_only_raw_filter_by_default() -> None:
    out = add_roofing_filter(
        synthetic_ohlcv(),
        high_pass_period=48,
        low_pass_period=10,
        slope_bars=3,
        output_col="roofing_filter",
    )

    derived = {
        "roofing_slope",
        "roofing_positive",
        "roofing_negative",
        "roofing_slope_positive",
        "roofing_slope_negative",
        "roofing_cross_up_zero",
        "roofing_cross_down_zero",
    }
    assert "roofing_filter" in out.columns
    assert not derived.intersection(out.columns)


def test_roofing_filter_rejects_legacy_derived_outputs() -> None:
    with pytest.raises(ValueError, match="feature transforms"):
        add_roofing_filter(
            synthetic_ohlcv(),
            high_pass_period=48,
            low_pass_period=10,
            output_col="roofing_filter",
            slope_col="roofing_slope",
        )


def test_roofing_filter_strategy_columns_are_helper_transforms() -> None:
    raw = add_roofing_filter(
        synthetic_ohlcv(),
        high_pass_period=48,
        low_pass_period=10,
        output_col="roofing_filter",
    )
    out = apply_feature_helpers(
        raw,
        transforms={
            "difference": {
                "source_col": "roofing_filter",
                "periods": 3,
                "output_col": "roofing_slope",
            },
            "threshold_flag": {
                "items": [
                    {"source_col": "roofing_filter", "threshold": 0.0, "op": "gt", "output_col": "roofing_positive"},
                    {"source_col": "roofing_filter", "threshold": 0.0, "op": "lt", "output_col": "roofing_negative"},
                    {"source_col": "roofing_slope", "threshold": 0.0, "op": "gt", "output_col": "roofing_slope_positive"},
                    {"source_col": "roofing_slope", "threshold": 0.0, "op": "lt", "output_col": "roofing_slope_negative"},
                ]
            },
            "crossing_flag": {
                "items": [
                    {
                        "source_col": "roofing_filter",
                        "threshold": 0.0,
                        "direction": "up",
                        "output_col": "roofing_cross_up_zero",
                    },
                    {
                        "source_col": "roofing_filter",
                        "threshold": 0.0,
                        "direction": "down",
                        "output_col": "roofing_cross_down_zero",
                    },
                ]
            },
        },
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
        assert str(out[column].dtype) == "int8"


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
        ],
        params={"high_pass_period": 32, "low_pass_period": 8},
    )
