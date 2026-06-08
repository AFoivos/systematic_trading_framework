from __future__ import annotations

import pytest

from src.features.hurst_exponent import add_hurst_exponent

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_hurst_exponent_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_hurst_exponent(df, window=64, max_lag=12, output_col="hurst_custom")

    assert "hurst_custom" in out.columns
    assert_no_mutation(add_hurst_exponent, df, window=64, max_lag=12, output_col="hurst_custom")
    assert_has_finite_values(out["hurst_custom"])
    assert ((out["hurst_custom"].dropna() >= 0) & (out["hurst_custom"].dropna() <= 1)).all()


def test_hurst_exponent_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_hurst_exponent(synthetic_ohlcv().drop(columns=["close"]), window=64)


def test_hurst_exponent_invalid_params() -> None:
    with pytest.raises(ValueError, match="max_lag"):
        add_hurst_exponent(synthetic_ohlcv(), window=32, max_lag=32)


def test_hurst_exponent_is_causal() -> None:
    assert_causal(
        add_hurst_exponent,
        synthetic_ohlcv(),
        output_cols=["hurst_64"],
        params={"window": 64, "max_lag": 12},
    )
