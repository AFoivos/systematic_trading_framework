from __future__ import annotations

import pytest

from src.features.garman_klass_volatility import add_garman_klass_volatility

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_garman_klass_volatility_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_garman_klass_volatility(df, window=20, output_col="gk_vol")

    assert "gk_vol" in out.columns
    assert_no_mutation(add_garman_klass_volatility, df, window=20, output_col="gk_vol")
    assert_has_finite_values(out["gk_vol"])
    assert (out["gk_vol"].dropna() >= 0).all()


def test_garman_klass_volatility_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_garman_klass_volatility(synthetic_ohlcv().drop(columns=["open"]), window=20)


def test_garman_klass_volatility_invalid_window() -> None:
    with pytest.raises(ValueError, match="window"):
        add_garman_klass_volatility(synthetic_ohlcv(), window=False)


def test_garman_klass_volatility_is_causal() -> None:
    assert_causal(
        add_garman_klass_volatility,
        synthetic_ohlcv(),
        output_cols=["garman_klass_vol_20"],
        params={"window": 20},
    )
