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
        output_cols=["roofing_filter_32_8"],
        params={"high_pass_period": 32, "low_pass_period": 8},
    )
