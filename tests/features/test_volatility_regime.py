from __future__ import annotations

import pytest

from src.features.volatility_regime import add_volatility_regime

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_volatility_regime_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_volatility_regime(df, vol_col="vol", regime_window=30, output_col="vol_regime")

    assert "vol_regime" in out.columns
    assert_no_mutation(add_volatility_regime, df, vol_col="vol", regime_window=30, output_col="vol_regime")
    assert_has_finite_values(out["vol_regime"])
    assert (out["vol_regime"].dropna() >= 0).all()


def test_volatility_regime_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_volatility_regime(synthetic_ohlcv().drop(columns=["vol"]), vol_col="vol")


def test_volatility_regime_invalid_params() -> None:
    with pytest.raises(ValueError, match="method"):
        add_volatility_regime(synthetic_ohlcv(), vol_col="vol", method="unknown")


def test_volatility_regime_is_causal() -> None:
    assert_causal(
        add_volatility_regime,
        synthetic_ohlcv(),
        output_cols=["volatility_regime"],
        params={"vol_col": "vol", "regime_window": 30},
    )
