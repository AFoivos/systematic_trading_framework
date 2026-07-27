from __future__ import annotations

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from src.features.systems.kds import add_kds_features
from src.features.systems.lmds import (
    LMDS_OUTPUT_COLUMNS,
    add_lmds_features,
)
from src.features.systems.quant_market_state import (
    QMS_OUTPUT_COLUMNS,
    add_quant_market_state_features,
)
from src.features.systems.rlvs import add_rlvs_features

from .conftest import make_fallback_m1


def _dependencies(
    frame: pd.DataFrame,
    *,
    kds_config: dict[str, object],
    rlvs_config: dict[str, object],
) -> pd.DataFrame:
    return add_rlvs_features(
        add_kds_features(frame, config=kds_config),
        config=rlvs_config,
    )


def _decelerating_uptrend(periods: int = 480) -> pd.DataFrame:
    index = pd.date_range("2025-03-01", periods=periods, freq="min", tz="UTC")
    increments = np.linspace(4.0e-5, 2.0e-6, periods)
    close = 1.10 * np.exp(np.cumsum(increments))
    open_ = np.r_[close[0], close[:-1]]
    half_range = close * 2.0e-5
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + half_range,
            "low": np.minimum(open_, close) - half_range,
            "close": close,
            "spread_bps": 0.8,
        },
        index=index,
    )


def test_lmds_contract_invariants_and_no_mutation(
    fallback_m1: pd.DataFrame,
    short_kds_config: dict[str, object],
    short_rlvs_config: dict[str, object],
) -> None:
    featured = _dependencies(
        fallback_m1,
        kds_config=short_kds_config,
        rlvs_config=short_rlvs_config,
    )
    before = featured.copy(deep=True)
    out = add_lmds_features(featured)

    pdt.assert_frame_equal(featured, before)
    assert out.index.equals(featured.index)
    assert set(LMDS_OUTPUT_COLUMNS).issubset(out.columns)
    numeric = out[list(LMDS_OUTPUT_COLUMNS)].to_numpy(dtype=float)
    assert not np.isinf(numeric).any()
    assert out["lmom_score"].dropna().between(-1.0, 1.0).all()
    assert out["lmom_breadth"].dropna().between(-1.0, 1.0).all()
    assert out["lmom_efficiency"].dropna().between(0.0, 1.0).all()
    assert out["lmom_activity"].dropna().between(0.0, 1.0).all()
    assert out["lmom_plus"].dropna().between(0.0, 100.0).all()
    assert out["lmom_minus"].dropna().between(0.0, 100.0).all()
    assert out["lmom_strength"].dropna().between(0.0, 100.0).all()
    assert out["lmom_exhaustion"].dropna().between(0.0, 1.0).all()
    assert out["lmom_alignment"].dropna().between(-1.0, 1.0).all()
    ready = out["lmom_activity"].notna()
    np.testing.assert_allclose(
        out.loc[ready, "lmom_strength"],
        100.0 * out.loc[ready, "lmom_activity"],
        rtol=0.0,
        atol=1e-10,
    )


def test_lmds_prefix_invariance(
    fallback_m1: pd.DataFrame,
    short_kds_config: dict[str, object],
    short_rlvs_config: dict[str, object],
) -> None:
    featured = _dependencies(
        fallback_m1,
        kds_config=short_kds_config,
        rlvs_config=short_rlvs_config,
    )
    cutoff = 320
    prefix = add_lmds_features(featured.iloc[:cutoff])
    full = add_lmds_features(featured)

    pdt.assert_frame_equal(
        prefix[list(LMDS_OUTPUT_COLUMNS)],
        full.iloc[:cutoff][list(LMDS_OUTPUT_COLUMNS)],
        check_exact=True,
    )


