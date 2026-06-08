from __future__ import annotations

import pytest

from src.features.permutation_entropy import add_permutation_entropy

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_permutation_entropy_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_permutation_entropy(df, window=32, order=3, delay=1, output_col="perm_entropy")

    assert "perm_entropy" in out.columns
    assert_no_mutation(add_permutation_entropy, df, window=32, order=3, delay=1, output_col="perm_entropy")
    assert_has_finite_values(out["perm_entropy"])
    assert ((out["perm_entropy"].dropna() >= 0) & (out["perm_entropy"].dropna() <= 1)).all()


def test_permutation_entropy_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_permutation_entropy(synthetic_ohlcv().drop(columns=["close"]), window=32)


def test_permutation_entropy_invalid_params() -> None:
    with pytest.raises(ValueError, match="window"):
        add_permutation_entropy(synthetic_ohlcv(), window=2, order=4, delay=1)


def test_permutation_entropy_is_causal() -> None:
    assert_causal(
        add_permutation_entropy,
        synthetic_ohlcv(),
        output_cols=["permutation_entropy_32"],
        params={"window": 32, "order": 3, "delay": 1},
    )
