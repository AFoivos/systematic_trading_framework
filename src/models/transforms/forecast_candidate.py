from __future__ import annotations

from typing import Any

import pandas as pd

from src.signals.forecast_threshold_candidate_signal import forecast_threshold_candidate_signal


def apply_forecast_candidate_transform(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, None, dict[str, Any]]:
    """Build point-in-time forecast candidates between stacked model stages.

    This deterministic model-stage transform exists so a first-stage OOS forecast can
    be converted into candidate/side columns before a later meta-label classifier is
    trained. It performs no fitting and does not use ``returns_col``.
    """
    del returns_col
    cfg = dict(model_cfg or {})
    params = dict(cfg.get("params", {}) or {})
    outputs = dict(cfg.get("outputs", {}) or {})

    forecast_col = str(params.get("forecast_col", "pred_ret"))
    pred_is_oos_col = str(params.get("pred_is_oos_col", "pred_is_oos"))
    signal_col = str(outputs.get("signal_col", params.get("signal_col", "signal_primary_candidate")))
    candidate_col = str(outputs.get("candidate_col", params.get("candidate_col", "primary_candidate")))
    side_col = str(outputs.get("side_col", params.get("side_col", "primary_candidate_side")))
    strength_col = str(outputs.get("strength_col", params.get("strength_col", "primary_candidate_strength")))
    threshold_distance_col = str(
        outputs.get(
            "threshold_distance_col",
            params.get("threshold_distance_col", "primary_candidate_threshold_distance"),
        )
    )

    out = forecast_threshold_candidate_signal(
        df,
        forecast_col=forecast_col,
        pred_is_oos_col=pred_is_oos_col,
        signal_col=signal_col,
        upper=float(params.get("upper", 0.0)),
        lower=(float(params["lower"]) if params.get("lower") is not None else None),
        mode=str(params.get("mode", "long_short")),
        activation_filters=list(params.get("activation_filters", []) or []),
        candidate_col=candidate_col,
        side_col=side_col,
        strength_col=strength_col,
        threshold_distance_col=threshold_distance_col,
        inclusive=bool(params.get("inclusive", False)),
    )

    oos_mask = out[pred_is_oos_col].fillna(False).astype(bool)
    candidate_mask = out[candidate_col].fillna(0.0).astype(float).ne(0.0)
    candidate_rows = int((oos_mask & candidate_mask).sum())
    oos_rows = int(oos_mask.sum())
    meta = {
        "model_kind": "forecast_candidate_transform",
        "feature_cols": [forecast_col],
        "pred_is_oos_col": pred_is_oos_col,
        "signal_col": signal_col,
        "candidate_col": candidate_col,
        "side_col": side_col,
        "strength_col": strength_col,
        "threshold_distance_col": threshold_distance_col,
        "test_pred_rows": oos_rows,
        "oos_rows": oos_rows,
        "prediction_diagnostics": {
            "oos_rows": oos_rows,
            "predicted_rows": oos_rows,
            "non_oos_prediction_rows": 0,
            "missing_oos_prediction_rows": 0,
            "oos_prediction_coverage": 1.0 if oos_rows else 0.0,
            "alignment_ok": True,
        },
        "candidate_summary": {
            "candidate_rows": candidate_rows,
            "candidate_rate": float(candidate_rows / max(oos_rows, 1)),
        },
        "anti_leakage": {
            "candidate_source": "first_stage_oos_forecast",
            "candidate_rows_require_pred_is_oos": True,
        },
    }
    return out, None, meta


__all__ = ["apply_forecast_candidate_transform"]