def test_lmds_accelerating_and_decelerating_trends(
    short_kds_config: dict[str, object],
    short_rlvs_config: dict[str, object],
) -> None:
    accelerating = _dependencies(
        make_fallback_m1(
            480,
            drift=2e-6,
            acceleration=6e-8,
            noise_scale=0.0,
        ),
        kds_config=short_kds_config,
        rlvs_config=short_rlvs_config,
    )
    decelerating = _dependencies(
        _decelerating_uptrend(),
        kds_config=short_kds_config,
        rlvs_config=short_rlvs_config,
    )
    accelerating_out = add_lmds_features(accelerating)
    decelerating_out = add_lmds_features(decelerating)

    assert accelerating_out["lmom_acceleration"].iloc[-30:].median() > 0.0
    assert accelerating_out["lmom_score"].iloc[-30:].median() > 0.0
    assert accelerating_out["lmom_activity"].iloc[-30:].median() > 0.0
    assert decelerating_out["ktrend_score"].iloc[-30:].median() > 0.0
    assert decelerating_out["lmom_acceleration"].iloc[-30:].median() < 0.0
    assert decelerating_out["lmom_divergence"].iloc[-30:].median() < 0.0


def test_lmds_constant_price_is_neutral(
    short_kds_config: dict[str, object],
    short_rlvs_config: dict[str, object],
) -> None:
    frame = make_fallback_m1(300, drift=0.0, noise_scale=0.0)
    frame[["open", "high", "low", "close"]] = 1.10
    out = add_lmds_features(
        _dependencies(
            frame,
            kds_config=short_kds_config,
            rlvs_config=short_rlvs_config,
        )
    )

    assert out["lmom_impulse"].iloc[-1] == pytest.approx(0.0)
    assert out["lmom_efficiency"].iloc[-1] == pytest.approx(0.0)
    assert out["lmom_activity"].iloc[-1] == pytest.approx(0.0)
    assert out["lmom_score"].iloc[-1] == pytest.approx(0.0)


def test_lmds_mean_reverting_path_has_low_efficiency(
    short_kds_config: dict[str, object],
    short_rlvs_config: dict[str, object],
) -> None:
    frame = make_fallback_m1(480, drift=0.0, noise_scale=0.0)
    alternating_close = 1.10 * np.exp(2.5e-4 * (-1.0) ** np.arange(len(frame)))
    alternating_open = np.r_[alternating_close[0], alternating_close[:-1]]
    frame["close"] = alternating_close
    frame["open"] = alternating_open
    frame["high"] = np.maximum(alternating_open, alternating_close) * 1.00002
    frame["low"] = np.minimum(alternating_open, alternating_close) * 0.99998
    out = add_lmds_features(
        _dependencies(
            frame,
            kds_config=short_kds_config,
            rlvs_config=short_rlvs_config,
        )
    )

    assert out["lmom_efficiency"].iloc[-100:].median() < 0.5


def test_lmds_requires_precomputed_kds_and_rlvs(fallback_m1: pd.DataFrame) -> None:
    with pytest.raises(KeyError, match="dependencies"):
        add_lmds_features(fallback_m1)


def test_lmds_rejects_invalid_weights(
    fallback_m1: pd.DataFrame,
    short_kds_config: dict[str, object],
    short_rlvs_config: dict[str, object],
) -> None:
    featured = _dependencies(
        fallback_m1,
        kds_config=short_kds_config,
        rlvs_config=short_rlvs_config,
    )
    with pytest.raises(ValueError, match="sum to one"):
        add_lmds_features(
            featured,
            config={"momentum_weights": [0.5, 0.5, 0.5]},
        )


