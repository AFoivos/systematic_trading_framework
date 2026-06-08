from __future__ import annotations

import pytest

from src.features.supersmoother import add_supersmoother

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_supersmoother_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_supersmoother(df, period=10, output_col="smooth")

    assert "smooth" in out.columns
    assert_no_mutation(add_supersmoother, df, period=10, output_col="smooth")
    assert_has_finite_values(out["smooth"])


def test_supersmoother_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_supersmoother(synthetic_ohlcv().drop(columns=["close"]), period=10)


def test_supersmoother_invalid_params() -> None:
    with pytest.raises(ValueError, match="period"):
        add_supersmoother(synthetic_ohlcv(), period=1)


def test_supersmoother_is_causal() -> None:
    assert_causal(
        add_supersmoother,
        synthetic_ohlcv(),
        output_cols=["supersmoother_10"],
        params={"period": 10},
    )
