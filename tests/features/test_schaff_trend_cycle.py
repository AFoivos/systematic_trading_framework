from __future__ import annotations

import numpy as np
import pytest

from src.features.helpers import (
    add_crossing_flag_transform,
    add_difference_transform,
    add_rising_flag_transform,
    add_threshold_flag_transform,
)
from src.features.technical.schaff_trend_cycle import (
    add_schaff_trend_cycle_features,
    compute_schaff_trend_cycle,
)

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_schaff_trend_cycle_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv(n=260)
    out = add_schaff_trend_cycle_features(df)

    expected = {
        "stc",
        "stc_signal",
    }
    assert expected.issubset(out.columns)
    assert {"stc_cross_up_25", "stc_cross_down_75", "stc_rising", "stc_falling"}.isdisjoint(out.columns)
    assert len(out) == len(df)
    assert_no_mutation(add_schaff_trend_cycle_features, df)
    assert_has_finite_values(out["stc"])
    assert out["stc"].dropna().between(0.0, 100.0).all()


def test_schaff_trend_cycle_derived_columns_are_helpers() -> None:
    out = add_schaff_trend_cycle_features(synthetic_ohlcv(n=260))
    out = add_crossing_flag_transform(
        out,
        source_col="stc",
        threshold=25.0,
        direction="up",
        output_col="stc_cross_up_25",
    )
    out = add_crossing_flag_transform(
        out,
        source_col="stc",
        threshold=75.0,
        direction="down",
        output_col="stc_cross_down_75",
    )
    out = add_rising_flag_transform(out, source_col="stc", output_col="stc_rising")
    out = add_difference_transform(out, source_col="stc", output_col="stc_delta_1")
    out = add_threshold_flag_transform(
        out,
        source_col="stc_delta_1",
        threshold=0.0,
        op="lt",
        output_col="stc_falling",
    )

    assert {
        "stc_cross_up_25",
        "stc_cross_down_75",
        "stc_rising",
        "stc_delta_1",
        "stc_falling",
    }.issubset(out.columns)
    assert out["stc_cross_up_25"].dtype == "int8"
    assert out["stc_cross_down_75"].dtype == "int8"
    assert out["stc_rising"].dtype == "int8"
    assert out["stc_falling"].dtype == "int8"


def test_compute_schaff_trend_cycle_requires_series() -> None:
    with pytest.raises(TypeError, match="Series"):
        compute_schaff_trend_cycle(np.arange(20, dtype=float))  # type: ignore[arg-type]


def test_schaff_trend_cycle_invalid_params() -> None:
    with pytest.raises(ValueError, match="fast must be less than slow"):
        add_schaff_trend_cycle_features(synthetic_ohlcv(), fast=50, slow=23)

    with pytest.raises(ValueError, match="long_cross_level"):
        add_schaff_trend_cycle_features(synthetic_ohlcv(), long_cross_level=80, short_cross_level=75)

    with pytest.raises(ValueError, match="derived outputs"):
        add_schaff_trend_cycle_features(synthetic_ohlcv(), cross_up_col="stc_cross_up_25")


def test_schaff_trend_cycle_is_causal() -> None:
    assert_causal(
        add_schaff_trend_cycle_features,
        synthetic_ohlcv(n=260),
        output_cols=[
            "stc",
            "stc_signal",
        ],
        params={"fast": 23, "slow": 50, "cycle": 10, "smooth": 3},
    )