def test_quant_market_state_orchestrates_all_systems_and_is_deterministic(
    fallback_m1: pd.DataFrame,
    short_kds_config: dict[str, object],
    short_rlvs_config: dict[str, object],
) -> None:
    before = fallback_m1.copy(deep=True)
    first = add_quant_market_state_features(
        fallback_m1,
        kds_config=short_kds_config,
        rlvs_config=short_rlvs_config,
    )
    second = add_quant_market_state_features(
        fallback_m1,
        kds_config=short_kds_config,
        rlvs_config=short_rlvs_config,
    )

    pdt.assert_frame_equal(fallback_m1, before)
    pdt.assert_frame_equal(first, second, check_exact=True)
    assert set(QMS_OUTPUT_COLUMNS).issubset(first.columns)
    assert set(LMDS_OUTPUT_COLUMNS).issubset(first.columns)
    assert first["qms_trend"].equals(first["ktrend_score"])
    assert first["qms_momentum"].equals(first["lmom_score"])
    assert first["qms_state_uncertainty"].dropna().between(0.0, 1.0).all()


def test_quant_market_state_prefix_invariance(
    fallback_m1: pd.DataFrame,
    short_kds_config: dict[str, object],
    short_rlvs_config: dict[str, object],
) -> None:
    cutoff = 320
    prefix = add_quant_market_state_features(
        fallback_m1.iloc[:cutoff],
        kds_config=short_kds_config,
        rlvs_config=short_rlvs_config,
    )
    full = add_quant_market_state_features(
        fallback_m1,
        kds_config=short_kds_config,
        rlvs_config=short_rlvs_config,
    )

    system_columns = [
        column
        for column in full.columns
        if column.startswith(("kalman_", "kdi_", "kdx", "kadx", "ktrend_", "rlv_", "lmom_", "qms_"))
        or column in {"local_realized_volatility", "spread_ratio", "volatility_ratio", "volatility_estimator_disagreement"}
    ]
    pdt.assert_frame_equal(
        prefix[system_columns],
        full.iloc[:cutoff][system_columns],
        check_exact=True,
    )


def test_quant_market_state_invalidates_momentum_windows_across_gap(
    fallback_m1: pd.DataFrame,
    short_kds_config: dict[str, object],
    short_rlvs_config: dict[str, object],
) -> None:
    frame = fallback_m1.drop(fallback_m1.index[180:190]).copy()
    out = add_quant_market_state_features(
        frame,
        kds_config=short_kds_config,
        rlvs_config=short_rlvs_config,
    )
    gap_position = 180

    assert out["qms_gap_flag"].iloc[gap_position] == 1.0
    assert out["qms_gap_minutes"].iloc[gap_position] == 10.0
    assert np.isnan(out["lmom_impulse_15"].iloc[gap_position])
    assert np.isnan(out["lmom_impulse_15"].iloc[gap_position + 14])
    assert np.isfinite(out["lmom_impulse_15"].iloc[gap_position + 15])
    assert out["qms_contiguous_bars"].iloc[gap_position] == 1.0


def test_weekend_gap_is_expected_and_soft_resets_state(
    short_kds_config: dict[str, object],
    short_rlvs_config: dict[str, object],
) -> None:
    friday = make_fallback_m1(180, drift=3e-5, noise_scale=0.0)
    friday.index = pd.date_range("2025-01-03 18:00", periods=180, freq="min", tz="UTC")
    sunday = make_fallback_m1(120, drift=0.0, noise_scale=1e-5)
    sunday.index = pd.date_range("2025-01-05 22:00", periods=120, freq="min", tz="UTC")
    sunday[["open", "high", "low", "close"]] *= 1.002
    frame = pd.concat([friday, sunday])

    out = add_quant_market_state_features(
        frame,
        kds_config=short_kds_config,
        rlvs_config=short_rlvs_config,
    )
    gap_position = len(friday)

    assert out["qms_weekend_gap"].iloc[gap_position] == 1.0
    assert out["qms_unexpected_data_gap"].iloc[gap_position] == 0.0
    assert out["qms_state_reinitialized"].iloc[gap_position] == 1.0
    assert np.isfinite(out["qms_opening_gap_return"].iloc[gap_position])
    assert np.isnan(out["lmom_impulse_60"].iloc[gap_position])
