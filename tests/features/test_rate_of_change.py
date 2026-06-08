from __future__ import annotations

import pytest

from src.features.rate_of_change import add_rate_of_change

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_rate_of_change_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_rate_of_change(df, window=5, output_col="roc_custom")

    assert "roc_custom" in out.columns
    assert_no_mutation(add_rate_of_change, df, window=5, output_col="roc_custom")
    assert_has_finite_values(out["roc_custom"])
    assert out["roc_custom"].iloc[5] == pytest.approx(df["close"].iloc[5] / df["close"].iloc[0] - 1.0)


def test_rate_of_change_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_rate_of_change(synthetic_ohlcv().drop(columns=["close"]), window=5)


def test_rate_of_change_invalid_window() -> None:
    with pytest.raises(ValueError, match="window"):
        add_rate_of_change(synthetic_ohlcv(), window=-1)


def test_rate_of_change_is_causal() -> None:
    assert_causal(
        add_rate_of_change,
        synthetic_ohlcv(),
        output_cols=["roc_5"],
        params={"window": 5},
    )
