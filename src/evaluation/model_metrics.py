from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.preprocessing import label_binarize


def empty_classification_metrics() -> dict[str, float | int | None]:
    return {
        "evaluation_rows": 0,
        "positive_rate": None,
        "accuracy": None,
        "brier": None,
        "roc_auc": None,
        "log_loss": None,
    }


def empty_multiclass_classification_metrics() -> dict[str, object]:
    return {
        "evaluation_rows": 0,
        "class_labels": [],
        "class_rates": {},
        "accuracy": None,
        "balanced_accuracy": None,
        "macro_f1": None,
        "multiclass_brier": None,
        "log_loss": None,
        "roc_auc_ovr_macro": None,
        "pr_auc_ovr_macro": None,
        "expected_calibration_error": None,
        "per_class": {},
        "confusion_matrix": [],
        "reliability": [],
        "probability_distribution": {},
        "probability_deciles": {},
    }


def _reliability_rows(
    y: np.ndarray,
    probabilities: np.ndarray,
    class_labels: np.ndarray,
    *,
    bins: int,
) -> tuple[list[dict[str, object]], float | None]:
    predicted_idx = np.argmax(probabilities, axis=1)
    confidence = probabilities[np.arange(len(probabilities)), predicted_idx]
    predicted = class_labels[predicted_idx]
    correct = (predicted == y).astype(float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows: list[dict[str, object]] = []
    weighted_error = 0.0
    for bin_idx in range(bins):
        lower = float(edges[bin_idx])
        upper = float(edges[bin_idx + 1])
        mask = (confidence >= lower) & (
            confidence <= upper if bin_idx == bins - 1 else confidence < upper
        )
        count = int(mask.sum())
        if count == 0:
            rows.append(
                {
                    "bin": bin_idx,
                    "lower": lower,
                    "upper": upper,
                    "rows": 0,
                    "mean_confidence": None,
                    "accuracy": None,
                }
            )
            continue
        mean_confidence = float(np.mean(confidence[mask]))
        bin_accuracy = float(np.mean(correct[mask]))
        weighted_error += float(count) * abs(mean_confidence - bin_accuracy)
        rows.append(
            {
                "bin": bin_idx,
                "lower": lower,
                "upper": upper,
                "rows": count,
                "mean_confidence": mean_confidence,
                "accuracy": bin_accuracy,
            }
        )
    ece = float(weighted_error / len(y)) if len(y) else None
    return rows, ece


def multiclass_classification_metrics(
    y_true: pd.Series,
    pred_probabilities: pd.DataFrame,
    *,
    class_labels: list[int] | np.ndarray | None = None,
    calibration_bins: int = 10,
) -> dict[str, object]:
    """Compute label-complete multiclass and calibration diagnostics."""
    if y_true.empty or pred_probabilities.empty:
        return empty_multiclass_classification_metrics()
    if y_true.index.has_duplicates or pred_probabilities.index.has_duplicates:
        raise ValueError("Multiclass classification metric inputs must have unique indexes.")
    common_index = y_true.index.intersection(pred_probabilities.index)
    if len(common_index) == 0:
        raise ValueError("Multiclass classification metric inputs have no overlapping index.")
    probability_frame = pred_probabilities.reindex(common_index).astype(float)
    labels_series = y_true.reindex(common_index)
    valid = labels_series.notna() & probability_frame.notna().all(axis=1)
    if not bool(valid.any()):
        return empty_multiclass_classification_metrics()
    probability_frame = probability_frame.loc[valid]
    labels_series = labels_series.loc[valid].astype(int)

    resolved_labels = np.asarray(
        list(class_labels) if class_labels is not None else [int(value) for value in probability_frame.columns],
        dtype=int,
    )
    if probability_frame.shape[1] != len(resolved_labels):
        raise ValueError("Probability column count must equal the number of class_labels.")
    probabilities = probability_frame.to_numpy(dtype=float, copy=False)
    if not np.isfinite(probabilities).all() or bool(((probabilities < 0.0) | (probabilities > 1.0)).any()):
        raise ValueError("Multiclass probabilities must be finite and within [0, 1].")
    row_sums = probabilities.sum(axis=1)
    if not np.allclose(row_sums, 1.0, atol=1e-5):
        raise ValueError("Multiclass probability rows must sum to one.")
    y = labels_series.to_numpy(dtype=int, copy=False)
    unknown = sorted(set(np.unique(y)) - set(resolved_labels.tolist()))
    if unknown:
        raise ValueError(f"Observed target labels are absent from class_labels: {unknown}")
    predicted = resolved_labels[np.argmax(probabilities, axis=1)]
    one_hot = label_binarize(y, classes=resolved_labels)
    if one_hot.ndim == 1:
        one_hot = one_hot.reshape(-1, 1)
    if len(resolved_labels) == 2 and one_hot.shape[1] == 1:
        one_hot = np.column_stack([1 - one_hot[:, 0], one_hot[:, 0]])

    precision, recall, per_class_f1, support = precision_recall_fscore_support(
        y,
        predicted,
        labels=resolved_labels,
        zero_division=0,
    )
    per_class: dict[str, dict[str, float | int | None]] = {}
    roc_values: list[float] = []
    pr_values: list[float] = []
    for class_idx, class_label in enumerate(resolved_labels):
        binary_target = (y == class_label).astype(int)
        roc_value: float | None = None
        pr_value: float | None = None
        if len(np.unique(binary_target)) >= 2:
            roc_value = float(roc_auc_score(binary_target, probabilities[:, class_idx]))
            pr_value = float(average_precision_score(binary_target, probabilities[:, class_idx]))
            roc_values.append(roc_value)
            pr_values.append(pr_value)
        per_class[str(int(class_label))] = {
            "support": int(support[class_idx]),
            "precision": float(precision[class_idx]),
            "recall": float(recall[class_idx]),
            "f1": float(per_class_f1[class_idx]),
            "roc_auc_ovr": roc_value,
            "pr_auc_ovr": pr_value,
        }

    reliability, ece = _reliability_rows(
        y,
        probabilities,
        resolved_labels,
        bins=int(calibration_bins),
    )
    probability_distribution: dict[str, dict[str, float]] = {}
    probability_deciles: dict[str, list[dict[str, float]]] = {}
    for idx, class_label in enumerate(resolved_labels):
        values = pd.Series(probabilities[:, idx], dtype=float)
        probability_distribution[str(int(class_label))] = {
            "mean": float(values.mean()),
            "std": float(values.std(ddof=0)),
            "min": float(values.min()),
            "q25": float(values.quantile(0.25)),
            "median": float(values.median()),
            "q75": float(values.quantile(0.75)),
            "max": float(values.max()),
        }
        probability_deciles[str(int(class_label))] = [
            {"quantile": float(q), "value": float(values.quantile(q))}
            for q in np.linspace(0.0, 1.0, 11)
        ]

    class_rates = {
        str(int(label)): float(np.mean(y == label))
        for label in resolved_labels
    }
    return {
        "evaluation_rows": int(len(y)),
        "class_labels": [int(value) for value in resolved_labels],
        "class_rates": class_rates,
        "accuracy": float(accuracy_score(y, predicted)),
        "balanced_accuracy": float(balanced_accuracy_score(y, predicted)),
        "macro_f1": float(f1_score(y, predicted, labels=resolved_labels, average="macro", zero_division=0)),
        "multiclass_brier": float(np.mean(np.sum(np.square(probabilities - one_hot), axis=1))),
        "log_loss": float(log_loss(y, probabilities, labels=resolved_labels)),
        "roc_auc_ovr_macro": float(np.mean(roc_values)) if roc_values else None,
        "pr_auc_ovr_macro": float(np.mean(pr_values)) if pr_values else None,
        "expected_calibration_error": ece,
        "per_class": per_class,
        "confusion_matrix": confusion_matrix(y, predicted, labels=resolved_labels).astype(int).tolist(),
        "reliability": reliability,
        "probability_distribution": probability_distribution,
        "probability_deciles": probability_deciles,
    }


def multiclass_baseline_metrics(
    train_labels: pd.Series,
    eval_labels: pd.Series,
    *,
    class_labels: list[int] | np.ndarray,
    last_returns: pd.Series | None = None,
    random_seed: int = 7,
) -> dict[str, dict[str, object]]:
    """Evaluate fold-local majority, empirical-random, and last-return baselines."""
    classes = np.asarray(class_labels, dtype=int)
    train = train_labels.dropna().astype(int)
    evaluation = eval_labels.dropna().astype(int)
    if train.empty or evaluation.empty:
        return {}
    priors = np.asarray([float(np.mean(train.to_numpy(dtype=int) == label)) for label in classes])
    if float(priors.sum()) <= 0.0:
        return {}
    priors = priors / priors.sum()
    majority_idx = int(np.argmax(priors))
    majority = np.zeros((len(evaluation), len(classes)), dtype=float)
    majority[:, majority_idx] = 1.0
    empirical = np.tile(priors, (len(evaluation), 1))
    baseline_probabilities: dict[str, np.ndarray] = {
        "majority_class": majority,
        "empirical_random": empirical,
    }
    if last_returns is not None:
        aligned_returns = last_returns.reindex(evaluation.index).fillna(0.0).to_numpy(dtype=float)
        for name, multiplier in (("last_return_continuation", 1), ("last_return_reversal", -1)):
            labels = np.sign(aligned_returns).astype(int) * int(multiplier)
            labels[labels == 0] = 0
            probabilities = np.zeros((len(evaluation), len(classes)), dtype=float)
            for row_idx, label in enumerate(labels):
                match = np.flatnonzero(classes == label)
                probabilities[row_idx, int(match[0]) if len(match) else majority_idx] = 1.0
            baseline_probabilities[name] = probabilities

    results: dict[str, dict[str, object]] = {}
    for name, probabilities in baseline_probabilities.items():
        frame = pd.DataFrame(probabilities, index=evaluation.index, columns=classes)
        metrics = multiclass_classification_metrics(
            evaluation,
            frame,
            class_labels=classes,
        )
        if name == "empirical_random":
            rng = np.random.default_rng(int(random_seed))
            sampled = rng.choice(classes, size=len(evaluation), p=priors)
            metrics["sampled_accuracy"] = float(np.mean(sampled == evaluation.to_numpy(dtype=int)))
            metrics["train_class_probabilities"] = {
                str(int(label)): float(prior) for label, prior in zip(classes, priors)
            }
        results[name] = metrics
    return results


def empty_regression_metrics() -> dict[str, float | int | None]:
    return {
        "evaluation_rows": 0,
        "mae": None,
        "rmse": None,
        "mse": None,
        "r2": None,
        "correlation": None,
        "directional_accuracy": None,
        "mean_prediction": None,
        "mean_target": None,
    }


def empty_volatility_metrics() -> dict[str, float | int | None]:
    return {
        "evaluation_rows": 0,
        "mae": None,
        "rmse": None,
        "correlation": None,
        "mean_prediction": None,
        "mean_target": None,
    }


def binary_classification_metrics(
    y_true: pd.Series,
    pred_prob: pd.Series,
) -> dict[str, float | int | None]:
    if y_true.empty or pred_prob.empty:
        return empty_classification_metrics()
    if y_true.index.has_duplicates or pred_prob.index.has_duplicates:
        raise ValueError("Binary classification metric inputs must have unique indexes.")
    common_index = y_true.index.intersection(pred_prob.index)
    if len(common_index) == 0:
        raise ValueError("Binary classification metric inputs have no overlapping index.")
    aligned = pd.concat(
        [
            y_true.reindex(common_index).rename("y_true"),
            pred_prob.reindex(common_index).rename("pred_prob"),
        ],
        axis=1,
    ).dropna()
    if aligned.empty:
        return empty_classification_metrics()

    y = aligned["y_true"].astype(int).to_numpy(dtype=int, copy=False)
    prob = aligned["pred_prob"].astype(float).to_numpy(dtype=float, copy=False)
    if not np.isfinite(prob).all() or bool(((prob < 0.0) | (prob > 1.0)).any()):
        raise ValueError("Binary classification probabilities must be finite and within [0, 1].")
    pred_label = (prob >= 0.5).astype(int)

    metrics: dict[str, float | int | None] = {
        "evaluation_rows": int(len(y)),
        "positive_rate": float(np.mean(y)),
        "accuracy": float(accuracy_score(y, pred_label)),
        "brier": float(brier_score_loss(y, prob)),
        "roc_auc": None,
        "log_loss": None,
    }
    if len(np.unique(y)) >= 2:
        metrics["roc_auc"] = float(roc_auc_score(y, prob))
        metrics["log_loss"] = float(log_loss(y, prob, labels=[0, 1]))
    return metrics


def regression_metrics(
    y_true: pd.Series,
    y_pred: pd.Series,
) -> dict[str, float | int | None]:
    if y_true.empty or y_pred.empty:
        return empty_regression_metrics()

    yt = y_true.astype(float)
    yp = y_pred.astype(float).reindex(yt.index)
    valid = yt.notna() & yp.notna()
    if not bool(valid.any()):
        return empty_regression_metrics()

    yt = yt.loc[valid]
    yp = yp.loc[valid]
    err = yp - yt
    mse = float(np.mean(np.square(err)))
    rmse = float(np.sqrt(mse))
    mae = float(np.mean(np.abs(err)))

    sst = float(np.sum(np.square(yt - yt.mean())))
    sse = float(np.sum(np.square(err)))
    r2 = float(1.0 - (sse / sst)) if sst > 1e-12 else None
    corr = None
    if len(yt) >= 2 and float(yt.std(ddof=1)) > 0 and float(yp.std(ddof=1)) > 0:
        corr = float(np.corrcoef(yt.to_numpy(dtype=float), yp.to_numpy(dtype=float))[0, 1])

    directional_accuracy = float((np.sign(yt) == np.sign(yp)).mean())
    return {
        "evaluation_rows": int(len(yt)),
        "mae": mae,
        "rmse": rmse,
        "mse": mse,
        "r2": r2,
        "correlation": corr,
        "directional_accuracy": directional_accuracy,
        "mean_prediction": float(yp.mean()),
        "mean_target": float(yt.mean()),
    }


def volatility_metrics(
    realized: pd.Series,
    predicted: pd.Series,
) -> dict[str, float | int | None]:
    if realized.empty or predicted.empty:
        return empty_volatility_metrics()

    y_true = realized.astype(float)
    y_pred = predicted.astype(float).reindex(y_true.index)
    valid = y_true.notna() & y_pred.notna()
    if not bool(valid.any()):
        return empty_volatility_metrics()

    y_true = y_true.loc[valid]
    y_pred = y_pred.loc[valid]
    err = y_pred - y_true
    mse = float(np.mean(np.square(err)))
    rmse = float(np.sqrt(mse))
    mae = float(np.mean(np.abs(err)))

    corr = None
    if len(y_true) >= 2 and float(y_true.std(ddof=1)) > 0 and float(y_pred.std(ddof=1)) > 0:
        corr = float(np.corrcoef(y_true.to_numpy(dtype=float), y_pred.to_numpy(dtype=float))[0, 1])

    return {
        "evaluation_rows": int(len(y_true)),
        "mae": mae,
        "rmse": rmse,
        "correlation": corr,
        "mean_prediction": float(y_pred.mean()),
        "mean_target": float(y_true.mean()),
    }


def fit_forecast_probability_scale(
    train_target: pd.Series,
    *,
    configured_scale: float | None = None,
) -> float:
    if configured_scale is not None:
        scale = float(abs(configured_scale))
        if not np.isfinite(scale) or scale <= 1e-8:
            raise ValueError("Configured forecast probability scale must be finite and > 1e-8.")
        return scale
    values = train_target.astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    scale = float(values.std(ddof=1)) if len(values) >= 2 else np.nan
    return scale if np.isfinite(scale) and scale > 1e-8 else 1.0


def forecast_to_probability(prediction: pd.Series, *, scale: float | None) -> pd.Series:
    if prediction.empty:
        return pd.Series(dtype="float32", index=prediction.index)
    denom = float(abs(scale)) if scale is not None else np.nan
    if not np.isfinite(denom) or denom <= 1e-8:
        raise ValueError(
            "forecast_to_probability requires a finite train-fitted scale; "
            "inference-batch scaling is forbidden."
        )
    logits = np.clip(prediction.astype(float).to_numpy(dtype=float) / denom, -25.0, 25.0)
    probs = 1.0 / (1.0 + np.exp(-logits))
    return pd.Series(probs.astype("float32"), index=prediction.index, dtype="float32")


__all__ = [
    "binary_classification_metrics",
    "empty_classification_metrics",
    "empty_multiclass_classification_metrics",
    "empty_regression_metrics",
    "empty_volatility_metrics",
    "fit_forecast_probability_scale",
    "forecast_to_probability",
    "multiclass_baseline_metrics",
    "multiclass_classification_metrics",
    "regression_metrics",
    "volatility_metrics",
]
