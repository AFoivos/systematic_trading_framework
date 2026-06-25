from __future__ import annotations

import pytest

from src.features.technical.roc import add_roc_features

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_roc_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_roc_features(df, window=5, output_col="roc_custom")

    assert "roc_custom" in out.columns
    assert_no_mutation(add_roc_features, df, window=5, output_col="roc_custom")
    assert_has_finite_values(out["roc_custom"])
    assert out["roc_custom"].iloc[5] == pytest.approx(df["close"].iloc[5] / df["close"].iloc[0] - 1.0)


def test_roc_missing_columns() -> None:
    with pytest.raises(KeyError, match="price_col"):
        add_roc_features(synthetic_ohlcv().drop(columns=["close"]), window=5)


def test_roc_invalid_window() -> None:
    with pytest.raises(ValueError, match="window"):
        add_roc_features(synthetic_ohlcv(), window=-1)


def test_roc_is_causal() -> None:
    assert_causal(
        add_roc_features,
        synthetic_ohlcv(),
        output_cols=["roc_5"],
        params={"window": 5},
    )
