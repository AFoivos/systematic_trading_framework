from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class MetaLabelEvaluation:
    status: str
    reason: str
    predictions: pd.DataFrame
    metrics: dict[str, Any]
    fold_metadata: list[dict[str, Any]]


def chronological_meta_label_evaluation(
    samples: pd.DataFrame,
    *,
    feature_columns: Sequence[str],
    target_column: str = "meta_label",
    min_samples: int = 60,
    min_class_samples: int = 20,
    n_splits: int = 3,
    seed: int = 7,
) -> MetaLabelEvaluation:
    """Evaluate a small logistic meta-label model with expanding time folds.

    The function is deliberately fail-closed.  It never relaxes sample or
    class-balance requirements and all preprocessing statistics are fitted
    inside each chronological training fold.
    """

    if not isinstance(samples.index, pd.DatetimeIndex):
        raise TypeError("samples must use a DatetimeIndex.")
    if not samples.index.is_monotonic_increasing:
        raise ValueError("samples must be sorted chronologically.")
    if samples.index.has_duplicates:
        raise ValueError("samples must have unique timestamps.")
    if n_splits < 2:
        raise ValueError("n_splits must be >= 2.")
    features = [str(column) for column in feature_columns]
    if not features or len(features) != len(set(features)):
        raise ValueError("feature_columns must be non-empty and unique.")
    missing = [column for column in [*features, target_column] if column not in samples.columns]
    if missing:
        raise KeyError(f"Meta-label samples are missing columns: {missing}")

    frame = samples[[*features, target_column]].copy()
    frame[features] = frame[features].apply(pd.to_numeric, errors="coerce")
    frame[target_column] = pd.to_numeric(frame[target_column], errors="coerce")
    frame = frame.loc[frame[target_column].isin([0, 1])].copy()
    target = frame[target_column].astype(int)
    counts = target.value_counts().reindex([0, 1], fill_value=0)

    readiness = {
        "rows": int(len(frame)),
        "negative_rows": int(counts.loc[0]),
        "positive_rows": int(counts.loc[1]),
        "minimum_rows": int(min_samples),
        "minimum_rows_per_class": int(min_class_samples),
        "features": features,
        "threshold": 0.5,
        "preprocessing": "fold-local median imputation then standard scaling",
        "estimator": "LogisticRegression(C=1, class_weight=balanced, seed=7)",
    }
    if len(frame) < min_samples:
        return MetaLabelEvaluation(
            status="insufficient_samples",
            reason=f"Need at least {min_samples} labeled trades; observed {len(frame)}.",
            predictions=pd.DataFrame(index=frame.index),
            metrics=readiness,
            fold_metadata=[],
        )
    if int(counts.min()) < min_class_samples:
        return MetaLabelEvaluation(
            status="insufficient_class_balance",
            reason=(
                f"Need at least {min_class_samples} trades in each class; "
                f"observed negative={counts.loc[0]}, positive={counts.loc[1]}."
            ),
            predictions=pd.DataFrame(index=frame.index),
            metrics=readiness,
            fold_metadata=[],
        )

    block = max(10, len(frame) // (n_splits + 2))
    first_test = len(frame) - n_splits * block
    if first_test < max(30, min_class_samples * 2):
        return MetaLabelEvaluation(
            status="insufficient_fold_history",
            reason="Not enough leading observations for the first expanding training fold.",
            predictions=pd.DataFrame(index=frame.index),
            metrics={**readiness, "planned_test_block_rows": int(block)},
            fold_metadata=[],
        )

    prediction_rows: list[pd.DataFrame] = []
    fold_metadata: list[dict[str, Any]] = []
    for fold in range(n_splits):
        train_end = first_test + fold * block
        test_end = min(len(frame), train_end + block)
        train = frame.iloc[:train_end]
        test = frame.iloc[train_end:test_end]
        train_target = train[target_column].astype(int)
        test_target = test[target_column].astype(int)
        train_counts = train_target.value_counts().reindex([0, 1], fill_value=0)
        if int(train_counts.min()) < min_class_samples:
            return MetaLabelEvaluation(
                status="insufficient_fold_class_balance",
                reason=(
                    f"Fold {fold} training data has negative={train_counts.loc[0]}, "
                    f"positive={train_counts.loc[1]}; minimum is {min_class_samples}."
                ),
                predictions=pd.DataFrame(index=frame.index),
                metrics=readiness,
                fold_metadata=fold_metadata,
            )

        estimator = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        C=1.0,
                        class_weight="balanced",
                        max_iter=2_000,
                        random_state=int(seed),
                        solver="lbfgs",
                    ),
                ),
            ]
        )
        estimator.fit(train[features], train_target)
        probability = estimator.predict_proba(test[features])[:, 1]
        fold_predictions = pd.DataFrame(
            {
                "actual": test_target.to_numpy(dtype=int),
                "probability": probability,
                "predicted": (probability >= 0.5).astype(int),
                "fold": int(fold),
            },
            index=test.index,
        )
        prediction_rows.append(fold_predictions)
        fold_metadata.append(
            {
                "fold": int(fold),
                "train_rows": int(len(train)),
                "test_rows": int(len(test)),
                "train_start": train.index.min().isoformat(),
                "train_end": train.index.max().isoformat(),
                "test_start": test.index.min().isoformat(),
                "test_end": test.index.max().isoformat(),
                "train_negative": int(train_counts.loc[0]),
                "train_positive": int(train_counts.loc[1]),
            }
        )

    predictions = pd.concat(prediction_rows).sort_index()
    actual = predictions["actual"].astype(int)
    probability = predictions["probability"].astype(float)
    predicted = predictions["predicted"].astype(int)
    auc = float(roc_auc_score(actual, probability)) if actual.nunique() == 2 else float("nan")
    metrics = {
        **readiness,
        "evaluated_rows": int(len(predictions)),
        "accuracy": float(accuracy_score(actual, predicted)),
        "brier_score": float(brier_score_loss(actual, probability)),
        "roc_auc": auc,
        "predicted_positive_rate": float(predicted.mean()),
        "actual_positive_rate": float(actual.mean()),
        "evaluation_scope": "expanding chronological out-of-fold predictions",
    }
    return MetaLabelEvaluation(
        status="evaluated",
        reason="All predeclared readiness gates passed.",
        predictions=predictions,
        metrics=metrics,
        fold_metadata=fold_metadata,
    )


__all__ = ["MetaLabelEvaluation", "chronological_meta_label_evaluation"]
