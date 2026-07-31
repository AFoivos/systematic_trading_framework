from __future__ import annotations

import numpy as np
import pandas as pd

from src.utils.eurusd_ftmo_ml_v2_contract import (
    PULLBACK_FAMILY_WEIGHT,
    SCORE_CAP,
    SCORE_FLOOR,
    SESSION_FAMILY_WEIGHT,
)


def score_to_confidence(score: pd.Series | np.ndarray | float) -> pd.Series | np.ndarray | float:
    confidence = (score - SCORE_FLOOR) / (SCORE_CAP - SCORE_FLOOR)
    if isinstance(confidence, pd.Series):
        return confidence.clip(0.0, 1.0)
    if isinstance(confidence, np.ndarray):
        return np.clip(confidence, 0.0, 1.0)
    return float(np.clip(confidence, 0.0, 1.0))


def attach_oos_scores(candidates: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    prediction_columns = [
        "candidate_id", "model_train_end", "scoring_year", "pred_model_3", "pred_model_7",
        "pred_model_15", "pred_score", "pred_is_oos",
    ]
    missing = [column for column in prediction_columns if column not in predictions.columns]
    if missing:
        raise KeyError(f"Missing OOS prediction columns: {missing}")
    if predictions["candidate_id"].duplicated().any():
        raise ValueError("Predictions must contain one row per candidate_id.")
    out = candidates.merge(predictions[prediction_columns], on="candidate_id", how="left", validate="one_to_one")
    out["confidence"] = score_to_confidence(out["pred_score"])
    out.loc[~out["pred_is_oos"].fillna(False), "confidence"] = 0.0
    return out


def aggregate_candidate_signals(market_index: pd.DatetimeIndex, scored_candidates: pd.DataFrame) -> pd.DataFrame:
    """Freeze candidate confidence at entry and aggregate active intervals."""
    if not isinstance(market_index, pd.DatetimeIndex) or market_index.has_duplicates:
        raise ValueError("market_index must be a unique DatetimeIndex.")
    component_columns = [f"pullback_{idx}_contribution" for idx in range(1, 5)]
    out = pd.DataFrame(0.0, index=market_index, columns=component_columns + ["session_contribution"])
    for candidate in scored_candidates.itertuples(index=False):
        confidence = float(candidate.confidence) if pd.notna(candidate.confidence) else 0.0
        if confidence <= 0.0:
            continue
        active = (out.index >= pd.Timestamp(candidate.entry_timestamp)) & (out.index < pd.Timestamp(candidate.exit_timestamp))
        if int(candidate.is_session) == 1:
            column = "session_contribution"
            contribution = int(candidate.direction) * confidence
        else:
            component_number = int(str(candidate.component_id).rsplit("_", 1)[-1])
            column = f"pullback_{component_number}_contribution"
            contribution = int(candidate.direction) * confidence * 0.25
        if (out.loc[active, column] != 0.0).any():
            raise AssertionError(f"Overlapping active candidates detected in {candidate.component_id}.")
        out.loc[active, column] = contribution
    out["pullback_signal"] = out[component_columns].sum(axis=1)
    out["directional_signal"] = (
        PULLBACK_FAMILY_WEIGHT * out["pullback_signal"]
        + SESSION_FAMILY_WEIGHT * out["session_contribution"]
    )
    return out


__all__ = ["aggregate_candidate_signals", "attach_oos_scores", "score_to_confidence"]
