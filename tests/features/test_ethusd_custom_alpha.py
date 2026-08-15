from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.ethusd_custom_alpha import (
    CUSTOM_ALPHA_OUTPUT_COLUMNS,
    add_ethusd_custom_alpha_features,
)
from src.features.registry import FEATURE_REGISTRY

from ._helpers import assert_causal, assert_no_mutation, synthetic_ohlcv


def test_custom_alpha_features_are_bounded_causal_and_registered() -> None:
    frame = synthetic_ohlcv(260)
    out = add_ethusd_custom_alpha_features(frame)

    assert set(CUSTOM_ALPHA_OUTPUT_COLUMNS).issubset(out.columns)
    assert FEATURE_REGISTRY["ethusd_custom_alpha"] is add_ethusd_custom_alpha_features
    assert out["laf_directional_flow"].dropna().between(-1.0, 1.0).all()
    assert out["pcp_consensus"].dropna().between(-1.0, 1.0).all()
    agreement = out["pcp_scale_agreement"].dropna().to_numpy(dtype=float)
    assert np.isclose(agreement * 3.0, np.round(agreement * 3.0)).all()
    assert pd.Series(agreement).between(1 / 3, 1.0).all()
    assert out["lad_absorption_divergence"].dropna().between(-1.0, 1.0).all()
    assert out["casc_score"].dropna().between(-1.0, 1.0).all()
    assert (out["causal_range_energy"].dropna() > 0.0).all()
    assert_causal(
        add_ethusd_custom_alpha_features,
        frame,
        output_cols=CUSTOM_ALPHA_OUTPUT_COLUMNS,
        cutoff=150,
        mutate_cols=["open", "high", "low", "close", "volume"],
    )
    assert_no_mutation(add_ethusd_custom_alpha_features, frame)


def test_flat_bars_are_safe_and_do_not_create_false_direction() -> None:
    index = pd.date_range("2025-01-01", periods=220, freq="30min")
    frame = pd.DataFrame(
        {
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 10.0,
        },
        index=index,
    )
    out = add_ethusd_custom_alpha_features(frame)

    assert out["laf_bar_acceptance"].eq(0.0).all()
    assert out["pcp_consensus"].dropna().empty
    assert out["casc_score"].dropna().empty
    assert out["causal_range_energy"].dropna().eq(0.0).all()


@pytest.mark.parametrize(
    "params",
    [
        {"flow_window": 0},
        {"path_windows": (4, 4, 12)},
        {"path_windows": (12, 4, 36)},
        {"path_windows": (4, 12)},
        {"eps": 0.0},
    ],
)
def test_invalid_custom_alpha_parameters_fail_closed(params: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        add_ethusd_custom_alpha_features(synthetic_ohlcv(), **params)
