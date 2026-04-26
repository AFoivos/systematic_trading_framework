from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from src.models.runtime import classify_feature_family


def summarize_label_distribution(values: Iterable[Any]) -> dict[str, Any]:
    series = pd.Series(list(values) if not isinstance(values, pd.Series) else values, copy=False)
    series = series.dropna()
    if series.empty:
        return {
            "labeled_rows": 0,
            "class_counts": {},
            "positive_rate": None,
            "negative_rate": None,
        }

    try:
        labels = series.astype(int)
    except Exception:
        labels = pd.to_numeric(series, errors="coerce").dropna().astype(int)

    counts = labels.value_counts().sort_index()
    positive = int(counts.get(1, 0))
    negative = int(counts.get(0, 0))
    total = int(counts.sum())
    return {
        "labeled_rows": total,
        "class_counts": {str(int(label)): int(count) for label, count in counts.items()},
        "positive_rate": float(positive / total) if total > 0 else None,
        "negative_rate": float(negative / total) if total > 0 else None,
    }


def aggregate_label_distributions(distributions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = defaultdict(int)
    labeled_rows = 0
    for item in distributions:
        dist = dict(item or {})
        labeled_rows += int(dist.get("labeled_rows", 0) or 0)
        for label, count in dict(dist.get("class_counts", {}) or {}).items():
            counts[str(label)] += int(count or 0)
    if labeled_rows <= 0:
        return {
            "labeled_rows": 0,
            "class_counts": {},
            "positive_rate": None,
            "negative_rate": None,
        }
    positive = int(counts.get("1", 0))
    negative = int(counts.get("0", 0))
    return {
        "labeled_rows": int(labeled_rows),
        "class_counts": dict(sorted(counts.items(), key=lambda kv: kv[0])),
        "positive_rate": float(positive / labeled_rows),
        "negative_rate": float(negative / labeled_rows),
    }


def summarize_numeric_distribution(values: Iterable[Any]) -> dict[str, Any]:
    series = pd.Series(list(values) if not isinstance(values, pd.Series) else values, copy=False)
    numeric = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    if numeric.empty:
        return {
            "rows": 0,
            "mean": None,
            "std": None,
            "min": None,
            "max": None,
            "median": None,
            "q05": None,
            "q95": None,
            "positive_rate": None,
            "negative_rate": None,
            "zero_rate": None,
        }

    return {
        "rows": int(len(numeric)),
        "mean": float(numeric.mean()),
        "std": float(numeric.std(ddof=1)) if len(numeric) >= 2 else 0.0,
        "min": float(numeric.min()),
        "max": float(numeric.max()),
        "median": float(numeric.median()),
        "q05": float(numeric.quantile(0.05)),
        "q95": float(numeric.quantile(0.95)),
        "positive_rate": float((numeric > 0.0).mean()),
        "negative_rate": float((numeric < 0.0).mean()),
        "zero_rate": float((numeric == 0.0).mean()),
    }


def summarize_feature_availability(frame: pd.DataFrame, feature_cols: Sequence[str]) -> dict[str, int]:
    if not feature_cols:
        return {
            "rows": int(len(frame)),
            "complete_rows": int(len(frame)),
            "missing_rows": 0,
        }
    features = frame.loc[:, list(feature_cols)]
    complete_rows = int(features.notna().all(axis=1).sum())
    return {
        "rows": int(len(frame)),
        "complete_rows": complete_rows,
        "missing_rows": int(len(frame) - complete_rows),
    }


def extract_feature_importance(model: Any, feature_cols: Sequence[str]) -> list[dict[str, Any]]:
    if model is None or not feature_cols:
        return []

    values: np.ndarray | None = None
    source: str | None = None

    if hasattr(model, "feature_importances_"):
        raw = np.asarray(getattr(model, "feature_importances_"), dtype=float)
        if raw.ndim == 1 and raw.size == len(feature_cols):
            values = raw
            source = "feature_importances_"
    elif hasattr(model, "coef_"):
        raw = np.asarray(getattr(model, "coef_"), dtype=float)
        if raw.ndim == 1 and raw.size == len(feature_cols):
            values = np.abs(raw)
            source = "coef_"
        elif raw.ndim == 2 and raw.shape[1] == len(feature_cols):
            values = np.mean(np.abs(raw), axis=0)
            source = "coef_"
    elif hasattr(model, "params"):
        try:
            params = pd.Series(getattr(model, "params"))
        except Exception:
            params = pd.Series(dtype=float)
        matched = []
        for feature in feature_cols:
            if feature in params.index:
                matched.append(abs(float(params.loc[feature])))
            else:
                matched.append(0.0)
        if any(value > 0.0 for value in matched):
            values = np.asarray(matched, dtype=float)
            source = "params"

    if values is None or source is None:
        return []

    values = np.where(np.isfinite(values), np.abs(values), 0.0)
    total = float(values.sum())
    rows: list[dict[str, Any]] = []
    order = np.argsort(values)[::-1]
    for rank, idx in enumerate(order, start=1):
        importance = float(values[idx])
        normalized = float(importance / total) if total > 0.0 else 0.0
        rows.append(
            {
                "feature": str(feature_cols[int(idx)]),
                "importance": importance,
                "importance_normalized": normalized,
                "rank": int(rank),
                "source": source,
            }
        )
    return rows


def aggregate_feature_importance(
    fold_importances: Sequence[Sequence[Mapping[str, Any]]],
    *,
    top_n: int = 20,
) -> dict[str, Any]:
    bucket: dict[str, dict[str, Any]] = {}
    available_folds = 0
    for fold in fold_importances:
        fold_rows = list(fold or [])
        if not fold_rows:
            continue
        available_folds += 1
        for row in fold_rows:
            feature = str(row.get("feature"))
            info = bucket.setdefault(
                feature,
                {
                    "feature": feature,
                    "importance_sum": 0.0,
                    "importance_normalized_sum": 0.0,
                    "fold_count": 0,
                    "source": row.get("source"),
                },
            )
            info["importance_sum"] += float(row.get("importance", row.get("mean_importance", 0.0)) or 0.0)
            info["importance_normalized_sum"] += float(
                row.get("importance_normalized", row.get("mean_importance_normalized", 0.0)) or 0.0
            )
            info["fold_count"] += 1

    if not bucket:
        return {
            "available": False,
            "folds_with_importance": 0,
            "top_features": [],
        }

    rows: list[dict[str, Any]] = []
    for feature, info in bucket.items():
        fold_count = max(int(info["fold_count"]), 1)
        rows.append(
            {
                "feature": feature,
                "mean_importance": float(info["importance_sum"] / fold_count),
                "mean_importance_normalized": float(info["importance_normalized_sum"] / fold_count),
                "fold_count": int(info["fold_count"]),
                "source": info.get("source"),
            }
        )
    rows.sort(key=lambda item: item["mean_importance"], reverse=True)
    for rank, row in enumerate(rows, start=1):
        row["rank"] = int(rank)

    return {
        "available": True,
        "folds_with_importance": int(available_folds),
        "top_features": rows[:top_n],
    }


def summarize_feature_family_counts(feature_cols: Sequence[str]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for feature in feature_cols:
        family = classify_feature_family(str(feature)) or "unclassified"
        counts[family] += 1
    return dict(sorted(counts.items(), key=lambda kv: kv[0]))


def summarize_feature_importance_stability(
    fold_importances: Sequence[Sequence[Mapping[str, Any]]],
    *,
    top_n: int = 10,
) -> dict[str, Any]:
    per_feature: dict[str, dict[str, Any]] = {}
    available_folds = 0
    for fold_idx, fold_rows in enumerate(fold_importances):
        rows = list(fold_rows or [])
        if not rows:
            continue
        available_folds += 1
        for row in rows:
            feature = str(row.get("feature"))
            info = per_feature.setdefault(
                feature,
                {
                    "feature": feature,
                    "family": classify_feature_family(feature) or "unclassified",
                    "fold_count": 0,
                    "rank_sum": 0.0,
                    "importance_sum": 0.0,
                    "normalized_sum": 0.0,
                    "best_rank": None,
                    "folds": [],
                },
            )
            rank = int(row.get("rank", 0) or 0)
            importance = float(row.get("importance", row.get("mean_importance", 0.0)) or 0.0)
            normalized = float(
                row.get("importance_normalized", row.get("mean_importance_normalized", 0.0)) or 0.0
            )
            info["fold_count"] += 1
            info["rank_sum"] += rank
            info["importance_sum"] += importance
            info["normalized_sum"] += normalized
            info["best_rank"] = rank if info["best_rank"] is None else min(int(info["best_rank"]), rank)
            info["folds"].append(
                {
                    "fold": int(fold_idx),
                    "rank": rank,
                    "importance": importance,
                    "importance_normalized": normalized,
                }
            )

    if not per_feature:
        return {
            "available": False,
            "folds_with_importance": 0,
            "top_features": [],
        }

    rows: list[dict[str, Any]] = []
    for info in per_feature.values():
        fold_count = max(int(info["fold_count"]), 1)
        coverage = float(info["fold_count"] / max(available_folds, 1))
        rows.append(
            {
                "feature": info["feature"],
                "family": info["family"],
                "fold_count": int(info["fold_count"]),
                "fold_coverage": coverage,
                "mean_rank": float(info["rank_sum"] / fold_count),
                "best_rank": int(info["best_rank"]) if info["best_rank"] is not None else None,
                "mean_importance": float(info["importance_sum"] / fold_count),
                "mean_importance_normalized": float(info["normalized_sum"] / fold_count),
                "folds": list(info["folds"]),
            }
        )
    rows.sort(key=lambda item: (-item["fold_coverage"], item["mean_rank"], -item["mean_importance"]))
    for rank, row in enumerate(rows, start=1):
        row["stability_rank"] = int(rank)

    return {
        "available": True,
        "folds_with_importance": int(available_folds),
        "top_features": rows[:top_n],
    }


def summarize_prediction_alignment(
    *,
    index: pd.Index,
    oos_mask: pd.Series,
    prediction: pd.Series,
    probability: pd.Series | None = None,
    target: pd.Series | None = None,
    pred_vol: pd.Series | None = None,
) -> dict[str, Any]:
    oos = oos_mask.reindex(index).fillna(False).astype(bool)
    pred = prediction.reindex(index)
    valid_pred = pred.notna()
    oos_valid_pred = valid_pred & oos
    pred_index = pred.index[oos_valid_pred]

    diagnostics: dict[str, Any] = {
        "oos_rows": int(oos.sum()),
        "predicted_rows": int(oos_valid_pred.sum()),
        "non_oos_prediction_rows": int((valid_pred & ~oos).sum()),
        "missing_oos_prediction_rows": int((oos & ~valid_pred).sum()),
        "oos_prediction_coverage": float(oos_valid_pred.sum() / max(int(oos.sum()), 1)),
        "alignment_ok": bool((valid_pred & ~oos).sum() == 0),
        "first_prediction_index": pred_index[0].isoformat() if len(pred_index) else None,
        "last_prediction_index": pred_index[-1].isoformat() if len(pred_index) else None,
        "prediction_distribution": summarize_numeric_distribution(pred.loc[oos_valid_pred]),
    }
    if target is not None:
        diagnostics["target_distribution"] = summarize_numeric_distribution(target.reindex(index).loc[oos_valid_pred])
    if probability is not None:
        diagnostics["probability_distribution"] = summarize_numeric_distribution(
            probability.reindex(index).loc[oos_valid_pred]
        )
    if pred_vol is not None:
        diagnostics["predicted_vol_distribution"] = summarize_numeric_distribution(
            pred_vol.reindex(index).loc[oos_valid_pred]
        )
    return diagnostics


__all__ = [
    "aggregate_feature_importance",
    "aggregate_label_distributions",
    "extract_feature_importance",
    "summarize_feature_family_counts",
    "summarize_feature_importance_stability",
    "summarize_feature_availability",
    "summarize_label_distribution",
    "summarize_numeric_distribution",
    "summarize_prediction_alignment",
]
