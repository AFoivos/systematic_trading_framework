from __future__ import annotations

import pytest

from src.features.shannon_entropy import add_shannon_entropy

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_shannon_entropy_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_shannon_entropy(df, window=32, bins=8, output_col="entropy")

    assert "entropy" in out.columns
    assert_no_mutation(add_shannon_entropy, df, window=32, bins=8, output_col="entropy")
    assert_has_finite_values(out["entropy"])
    assert ((out["entropy"].dropna() >= 0) & (out["entropy"].dropna() <= 1)).all()


def test_shannon_entropy_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_shannon_entropy(synthetic_ohlcv().drop(columns=["close"]), window=32)


def test_shannon_entropy_invalid_params() -> None:
    with pytest.raises(ValueError, match="bins"):
        add_shannon_entropy(synthetic_ohlcv(), window=32, bins=1)


def test_shannon_entropy_is_causal() -> None:
    assert_causal(
        add_shannon_entropy,
        synthetic_ohlcv(),
        output_cols=["shannon_entropy_32"],
        params={"window": 32, "bins": 8},
    )
