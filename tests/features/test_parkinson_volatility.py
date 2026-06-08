from __future__ import annotations

import pytest

from src.features.parkinson_volatility import add_parkinson_volatility

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_parkinson_volatility_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_parkinson_volatility(df, window=20, output_col="pk_vol")

    assert "pk_vol" in out.columns
    assert_no_mutation(add_parkinson_volatility, df, window=20, output_col="pk_vol")
    assert_has_finite_values(out["pk_vol"])
    assert (out["pk_vol"].dropna() >= 0).all()


def test_parkinson_volatility_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_parkinson_volatility(synthetic_ohlcv().drop(columns=["high"]), window=20)


def test_parkinson_volatility_invalid_window() -> None:
    with pytest.raises(ValueError, match="window"):
        add_parkinson_volatility(synthetic_ohlcv(), window=0)


def test_parkinson_volatility_is_causal() -> None:
    assert_causal(
        add_parkinson_volatility,
        synthetic_ohlcv(),
        output_cols=["parkinson_vol_20"],
        params={"window": 20},
    )
