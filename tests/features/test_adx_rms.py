from __future__ import annotations

import pytest

from src.features.adx_rms import add_adx_rms

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_adx_rms_contract_and_numeric_sanity_reuses_existing_adx() -> None:
    df = synthetic_ohlcv()
    out = add_adx_rms(df, adx_col="adx_14", window=10, output_col="adx_rms_custom")

    assert "adx_rms_custom" in out.columns
    assert_no_mutation(add_adx_rms, df, adx_col="adx_14", window=10, output_col="adx_rms_custom")
    assert_has_finite_values(out["adx_rms_custom"])
    assert (out["adx_rms_custom"].dropna() >= 0).all()


def test_adx_rms_missing_columns_when_computing_adx() -> None:
    df = synthetic_ohlcv().drop(columns=["adx_14", "high"])
    with pytest.raises(KeyError, match="Missing columns"):
        add_adx_rms(df, window=10)


def test_adx_rms_invalid_window() -> None:
    with pytest.raises(ValueError, match="window"):
        add_adx_rms(synthetic_ohlcv(), adx_col="adx_14", window=0)


def test_adx_rms_is_causal() -> None:
    assert_causal(
        add_adx_rms,
        synthetic_ohlcv(),
        output_cols=["adx_rms_10"],
        params={"adx_col": "adx_14", "window": 10},
    )
