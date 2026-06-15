from __future__ import annotations

import numpy as np
import pytest

from src.features.hilbert_transform import add_hilbert_transform

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_hilbert_transform_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_hilbert_transform(
        df,
        window=32,
        amplitude_col="amp",
        phase_col="phase",
        instantaneous_frequency_col="freq",
    )

    assert {"amp", "phase", "freq"}.issubset(out.columns)
    assert_no_mutation(
        add_hilbert_transform,
        df,
        window=32,
        amplitude_col="amp",
        phase_col="phase",
        instantaneous_frequency_col="freq",
    )
    assert_has_finite_values(out["amp"])
    assert (out["amp"].dropna() >= 0).all()
    assert np.isfinite(out["freq"].dropna()).all()


def test_hilbert_transform_emits_strategy_compatibility_columns() -> None:
    out = add_hilbert_transform(
        synthetic_ohlcv(),
        window=32,
        amplitude_col="hilbert_amplitude",
        phase_col="hilbert_phase",
        instantaneous_frequency_col="hilbert_instantaneous_frequency",
        dominant_cycle_col="hilbert_dominant_cycle",
        cycle_ok_col="hilbert_cycle_ok",
        amplitude_rising_col="hilbert_amplitude_rising",
        min_cycle=10,
        max_cycle=48,
        amplitude_slope_bars=3,
    )

    expected = {
        "hilbert_amplitude",
        "hilbert_phase",
        "hilbert_instantaneous_frequency",
        "hilbert_dominant_cycle",
        "hilbert_cycle_ok",
        "hilbert_amplitude_rising",
    }
    assert expected.issubset(out.columns)
    assert_has_finite_values(out["hilbert_dominant_cycle"])
    assert out["hilbert_cycle_ok"].dtype == bool
    assert out["hilbert_amplitude_rising"].dtype == bool


def test_hilbert_transform_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_hilbert_transform(synthetic_ohlcv().drop(columns=["close"]), window=32)


def test_hilbert_transform_invalid_params() -> None:
    with pytest.raises(ValueError, match="window"):
        add_hilbert_transform(synthetic_ohlcv(), window=3)


def test_hilbert_transform_is_causal() -> None:
    assert_causal(
        add_hilbert_transform,
        synthetic_ohlcv(),
        output_cols=[
            "hilbert_amplitude_32",
            "hilbert_phase_32",
            "hilbert_instantaneous_frequency_32",
            "hilbert_dominant_cycle_32",
            "hilbert_cycle_ok_32",
            "hilbert_amplitude_rising_32",
        ],
        params={"window": 32},
    )
