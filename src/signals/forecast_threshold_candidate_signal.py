from __future__ import annotations

import pandas as pd

from src.signals._common import resolve_signal_output_name
from src.signals.forecast_signal import (
    compute_forecast_threshold_candidates,
    compute_forecast_threshold_signal,
)


def forecast_threshold_candidate_signal(
    df: pd.DataFrame,
    forecast_col: str = "pred_ret",
    pred_is_oos_col: str = "pred_is_oos",
    signal_col: str | None = None,
    upper: float = 0.0,
    lower: float | None = None,
    mode: str = "long_short",
    activation_filters: list[dict[str, object]] | None = None,
    candidate_col: str = "primary_candidate",
    side_col: str = "primary_candidate_side",
    strength_col: str = "primary_candidate_strength",
    threshold_distance_col: str = "primary_candidate_threshold_distance",
    inclusive: bool = False,
) -> pd.DataFrame:
    """
    Emit the thresholded forecast signal plus OOS-only primary candidate columns.

    YAML declaration::

        signals:
          kind: forecast_threshold_candidate
          params:
            forecast_col: pred_ret
            pred_is_oos_col: pred_is_oos
            signal_col: signal_structured_tail
            upper: 0.7
            lower: -0.85
            mode: long_short
            activation_filters: []
            candidate_col: primary_candidate
            side_col: primary_candidate_side
            strength_col: primary_candidate_strength
            threshold_distance_col: primary_candidate_threshold_distance

    Required input columns
    ----------------------
    forecast_col:
        Point-in-time forecast column used by the primary threshold rule.
    pred_is_oos_col:
        Boolean OOS mask. Candidate columns are emitted only where this is true.
    activation_filters:
        Optional point-in-time feature columns referenced by filter declarations.

    Parameters
    ----------
    upper, lower:
        Forecast thresholds for long and short candidates.
    mode:
        One of ``long_only``, ``short_only``, or ``long_short``.
    candidate_col, side_col, strength_col, threshold_distance_col:
        Output columns for the OOS candidate dataset.
    """
    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_forecast",
    )
    out = compute_forecast_threshold_signal(
        df,
        forecast_col=forecast_col,
        upper=upper,
        lower=lower,
        signal_col=output_col,
        mode=mode,
        activation_filters=activation_filters,
        inclusive=inclusive,
    )
    return compute_forecast_threshold_candidates(
        out,
        forecast_col=forecast_col,
        pred_is_oos_col=pred_is_oos_col,
        upper=upper,
        lower=lower,
        mode=mode,
        activation_filters=activation_filters,
        candidate_col=candidate_col,
        side_col=side_col,
        strength_col=strength_col,
        threshold_distance_col=threshold_distance_col,
        inclusive=inclusive,
    )


__all__ = ["forecast_threshold_candidate_signal"]
