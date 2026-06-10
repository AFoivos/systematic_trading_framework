from __future__ import annotations

import pytest

from src.features.hmm_regime import add_hmm_regime

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_hmm_regime_contract_and_numeric_sanity_static_train() -> None:
    df = synthetic_ohlcv(90)
    out = add_hmm_regime(
        df,
        feature_cols=["returns"],
        mode="static_train",
        train_size=35,
        n_states=2,
        include_probabilities=True,
        output_col="hmm_custom",
    )

    assert "hmm_custom" in out.columns
    assert "hmm_regime_prob_0" in out.columns
    assert_no_mutation(
        add_hmm_regime,
        df,
        feature_cols=["returns"],
        mode="static_train",
        train_size=35,
        n_states=2,
        output_col="hmm_custom",
    )
    assert_has_finite_values(out["hmm_custom"])
    assert set(out["hmm_custom"].dropna().unique()).issubset({0.0, 1.0})


def test_hmm_regime_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_hmm_regime(synthetic_ohlcv().drop(columns=["returns"]), feature_cols=["returns"], mode="expanding")


def test_hmm_regime_invalid_params() -> None:
    with pytest.raises(ValueError, match="mode"):
        add_hmm_regime(synthetic_ohlcv(), feature_cols=["returns"], mode="bad")

def test_hmm_regime_is_causal() -> None:
    assert_causal(
        add_hmm_regime,
        synthetic_ohlcv(90),
        output_cols=["hmm_regime"],
        params={
            "feature_cols": ["returns"],
            "mode": "static_train",
            "train_size": 35,
            "n_states": 2,
        },
        cutoff=60,
        mutate_cols=["returns"],
    )
