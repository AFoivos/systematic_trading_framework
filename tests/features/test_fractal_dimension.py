from __future__ import annotations

import pytest

from src.features.fractal_dimension import add_fractal_dimension

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_fractal_dimension_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_fractal_dimension(df, window=32, output_col="fd")

    assert "fd" in out.columns
    assert_no_mutation(add_fractal_dimension, df, window=32, output_col="fd")
    assert_has_finite_values(out["fd"])
    assert (out["fd"].dropna() >= 1).all()


def test_fractal_dimension_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_fractal_dimension(synthetic_ohlcv().drop(columns=["close"]), window=32)


def test_fractal_dimension_invalid_window() -> None:
    with pytest.raises(ValueError, match="window"):
        add_fractal_dimension(synthetic_ohlcv(), window=1)


def test_fractal_dimension_is_causal() -> None:
    assert_causal(
        add_fractal_dimension,
        synthetic_ohlcv(),
        output_cols=["fractal_dimension_32"],
        params={"window": 32},
    )
