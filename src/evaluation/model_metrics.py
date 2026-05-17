from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score


def empty_classification_metrics() -> dict[str, float | int | None]:
    return {
        "evaluation_rows": 0,
        "positive_rate": None,
        "accuracy": None,
        "brier": None,
        "roc_auc": None,
        "log_loss": None,
    }


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

    y = y_true.astype(int).to_numpy(dtype=int, copy=False)
    prob = pred_prob.astype(float).to_numpy(dtype=float, copy=False)
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


def forecast_to_probability(prediction: pd.Series, *, scale: float | None) -> pd.Series:
    if prediction.empty:
        return pd.Series(dtype="float32", index=prediction.index)
    denom = float(abs(scale)) if scale is not None else 0.0
    if not np.isfinite(denom) or denom <= 1e-8:
        denom = float(np.nanstd(prediction.to_numpy(dtype=float), ddof=1))
    if not np.isfinite(denom) or denom <= 1e-8:
        denom = 1.0
    logits = np.clip(prediction.astype(float).to_numpy(dtype=float) / denom, -25.0, 25.0)
    probs = 1.0 / (1.0 + np.exp(-logits))
    return pd.Series(probs.astype("float32"), index=prediction.index, dtype="float32")


__all__ = [
    "binary_classification_metrics",
    "empty_classification_metrics",
    "empty_regression_metrics",
    "empty_volatility_metrics",
    "forecast_to_probability",
    "regression_metrics",
    "volatility_metrics",
]
