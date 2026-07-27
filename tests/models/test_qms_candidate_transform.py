from __future__ import annotations

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from src.models.registry import MODEL_REGISTRY, get_model_fn
from src.models.transforms.qms_candidate import apply_qms_candidate_transform
from src.utils.config_validation import ConfigValidationError, validate_model_block


def _qms_frame(periods: int = 180) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=periods, freq="30min", tz="UTC")
    phase = np.arange(periods, dtype=float)
    return pd.DataFrame(
        {
            "ktrend_score": 0.10 + 0.01 * np.sin(phase / 9.0),
            "ktrend_uncertainty": 0.40 + 0.01 * np.cos(phase / 11.0),
            "kalman_innovation_z": 0.10 * np.sin(phase / 5.0),
            "lmom_score": 0.10 + 0.01 * np.cos(phase / 8.0),
            "lmom_efficiency": 0.50 + 0.01 * np.cos(phase / 13.0),
            "lmom_reversal_pressure": 0.10 + 0.01 * np.sin(phase / 6.0),
            "lmom_exhaustion": 0.10 + 0.01 * np.cos(phase / 10.0),
            "rlv_vol_of_vol_ratio": 1.0 + 0.01 * np.sin(phase / 17.0),
            "rlv_shock_z": 0.20 * np.sin(phase / 4.0),
            "qms_gap_flag": 0.0,
            "qms_unexpected_data_gap": 0.0,
        },
        index=index,
    )


def _params() -> dict[str, object]:
    return {
        "strategies": [
            "kds_pullback_continuation",
            "lmds_exhaustion_reversal",
        ],
        "common_params": {
            "lookback_bars": 60,
            "min_periods": 40,
            "signal_on_crossing": True,
        },
    }


def _set_kds_event(frame: pd.DataFrame, row: int) -> None:
    frame.iloc[row, frame.columns.get_loc("ktrend_score")] = 0.80
    frame.iloc[row, frame.columns.get_loc("ktrend_uncertainty")] = 0.10
    frame.iloc[row, frame.columns.get_loc("kalman_innovation_z")] = -5.0
    frame.iloc[row, frame.columns.get_loc("rlv_vol_of_vol_ratio")] = 0.50


def _set_exhaustion_event(frame: pd.DataFrame, row: int) -> None:
    frame.iloc[row, frame.columns.get_loc("ktrend_score")] = 0.80
    frame.iloc[row, frame.columns.get_loc("lmom_score")] = -0.80
    frame.iloc[row, frame.columns.get_loc("lmom_efficiency")] = 0.05
    frame.iloc[row, frame.columns.get_loc("lmom_reversal_pressure")] = 0.95
    frame.iloc[row, frame.columns.get_loc("lmom_exhaustion")] = 0.95
    frame.iloc[row, frame.columns.get_loc("rlv_shock_z")] = 5.0


def test_qms_candidate_transform_unions_causal_strategy_events() -> None:
    frame = _qms_frame()
    _set_kds_event(frame, 120)
    _set_exhaustion_event(frame, 130)

    out, model, meta = apply_qms_candidate_transform(
        frame,
        {"kind": "qms_candidate_transform", "params": _params()},
    )

    assert model is None
    assert out["qms_meta_candidate"].iloc[120] == 1
    assert out["qms_meta_side"].iloc[120] == 1
    assert out["qms_meta_candidate"].iloc[130] == 1
    assert out["qms_meta_side"].iloc[130] == -1
    assert meta["candidate_rows"] >= 2
    assert meta["anti_leakage"]["fitted"] is False


def test_qms_candidate_transform_fails_closed_on_side_conflict() -> None:
    frame = _qms_frame()
    _set_kds_event(frame, 120)
    _set_exhaustion_event(frame, 120)

    out, _, meta = apply_qms_candidate_transform(
        frame,
        {"kind": "qms_candidate_transform", "params": _params()},
    )

    assert out["qms_meta_source_count"].iloc[120] == 2
    assert out["qms_meta_side_conflict"].iloc[120] == 1
    assert out["qms_meta_candidate"].iloc[120] == 0
    assert out["qms_meta_side"].iloc[120] == 0
    assert meta["conflict_rows"] >= 1


def test_qms_candidate_transform_is_prefix_invariant() -> None:
    frame = _qms_frame()
    _set_kds_event(frame, 120)
    _set_exhaustion_event(frame, 130)
    cfg = {"kind": "qms_candidate_transform", "params": _params()}

    prefix, _, _ = apply_qms_candidate_transform(frame.iloc[:145], cfg)
    full, _, _ = apply_qms_candidate_transform(frame, cfg)

    columns = [
        "qms_meta_candidate",
        "qms_meta_side",
        "qms_meta_source_count",
        "qms_meta_side_conflict",
        "qms_meta_threshold_ready",
    ]
    pdt.assert_frame_equal(prefix[columns], full.iloc[:145][columns], check_exact=True)


def test_qms_candidate_transform_is_registered_and_validated() -> None:
    assert "qms_candidate_transform" in MODEL_REGISTRY
    assert get_model_fn("qms_candidate_transform") is not None
    validate_model_block(
        {"kind": "qms_candidate_transform", "params": _params()}
    )

    with pytest.raises(ConfigValidationError, match="Unsupported QMS strategies"):
        validate_model_block(
            {
                "kind": "qms_candidate_transform",
                "params": {"strategies": ["unknown"]},
            }
        )
