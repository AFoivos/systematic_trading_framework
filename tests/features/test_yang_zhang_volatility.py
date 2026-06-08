from __future__ import annotations

import pytest

from src.features.yang_zhang_volatility import add_yang_zhang_volatility

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_yang_zhang_volatility_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_yang_zhang_volatility(df, window=20, output_col="yz_vol")

    assert "yz_vol" in out.columns
    assert_no_mutation(add_yang_zhang_volatility, df, window=20, output_col="yz_vol")
    assert_has_finite_values(out["yz_vol"])
    assert (out["yz_vol"].dropna() >= 0).all()


def test_yang_zhang_volatility_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_yang_zhang_volatility(synthetic_ohlcv().drop(columns=["close"]), window=20)


def test_yang_zhang_volatility_invalid_window() -> None:
    with pytest.raises(ValueError, match="window"):
        add_yang_zhang_volatility(synthetic_ohlcv(), window=1)


def test_yang_zhang_volatility_is_causal() -> None:
    assert_causal(
        add_yang_zhang_volatility,
        synthetic_ohlcv(),
        output_cols=["yang_zhang_vol_20"],
        params={"window": 20},
    )
