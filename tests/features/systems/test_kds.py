from __future__ import annotations

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from src.features.systems.kds import KDS_OUTPUT_COLUMNS, add_kds_features

from .conftest import make_fallback_m1


def test_kds_contract_invariants_and_no_mutation(
    fallback_m1: pd.DataFrame,
    short_kds_config: dict[str, object],
) -> None:
    before = fallback_m1.copy(deep=True)
    out = add_kds_features(fallback_m1, config=short_kds_config)

    pdt.assert_frame_equal(fallback_m1, before)
    assert out.index.equals(fallback_m1.index)
    assert set(KDS_OUTPUT_COLUMNS).issubset(out.columns)
    finite = out[list(KDS_OUTPUT_COLUMNS)].select_dtypes(include=[np.number]).to_numpy(dtype=float)
    assert not np.isinf(finite).any()

    assert out["kalman_prob_up"].dropna().between(0.0, 1.0).all()
    assert out["kdi_activity"].dropna().between(0.0, 1.0).all()
    assert out["kdi_plus"].dropna().between(0.0, 100.0).all()
    assert out["kdi_minus"].dropna().between(0.0, 100.0).all()
    assert out["kdx"].dropna().between(0.0, 100.0).all()
    assert out["kadx"].dropna().between(0.0, 100.0).all()
    assert out["kadx_signed"].dropna().between(-100.0, 100.0).all()
    assert out["ktrend_score"].dropna().between(-1.0, 1.0).all()
    active = out["kdi_activity"].notna()
    np.testing.assert_allclose(
        (out.loc[active, "kdi_plus"] + out.loc[active, "kdi_minus"]).to_numpy(),
        (100.0 * out.loc[active, "kdi_activity"]).to_numpy(),
        rtol=1e-6,
        atol=1e-10,
    )


def test_kds_prefix_and_appended_data_invariance(
    fallback_m1: pd.DataFrame,
    short_kds_config: dict[str, object],
) -> None:
    cutoff = 260
    prefix = add_kds_features(fallback_m1.iloc[:cutoff], config=short_kds_config)
    full = add_kds_features(fallback_m1, config=short_kds_config)

    pdt.assert_frame_equal(
        prefix[list(KDS_OUTPUT_COLUMNS)],
        full.iloc[:cutoff][list(KDS_OUTPUT_COLUMNS)],
        check_exact=True,
    )


def test_kds_shifted_spread_baseline_excludes_current_spike(
    fallback_m1: pd.DataFrame,
    short_kds_config: dict[str, object],
) -> None:
    frame = fallback_m1.copy()
    spike_position = 120
    frame.iloc[spike_position, frame.columns.get_loc("spread_bps")] = 100.0
    out = add_kds_features(frame, config=short_kds_config)

    historical = frame["spread_bps"].iloc[spike_position - 24 : spike_position].median()
    expected = 100.0 / (historical + float(short_kds_config.get("epsilon", 1e-12)))
    assert out["spread_ratio"].iloc[spike_position] == pytest.approx(expected)


def test_kds_synthetic_direction_and_constant_behavior(
    short_kds_config: dict[str, object],
) -> None:
    upward = add_kds_features(
        make_fallback_m1(360, drift=2.0e-5, noise_scale=0.0),
        config=short_kds_config,
    )
    downward = add_kds_features(
        make_fallback_m1(360, drift=-2.0e-5, noise_scale=0.0),
        config=short_kds_config,
    )
    constant = make_fallback_m1(360, drift=0.0, noise_scale=0.0)
    constant[["open", "high", "low", "close"]] = 1.10
    flat = add_kds_features(constant, config=short_kds_config)

    assert upward["kalman_drift"].iloc[-1] > 0.0
    assert upward["kdi_plus"].iloc[-1] > upward["kdi_minus"].iloc[-1]
    assert upward["ktrend_score"].iloc[-1] > 0.0
    assert downward["kalman_drift"].iloc[-1] < 0.0
    assert downward["kdi_minus"].iloc[-1] > downward["kdi_plus"].iloc[-1]
    assert downward["ktrend_score"].iloc[-1] < 0.0
    assert abs(float(flat["kalman_drift"].iloc[-1])) < 1e-9
    assert float(flat["kdi_activity"].iloc[-1]) < 1e-6


def test_kds_spread_spike_reduces_equivalent_observation_response(
    fallback_m1: pd.DataFrame,
    short_kds_config: dict[str, object],
) -> None:
    jump_position = 150
    normal = fallback_m1.copy()
    wide = fallback_m1.copy()
    for frame in (normal, wide):
        factor = 1.003
        frame.iloc[jump_position:, frame.columns.get_loc("close")] *= factor
        frame.iloc[jump_position:, frame.columns.get_loc("high")] *= factor
    wide.iloc[jump_position, wide.columns.get_loc("spread_bps")] = 100.0

    normal_out = add_kds_features(normal, config=short_kds_config)
    wide_out = add_kds_features(wide, config=short_kds_config)

    prior_level = float(normal_out["kalman_level"].iloc[jump_position - 1])
    normal_move = abs(float(normal_out["kalman_level"].iloc[jump_position]) - prior_level)
    wide_move = abs(float(wide_out["kalman_level"].iloc[jump_position]) - prior_level)
    assert wide_move < normal_move


def test_kds_empty_all_nan_and_isolated_nan(
    short_kds_config: dict[str, object],
) -> None:
    index = pd.DatetimeIndex([], tz="UTC")
    empty = pd.DataFrame(columns=["open", "high", "low", "close"], index=index, dtype=float)
    empty_out = add_kds_features(empty, config=short_kds_config)
    assert empty_out.empty
    assert set(KDS_OUTPUT_COLUMNS).issubset(empty_out.columns)

    nan_index = pd.date_range("2025-01-01", periods=20, freq="min", tz="UTC")
    all_nan = pd.DataFrame(
        np.nan,
        index=nan_index,
        columns=["open", "high", "low", "close"],
    )
    nan_out = add_kds_features(all_nan, config=short_kds_config)
    assert nan_out[list(KDS_OUTPUT_COLUMNS)].isna().all().all()

    frame = make_fallback_m1(120)
    frame.loc[frame.index[60], ["open", "high", "low", "close"]] = np.nan
    isolated = add_kds_features(frame, config=short_kds_config)
    assert np.isnan(isolated.loc[frame.index[60], "kalman_innovation"])
    assert np.isfinite(isolated.loc[frame.index[61], "kalman_level"])


def test_kds_rejects_non_finite_config(fallback_m1: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="finite"):
        add_kds_features(fallback_m1, config={"huber_threshold": np.inf})
