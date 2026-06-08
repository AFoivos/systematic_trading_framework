from __future__ import annotations

import pytest

from src.features.zscore_momentum import add_zscore_momentum

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_zscore_momentum_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_zscore_momentum(df, window=20, output_col="z_mom")

    assert "z_mom" in out.columns
    assert_no_mutation(add_zscore_momentum, df, window=20, output_col="z_mom")
    assert_has_finite_values(out["z_mom"])


def test_zscore_momentum_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_zscore_momentum(synthetic_ohlcv().drop(columns=["close"]), window=20)


def test_zscore_momentum_invalid_window() -> None:
    with pytest.raises(ValueError, match="window"):
        add_zscore_momentum(synthetic_ohlcv(), window=1)


def test_zscore_momentum_is_causal() -> None:
    assert_causal(
        add_zscore_momentum,
        synthetic_ohlcv(),
        output_cols=["zscore_momentum_20"],
        params={"window": 20},
    )
