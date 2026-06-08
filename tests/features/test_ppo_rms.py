from __future__ import annotations

import pytest

from src.features.ppo_rms import add_ppo_rms

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_ppo_rms_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_ppo_rms(df, source_col="ppo_hist", window=12, output_col="ppo_rms_custom")

    assert "ppo_rms_custom" in out.columns
    assert_no_mutation(add_ppo_rms, df, source_col="ppo_hist", window=12, output_col="ppo_rms_custom")
    assert_has_finite_values(out["ppo_rms_custom"])
    assert (out["ppo_rms_custom"].dropna() >= 0).all()


def test_ppo_rms_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_ppo_rms(synthetic_ohlcv().drop(columns=["ppo_hist"]), source_col="ppo_hist", window=12)


def test_ppo_rms_invalid_params() -> None:
    with pytest.raises(ValueError, match="fast"):
        add_ppo_rms(synthetic_ohlcv(), source_col=None, fast=30, slow=20)


def test_ppo_rms_is_causal() -> None:
    assert_causal(
        add_ppo_rms,
        synthetic_ohlcv(),
        output_cols=["ppo_rms_12"],
        params={"source_col": "ppo_hist", "window": 12},
    )
