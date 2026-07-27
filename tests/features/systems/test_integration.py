from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.experiments.orchestration.feature_stage import apply_feature_steps
from src.features.registry import FEATURE_REGISTRY, get_feature_fn
from src.features.systems import QMS_OUTPUT_COLUMNS, add_quant_market_state_features
from src.utils.config_validation import ConfigValidationError, validate_features_block

from .conftest import make_fallback_m1


def test_system_builders_are_canonical_registry_entries() -> None:
    for name in ("kds", "rlvs", "lmds", "quant_market_state"):
        assert name in FEATURE_REGISTRY
        assert get_feature_fn(name) is FEATURE_REGISTRY[name]


def test_feature_stage_runs_separate_system_steps_in_dependency_order(
    fallback_m1: pd.DataFrame,
    short_kds_config: dict[str, object],
    short_rlvs_config: dict[str, object],
) -> None:
    steps = [
        {"step": "kds", "params": {"config": short_kds_config}},
        {"step": "rlvs", "params": {"config": short_rlvs_config}},
        {"step": "lmds", "params": {}},
    ]
    validate_features_block(steps)
    out = apply_feature_steps(fallback_m1, steps)

    assert {"ktrend_score", "rlv_regime_z", "lmom_score"}.issubset(out.columns)


def test_feature_stage_runs_quant_market_state_step(
    fallback_m1: pd.DataFrame,
    short_kds_config: dict[str, object],
    short_rlvs_config: dict[str, object],
) -> None:
    steps = [
        {
            "step": "quant_market_state",
            "params": {
                "preset": "balanced",
                "kds_config": short_kds_config,
                "rlvs_config": short_rlvs_config,
            },
        }
    ]
    validate_features_block(steps)
    out = apply_feature_steps(fallback_m1, steps)

    assert set(QMS_OUTPUT_COLUMNS).issubset(out.columns)


@pytest.mark.parametrize(
    "params",
    [
        {"preset": "unknown"},
        {"config": {"huber_threshold": float("inf")}},
        {"misspelled_parameter": 1},
    ],
)
def test_system_config_preflight_fails_closed(params: dict[str, object]) -> None:
    with pytest.raises(ConfigValidationError):
        validate_features_block([{"step": "kds", "params": params}])


@pytest.mark.parametrize("bar_minutes", [15.0, 30.0])
def test_system_config_preflight_accepts_explicit_intraday_bars(
    bar_minutes: float,
) -> None:
    validate_features_block(
        [
            {
                "step": "quant_market_state",
                "params": {"preset": "balanced", "bar_minutes": bar_minutes},
            }
        ]
    )


def test_quant_market_state_uses_no_negative_shift(
    monkeypatch: pytest.MonkeyPatch,
    fallback_m1: pd.DataFrame,
    short_kds_config: dict[str, object],
    short_rlvs_config: dict[str, object],
) -> None:
    original_shift = pd.Series.shift
    observed_periods: list[int] = []

    def recording_shift(series: pd.Series, periods: int = 1, *args, **kwargs):
        observed_periods.append(int(periods))
        return original_shift(series, periods=periods, *args, **kwargs)

    monkeypatch.setattr(pd.Series, "shift", recording_shift)
    add_quant_market_state_features(
        fallback_m1,
        kds_config=short_kds_config,
        rlvs_config=short_rlvs_config,
    )

    assert observed_periods
    assert min(observed_periods) >= 0


def test_system_builders_do_not_resample_internally() -> None:
    system_root = Path("src/features/systems")
    batch_sources = [
        system_root / "kds.py",
        system_root / "rlvs.py",
        system_root / "lmds.py",
        system_root / "quant_market_state.py",
    ]
    assert all(".resample(" not in path.read_text(encoding="utf-8") for path in batch_sources)


def test_short_history_and_zero_spread_are_stable(
    short_kds_config: dict[str, object],
    short_rlvs_config: dict[str, object],
) -> None:
    frame = make_fallback_m1(12)
    frame["spread_bps"] = 0.0
    out = add_quant_market_state_features(
        frame,
        kds_config=short_kds_config,
        rlvs_config=short_rlvs_config,
    )

    assert len(out) == len(frame)
    assert not np.isinf(out.select_dtypes(include=[np.number]).to_numpy(dtype=float)).any()


def test_extreme_finite_price_scale_does_not_overflow(
    short_kds_config: dict[str, object],
    short_rlvs_config: dict[str, object],
) -> None:
    frame = make_fallback_m1(140, drift=0.0, noise_scale=0.0)
    jump = 70
    extreme = 1e200
    frame.iloc[jump:, frame.columns.get_loc("close")] = extreme
    frame.iloc[jump, frame.columns.get_loc("open")] = 1.10
    frame.iloc[jump + 1 :, frame.columns.get_loc("open")] = extreme
    frame.iloc[jump:, frame.columns.get_loc("high")] = extreme * 1.0001
    frame.iloc[jump, frame.columns.get_loc("low")] = 1.09
    frame.iloc[jump + 1 :, frame.columns.get_loc("low")] = extreme * 0.9999
    out = add_quant_market_state_features(
        frame,
        kds_config=short_kds_config,
        rlvs_config=short_rlvs_config,
    )

    numeric = out.select_dtypes(include=[np.number]).to_numpy(dtype=float)
    assert not np.isinf(numeric).any()


@pytest.mark.parametrize("bar_minutes", [15.0, 30.0])
def test_quant_market_state_supports_regular_intraday_bars(
    fallback_m1: pd.DataFrame,
    short_kds_config: dict[str, object],
    short_rlvs_config: dict[str, object],
    bar_minutes: float,
) -> None:
    frame = fallback_m1.copy()
    frame.index = pd.date_range(
        "2025-01-01",
        periods=len(frame),
        freq=f"{int(bar_minutes)}min",
        tz="UTC",
    )

    out = add_quant_market_state_features(
        frame,
        bar_minutes=bar_minutes,
        kds_config=short_kds_config,
        rlvs_config=short_rlvs_config,
    )

    assert out["qms_gap_flag"].eq(0.0).all()
    assert out["qms_state_reinitialized"].eq(0.0).all()
    assert out["ktrend_score"].iloc[120:].notna().all()
    assert out["lmom_score"].iloc[120:].notna().all()
    assert out["lmom_impulse_60"].iloc[120:].notna().all()


def test_explicit_one_minute_duration_preserves_default_outputs(
    fallback_m1: pd.DataFrame,
    short_kds_config: dict[str, object],
    short_rlvs_config: dict[str, object],
) -> None:
    default = add_quant_market_state_features(
        fallback_m1,
        kds_config=short_kds_config,
        rlvs_config=short_rlvs_config,
    )
    explicit = add_quant_market_state_features(
        fallback_m1,
        bar_minutes=1.0,
        kds_config=short_kds_config,
        rlvs_config=short_rlvs_config,
    )

    pd.testing.assert_frame_equal(default, explicit, check_exact=True)
