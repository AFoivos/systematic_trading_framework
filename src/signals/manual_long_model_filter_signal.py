from __future__ import annotations

import numpy as np
import pandas as pd


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for manual_long_model_filter_signal: {missing}")


def manual_long_model_filter_signal(
    df: pd.DataFrame,
    *,
    prob_col: str = "pred_prob",
    candidate_col: str = "manual_long_candidate",
    base_signal_col: str = "manual_vol_adjusted_candidate",
    threshold: float = 0.55,
    signal_col: str | None = None,
) -> pd.Series:
    """
    Filter manual long candidates with an out-of-sample model probability.

    The model is only a long-entry filter. It cannot create trades without a manual candidate,
    cannot flip direction, and cannot emit short exposure.
    """
    output_col = str(signal_col or "model_filtered_long_signal")
    threshold_value = float(threshold)
    if not np.isfinite(threshold_value) or not 0.0 < threshold_value < 1.0:
        raise ValueError("manual_long_model_filter_signal threshold must be in (0, 1).")

    _require_columns(df, [prob_col, candidate_col, base_signal_col])

    pred_prob = pd.to_numeric(df[prob_col], errors="coerce")
    candidate = pd.to_numeric(df[candidate_col], errors="coerce").fillna(0.0).gt(0.0)
    base_signal = pd.to_numeric(df[base_signal_col], errors="coerce").fillna(0.0)
    long_exposure = base_signal.clip(lower=0.0)

    passes_filter = candidate & pred_prob.ge(threshold_value).fillna(False)
    signal = long_exposure.where(passes_filter, other=0.0).astype("float32")
    signal.name = output_col
    return signal


__all__ = ["manual_long_model_filter_signal"]
