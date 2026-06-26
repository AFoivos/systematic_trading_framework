from __future__ import annotations

import numpy as np
import pytest

from src.features.helpers import add_between_flag_transform, add_reciprocal_transform, add_rising_flag_transform
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
    assert "hilbert_dominant_cycle_32" not in out.columns
    assert "hilbert_cycle_ok_32" not in out.columns
    assert "hilbert_amplitude_rising_32" not in out.columns
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


def test_hilbert_transform_derived_columns_are_helpers() -> None:
    out = add_hilbert_transform(
        synthetic_ohlcv(),
        window=32,
        amplitude_col="hilbert_amplitude",
        phase_col="hilbert_phase",
        instantaneous_frequency_col="hilbert_instantaneous_frequency",
    )
    out = add_reciprocal_transform(
        out,
        source_col="hilbert_instantaneous_frequency",
        use_abs=True,
        output_col="hilbert_dominant_cycle",
    )
    out = add_between_flag_transform(
        out,
        source_col="hilbert_dominant_cycle",
        lower=10.0,
        upper=48.0,
        output_col="hilbert_cycle_ok",
    )
    out = add_rising_flag_transform(
        out,
        source_col="hilbert_amplitude",
        periods=3,
        output_col="hilbert_amplitude_rising",
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
    assert out["hilbert_cycle_ok"].dtype == "int8"
    assert out["hilbert_amplitude_rising"].dtype == "int8"


def test_hilbert_transform_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_hilbert_transform(synthetic_ohlcv().drop(columns=["close"]), window=32)


def test_hilbert_transform_invalid_params() -> None:
    with pytest.raises(ValueError, match="window"):
        add_hilbert_transform(synthetic_ohlcv(), window=3)

    with pytest.raises(ValueError, match="derived outputs"):
        add_hilbert_transform(synthetic_ohlcv(), window=32, add_derived=True)

    with pytest.raises(ValueError, match="derived outputs"):
        add_hilbert_transform(synthetic_ohlcv(), window=32, dominant_cycle_col="hilbert_dominant_cycle")


def test_hilbert_transform_is_causal() -> None:
    assert_causal(
        add_hilbert_transform,
        synthetic_ohlcv(),
        output_cols=[
            "hilbert_amplitude_32",
            "hilbert_phase_32",
            "hilbert_instantaneous_frequency_32",
        ],
        params={"window": 32},
    )
