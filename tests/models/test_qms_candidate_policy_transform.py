from __future__ import annotations

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from src.models.registry import MODEL_REGISTRY, get_model_fn
from src.models.transforms.qms_candidate_policy import (
    apply_qms_candidate_policy_transform,
    validate_qms_candidate_policy_params,
)
from src.utils.config_validation import ConfigValidationError, validate_model_block


def _frame(periods: int = 180) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=periods, freq="30min", tz="UTC")
    phase = np.arange(periods, dtype=float)
    frame = pd.DataFrame(
        {
            "qms_meta_candidate": np.zeros(periods),
            "qms_meta_side": np.zeros(periods),
            "pred_future_rv_16_is_oos": np.arange(periods) >= 80,
            "kadx_signed": 0.2 + 0.01 * np.sin(phase / 7.0),
            "atr_over_price_48": 0.001 + 0.0001 * np.sin(phase / 13.0),
            "rlv_sigma_slow": np.ones(periods),
            "pred_future_rv_16": np.ones(periods),
        },
        index=index,
    )
    for row, side, forecast in ((60, 1, 2.0), (120, 1, 2.0), (130, -1, 4.0)):
        frame.iloc[row, frame.columns.get_loc("qms_meta_candidate")] = 1.0
        frame.iloc[row, frame.columns.get_loc("qms_meta_side")] = side
        frame.iloc[row, frame.columns.get_loc("pred_future_rv_16")] = forecast
    frame.iloc[130, frame.columns.get_loc("kadx_signed")] = -0.2
    return frame


def _forecast_policy_params() -> dict[str, object]:
    return {
        "candidate_col": "qms_meta_candidate",
        "side_col": "qms_meta_side",
        "pred_is_oos_col": "pred_future_rv_16_is_oos",
        "side_alignment_cols": ["kadx_signed"],
        "gate": {
            "kind": "forecast_expansion",
            "forecast_col": "pred_future_rv_16",
            "current_vol_col": "rlv_sigma_slow",
            "lookback_bars": 60,
            "min_periods": 40,
            "min_expansion": 1.1,
            "forecast_lower_quantile": None,
            "forecast_upper_quantile": None,
            "current_vol_upper_quantile": 0.95,
        },
        "sizing": {
            "kind": "inverse_forecast_vol",
            "forecast_col": "pred_future_rv_16",
            "lookback_bars": 60,
            "min_periods": 40,
            "target_quantile": 0.5,
            "min_weight": 0.2,
            "max_weight": 1.0,
        },
    }


def test_qms_candidate_policy_requires_oos_and_preserves_candidate_side() -> None:
    frame = _frame()
    out, model, meta = apply_qms_candidate_policy_transform(
        frame,
        {"kind": "qms_candidate_policy_transform", "params": _forecast_policy_params()},
    )

    assert model is None
    assert out["qms_policy_candidate"].iloc[60] == 0
    assert out["qms_policy_candidate"].iloc[120] == 1
    assert out["qms_policy_side"].iloc[120] == 1
    assert out["qms_policy_candidate"].iloc[130] == 1
    assert out["qms_policy_side"].iloc[130] == -1
    assert meta["anti_leakage"]["candidate_rows_require_pred_is_oos"] is True
    assert meta["prediction_diagnostics"]["non_oos_prediction_rows"] == 0


def test_inverse_forecast_sizing_is_causal_bounded_and_reduces_high_vol_weight() -> None:
    frame = _frame()
    out, _, _ = apply_qms_candidate_policy_transform(
        frame,
        {"kind": "qms_candidate_policy_transform", "params": _forecast_policy_params()},
    )

    assert out["qms_policy_weight"].iloc[120] == pytest.approx(0.5)
    assert out["qms_policy_weight"].iloc[130] == pytest.approx(0.25)
    assert out["qms_policy_signal"].iloc[120] == pytest.approx(0.5)
    assert out["qms_policy_signal"].iloc[130] == pytest.approx(-0.25)
    assert out["qms_policy_weight"].between(0.0, 1.0).all()


def test_atr_regime_gate_uses_shifted_past_only_thresholds() -> None:
    frame = _frame()
    frame["atr_over_price_48"] = np.linspace(0.5, 1.5, len(frame))
    params = {
        "side_alignment_cols": ["kadx_signed"],
        "gate": {
            "kind": "atr_regime",
            "volatility_col": "atr_over_price_48",
            "lookback_bars": 60,
            "min_periods": 40,
            "lower_quantile": 0.60,
            "upper_quantile": 0.95,
        },
    }
    out, _, meta = apply_qms_candidate_policy_transform(
        frame,
        {"kind": "qms_candidate_policy_transform", "params": params},
    )

    assert out["qms_policy_gate_ready"].iloc[120] == 1
    assert meta["gate_kind"] == "atr_regime"
    assert meta["anti_leakage"]["current_bar_excluded_from_thresholds"] is True


def test_positive_filter_column_rejects_candidates_outside_session() -> None:
    frame = _frame()
    frame["session_london_ny_liquid"] = 0.0
    frame.iloc[120, frame.columns.get_loc("session_london_ny_liquid")] = 1.0
    params = {
        "candidate_col": "qms_meta_candidate",
        "side_col": "qms_meta_side",
        "pred_is_oos_col": "pred_future_rv_16_is_oos",
        "side_alignment_cols": ["kadx_signed"],
        "positive_filter_cols": ["session_london_ny_liquid"],
        "gate": {"kind": "none"},
        "sizing": {"kind": "fixed"},
    }

    out, _, meta = apply_qms_candidate_policy_transform(
        frame,
        {"kind": "qms_candidate_policy_transform", "params": params},
    )

    assert out["qms_policy_candidate"].iloc[120] == 1
    assert out["qms_policy_candidate"].iloc[130] == 0
    assert meta["candidate_summary"]["alignment_rejected_rows"] == 1


def test_qms_candidate_policy_is_prefix_invariant() -> None:
    frame = _frame()
    cfg = {"kind": "qms_candidate_policy_transform", "params": _forecast_policy_params()}

    prefix, _, _ = apply_qms_candidate_policy_transform(frame.iloc[:145], cfg)
    full, _, _ = apply_qms_candidate_policy_transform(frame, cfg)

    columns = [
        "qms_policy_candidate",
        "qms_policy_side",
        "qms_policy_weight",
        "qms_policy_signal",
        "qms_policy_gate_ready",
        "qms_policy_expansion_ratio",
    ]
    pdt.assert_frame_equal(prefix[columns], full.iloc[:145][columns], check_exact=True)


def test_qms_candidate_policy_is_registered_and_config_validated() -> None:
    assert "qms_candidate_policy_transform" in MODEL_REGISTRY
    assert get_model_fn("qms_candidate_policy_transform") is not None
    validate_model_block(
        {"kind": "qms_candidate_policy_transform", "params": _forecast_policy_params()}
    )

    with pytest.raises(ConfigValidationError, match="max_weight must be <= 1.0"):
        validate_model_block(
            {
                "kind": "qms_candidate_policy_transform",
                "params": {
                    "sizing": {
                        "kind": "inverse_forecast_vol",
                        "max_weight": 1.5,
                    }
                },
            }
        )


def test_qms_candidate_policy_rejects_unknown_parameters() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        validate_qms_candidate_policy_params({"misspelled_gate": {}})
