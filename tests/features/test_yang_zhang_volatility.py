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


def test_yang_zhang_volatility_optional_regime_outputs() -> None:
    df = synthetic_ohlcv()
    out = add_yang_zhang_volatility(
        df,
        window=20,
        regime_window=30,
        high_vol_mult=1.05,
        output_col="yz_vol",
        rolling_mean_col="yz_mean",
        ratio_col="yz_ratio",
        rising_col="yz_rising",
        high_vol_regime_col="yz_high",
    )

    assert {"yz_vol", "yz_mean", "yz_ratio", "yz_rising", "yz_high"}.issubset(out.columns)
    assert_has_finite_values(out["yz_mean"])
    assert_has_finite_values(out["yz_ratio"])
    assert str(out["yz_rising"].dtype) == "int8"
    assert str(out["yz_high"].dtype) == "int8"
    assert set(out["yz_rising"].unique()).issubset({0, 1})
    assert set(out["yz_high"].unique()).issubset({0, 1})


def test_yang_zhang_volatility_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_yang_zhang_volatility(synthetic_ohlcv().drop(columns=["close"]), window=20)


def test_yang_zhang_volatility_invalid_window() -> None:
    with pytest.raises(ValueError, match="window"):
        add_yang_zhang_volatility(synthetic_ohlcv(), window=1)
    with pytest.raises(ValueError, match="regime_window"):
        add_yang_zhang_volatility(
            synthetic_ohlcv(),
            window=20,
            rolling_mean_col="yz_mean",
        )


def test_yang_zhang_volatility_is_causal() -> None:
    assert_causal(
        add_yang_zhang_volatility,
        synthetic_ohlcv(),
        output_cols=["yang_zhang_vol_20"],
        params={"window": 20},
    )
