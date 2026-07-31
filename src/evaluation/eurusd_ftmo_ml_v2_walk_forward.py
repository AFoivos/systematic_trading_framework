from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.features.eurusd_ftmo_ml_v2 import model_matrix
from src.models.classification.eurusd_ftmo_meta_ensemble import MetaEnsemble
from src.utils.eurusd_ftmo_ml_v2_contract import FEATURE_COLUMNS


@dataclass
class WalkForwardResult:
    predictions: pd.DataFrame
    fold_models: dict[str, MetaEnsemble]
    fold_manifest: list[dict[str, Any]]
    final_ensemble: MetaEnsemble


def _schedule(max_timestamp: pd.Timestamp) -> list[tuple[str, pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    entries = [
        ("2022", pd.Timestamp("2022-01-01"), pd.Timestamp("2022-01-01"), pd.Timestamp("2023-01-01")),
        ("2023", pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01")),
        ("2024", pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")),
        ("2025_holdout", pd.Timestamp("2025-01-01"), pd.Timestamp("2025-01-01"), max_timestamp + pd.Timedelta(nanoseconds=1)),
    ]
    return entries


def annual_walk_forward(candidate_features: pd.DataFrame) -> WalkForwardResult:
    required = {"candidate_id", "signal_timestamp", "target_positive_net"}
    missing = sorted(required.difference(candidate_features.columns))
    if missing:
        raise KeyError(f"Missing walk-forward columns: {missing}")
    data = candidate_features.copy()
    data["signal_timestamp"] = pd.to_datetime(data["signal_timestamp"])
    data = data.sort_values(["signal_timestamp", "candidate_id"], kind="stable").reset_index(drop=True)
    if data.empty:
        raise ValueError("Walk-forward evaluation requires candidate trades.")

    predictions = data[["candidate_id", "signal_timestamp"]].copy()
    predictions["model_train_end"] = pd.Series(pd.NA, index=predictions.index, dtype="object")
    predictions["scoring_year"] = pd.Series(pd.NA, index=predictions.index, dtype="Int64")
    for column in ("pred_model_3", "pred_model_7", "pred_model_15", "pred_score"):
        predictions[column] = np.nan
    predictions["pred_is_oos"] = False
    fold_models: dict[str, MetaEnsemble] = {}
    fold_manifest: list[dict[str, Any]] = []

    max_timestamp = pd.Timestamp(data["signal_timestamp"].max())
    for fold_name, train_cutoff, score_start, score_end in _schedule(max_timestamp):
        train_mask = data["signal_timestamp"] < train_cutoff
        score_mask = (data["signal_timestamp"] >= score_start) & (data["signal_timestamp"] < score_end)
        if not score_mask.any():
            continue
        train = data.loc[train_mask]
        if train.empty:
            raise ValueError(f"Fold {fold_name} has no strictly prior training candidates.")
        ensemble = MetaEnsemble.fit(
            model_matrix(train),
            train["target_positive_net"],
        )
        scored = ensemble.predict(model_matrix(data.loc[score_mask]))
        for column in scored.columns:
            predictions.loc[score_mask, column] = scored[column].to_numpy()
        actual_train_end = pd.Timestamp(train["signal_timestamp"].max())
        predictions.loc[score_mask, "model_train_end"] = actual_train_end.isoformat()
        predictions.loc[score_mask, "scoring_year"] = data.loc[score_mask, "signal_timestamp"].dt.year.to_numpy()
        predictions.loc[score_mask, "pred_is_oos"] = (
            data.loc[score_mask, "signal_timestamp"] > actual_train_end
        ).to_numpy()
        fold_models[fold_name] = ensemble
        fold_manifest.append(
            {
                "fold": fold_name,
                "train_cutoff_exclusive": train_cutoff.isoformat(),
                "train_start": pd.Timestamp(train["signal_timestamp"].min()).isoformat(),
                "train_end": actual_train_end.isoformat(),
                "train_rows": int(len(train)),
                "score_start": score_start.isoformat(),
                "score_end_exclusive": score_end.isoformat(),
                "score_rows": int(score_mask.sum()),
                "strictly_oos": bool((data.loc[score_mask, "signal_timestamp"] > actual_train_end).all()),
            }
        )

    eligible = predictions["signal_timestamp"] >= pd.Timestamp("2022-01-01")
    if eligible.any():
        missing_predictions = predictions.loc[eligible, "pred_score"].isna()
        if missing_predictions.any():
            raise AssertionError("Annual walk-forward left eligible candidates unscored.")
        if not predictions.loc[eligible, "pred_is_oos"].all():
            raise AssertionError("A historical headline prediction is not strictly OOS.")

    final_ensemble = MetaEnsemble.fit(model_matrix(data), data["target_positive_net"])
    return WalkForwardResult(
        predictions=predictions,
        fold_models=fold_models,
        fold_manifest=fold_manifest,
        final_ensemble=final_ensemble,
    )


__all__ = ["WalkForwardResult", "annual_walk_forward"]
