from __future__ import annotations

import pytest

from src.features.vpin import add_vpin

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_vpin_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_vpin(df, window=20, output_col="vpin_custom")

    assert "vpin_custom" in out.columns
    assert_no_mutation(add_vpin, df, window=20, output_col="vpin_custom")
    assert_has_finite_values(out["vpin_custom"])
    assert ((out["vpin_custom"].dropna() >= 0) & (out["vpin_custom"].dropna() <= 1)).all()


def test_vpin_missing_real_volume_columns() -> None:
    df = synthetic_ohlcv().drop(columns=["buy_volume", "sell_volume", "signed_volume"])
    with pytest.raises(KeyError, match="VPIN"):
        add_vpin(df, buy_volume_col="buy_volume", sell_volume_col="sell_volume", signed_volume_col=None)


def test_vpin_invalid_params() -> None:
    with pytest.raises(ValueError, match="window"):
        add_vpin(synthetic_ohlcv(), window=0)


def test_vpin_is_causal() -> None:
    assert_causal(
        add_vpin,
        synthetic_ohlcv(),
        output_cols=["vpin_20"],
        params={"window": 20},
        mutate_cols=["buy_volume", "sell_volume", "signed_volume", "volume"],
    )
