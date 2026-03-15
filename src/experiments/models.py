from __future__ import annotations

from typing import Any, Callable, Iterable, Sequence

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score

from src.evaluation.time_splits import (
    assert_no_forward_label_leakage,
    build_time_splits,
    trim_train_indices_for_horizon,
)
from src.experiments.contracts import TargetContract, validate_feature_target_contract
from src.models.garch import make_garch_fold_predictor
from src.models.lightgbm_baseline import default_feature_columns
from src.models.sarimax import train_sarimax_fold
from src.models.tft import make_tft_fold_predictor

EstimatorFactory = Callable[[dict[str, Any]], object]
ForecasterFoldPredictor = Callable[
    [pd.DataFrame, np.ndarray, np.ndarray, list[str], str, dict[str, Any], dict[str, Any]],
    tuple[pd.Series, dict[str, pd.Series], object, dict[str, Any]],
]


def _resolve_runtime_for_model(
    model_cfg: dict[str, Any],
    model_params: dict[str, Any],
    *,
    estimator_family: str,
) -> dict[str, Any]:
    """
    Handle runtime for model inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    runtime_cfg = dict(model_cfg.get("runtime", {}) or {})

    seed = runtime_cfg.get("seed", model_params.get("random_state", 7))
    if not isinstance(seed, int) or seed < 0:
        raise ValueError("model.runtime.seed must be an integer >= 0.")

    deterministic = runtime_cfg.get("deterministic", True)
    if not isinstance(deterministic, bool):
        raise ValueError("model.runtime.deterministic must be a boolean.")

    repro_mode = runtime_cfg.get("repro_mode", "strict")
    if repro_mode not in {"strict", "relaxed"}:
        raise ValueError("model.runtime.repro_mode must be 'strict' or 'relaxed'.")

    threads = runtime_cfg.get("threads")
    if threads is not None and (not isinstance(threads, int) or threads <= 0):
        raise ValueError("model.runtime.threads must be null or a positive integer.")
    if repro_mode == "strict" and threads is None:
        threads = 1

    model_params.setdefault("random_state", seed)
    if estimator_family == "lightgbm":
        model_params.setdefault("seed", seed)
        if deterministic:
            model_params.setdefault("deterministic", True)
            model_params.setdefault("force_col_wise", True)
            model_params.setdefault("feature_fraction_seed", seed)
            model_params.setdefault("bagging_seed", seed)
            model_params.setdefault("data_random_seed", seed)

    if threads is not None:
        model_params.setdefault("n_jobs", threads)

    return {
        "seed": seed,
        "deterministic": deterministic,
        "threads": model_params.get("n_jobs", threads),
        "repro_mode": repro_mode,
    }


def infer_feature_columns(
    df: pd.DataFrame,
    explicit_cols: Sequence[str] | None = None,
    exclude: Iterable[str] | None = None,
) -> list[str]:
    """
    Infer feature columns from the available inputs when the caller has not specified them
    explicitly. The heuristic is isolated here so it can evolve without obscuring the rest of
    the experiment orchestration flow.
    """
    if explicit_cols:
        missing = [c for c in explicit_cols if c not in df.columns]
        if missing:
            raise KeyError(f"Missing feature columns: {missing}")
        return list(explicit_cols)

    inferred = default_feature_columns(df)
    if inferred:
        return inferred

    exclude_set = set(exclude or [])
    exclude_set.update({"open", "high", "low", "close", "adj_close", "volume"})

    numeric_cols = df.select_dtypes(include=["number"]).columns
    features: list[str] = []
    for col in numeric_cols:
        if col in exclude_set:
            continue
        if col.startswith(("signal_", "pred_", "target_")):
            continue
        features.append(col)
    return features


def _build_forward_return_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Handle forward return target inside the experiment orchestration layer. The helper isolates
    one focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    cfg = dict(target_cfg or {})
    price_col = cfg.get("price_col", "close")
    horizon = int(cfg.get("horizon", 1))
    if horizon <= 0:
        raise ValueError("target.horizon must be a positive integer.")
    fwd_col = cfg.get("fwd_col", f"target_fwd_{horizon}")
    label_col = cfg.get("label_col", "label")
    threshold = float(cfg.get("threshold", 0.0))
    quantiles = cfg.get("quantiles")

    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")

    out = df.copy()
    out[fwd_col] = out[price_col].pct_change(periods=horizon).shift(-horizon)

    valid_mask = out[fwd_col].notna()
    out[label_col] = np.nan
    if quantiles:
        if not isinstance(quantiles, (list, tuple)) or len(quantiles) != 2:
            raise ValueError("target.quantiles must be a [low, high] pair")
        q_low, q_high = float(quantiles[0]), float(quantiles[1])
        if not (0.0 <= q_low < q_high <= 1.0):
            raise ValueError("target.quantiles must satisfy 0 <= low < high <= 1")
    else:
        out.loc[valid_mask, label_col] = (
            out.loc[valid_mask, fwd_col] > threshold
        ).astype("float32")

    meta = {
        "kind": "forward_return",
        "price_col": price_col,
        "horizon": horizon,
        "fwd_col": fwd_col,
        "label_col": label_col,
        "threshold": threshold,
        "quantiles": quantiles,
    }
    return out, label_col, fwd_col, meta


def _assign_quantile_labels(
    forward_returns: pd.Series,
    *,
    low_value: float,
    high_value: float,
) -> pd.Series:
    """
    Handle assign quantile labels inside the experiment orchestration layer. The helper isolates
    one focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    labels = pd.Series(np.nan, index=forward_returns.index, dtype="float32")
    labels.loc[forward_returns <= float(low_value)] = 0.0
    labels.loc[forward_returns >= float(high_value)] = 1.0
    return labels


def _empty_classification_metrics() -> dict[str, float | int | None]:
    """
    Build an empty binary-classification summary payload.
    """
    return {
        "evaluation_rows": 0,
        "positive_rate": None,
        "accuracy": None,
        "brier": None,
        "roc_auc": None,
        "log_loss": None,
    }


def _empty_regression_metrics() -> dict[str, float | int | None]:
    """
    Build an empty regression summary payload.
    """
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


def _empty_volatility_metrics() -> dict[str, float | int | None]:
    """
    Build an empty volatility-forecast summary payload.
    """
    return {
        "evaluation_rows": 0,
        "mae": None,
        "rmse": None,
        "correlation": None,
        "mean_prediction": None,
        "mean_target": None,
    }


def _binary_classification_metrics(
    y_true: pd.Series,
    pred_prob: pd.Series,
) -> dict[str, float | int | None]:
    """
    Handle binary classification metrics inside the experiment orchestration layer. The helper
    isolates one focused responsibility so the surrounding code remains modular, readable, and
    easier to test.
    """
    if y_true.empty or pred_prob.empty:
        return _empty_classification_metrics()

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


def _regression_metrics(
    y_true: pd.Series,
    y_pred: pd.Series,
) -> dict[str, float | int | None]:
    """
    Compute regression diagnostics for out-of-sample predictions.
    """
    if y_true.empty or y_pred.empty:
        return _empty_regression_metrics()

    yt = y_true.astype(float)
    yp = y_pred.astype(float).reindex(yt.index)
    valid = yt.notna() & yp.notna()
    if not bool(valid.any()):
        return _empty_regression_metrics()

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


def _volatility_metrics(
    realized: pd.Series,
    predicted: pd.Series,
) -> dict[str, float | int | None]:
    """
    Compute volatility forecast diagnostics against a realized magnitude proxy.
    """
    if realized.empty or predicted.empty:
        return _empty_volatility_metrics()

    y_true = realized.astype(float)
    y_pred = predicted.astype(float).reindex(y_true.index)
    valid = y_true.notna() & y_pred.notna()
    if not bool(valid.any()):
        return _empty_volatility_metrics()

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


def _forecast_to_probability(prediction: pd.Series, *, scale: float | None) -> pd.Series:
    """
    Map return forecasts to a [0, 1] directional confidence using a logistic link.
    """
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


def _train_forward_classifier(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    *,
    model_kind: str,
    estimator_family: str,
    estimator_factory: EstimatorFactory,
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Handle forward classifier inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    model_cfg = dict(model_cfg or {})
    model_params = dict(model_cfg.get("params", {}) or {})
    runtime_meta = _resolve_runtime_for_model(
        model_cfg=model_cfg,
        model_params=model_params,
        estimator_family=estimator_family,
    )

    pred_prob_col = model_cfg.get("pred_prob_col", "pred_prob")
    target_cfg = model_cfg.get("target", {}) or {}
    target_kind = target_cfg.get("kind", "forward_return")
    if target_kind != "forward_return":
        raise ValueError(f"Unsupported target.kind: {target_kind}")

    out, label_col, fwd_col, target_meta = _build_forward_return_target(df=df, target_cfg=target_cfg)

    contract_df = out
    contract_target_col = label_col
    if target_meta.get("quantiles") is not None:
        contract_target_col = "__contract_label__"
        contract_df = out.copy()
        valid_mask = contract_df[fwd_col].notna()
        contract_df[contract_target_col] = np.nan
        contract_df.loc[valid_mask, contract_target_col] = (
            contract_df.loc[valid_mask, fwd_col] > float(target_meta["threshold"])
        ).astype("float32")

    feature_cols = infer_feature_columns(
        out,
        explicit_cols=model_cfg.get("feature_cols"),
        exclude={label_col, fwd_col, pred_prob_col},
    )
    if not feature_cols:
        raise ValueError("No feature columns resolved for model training.")

    contract_meta = validate_feature_target_contract(
        contract_df,
        feature_cols=feature_cols,
        target=TargetContract(target_col=contract_target_col, horizon=int(target_meta["horizon"])),
    )

    split_cfg = model_cfg.get("split", {}) or {}
    method = split_cfg.get("method", "time")
    if method not in {"time", "walk_forward", "purged"}:
        raise ValueError(f"Unsupported split.method: {method}")

    splits = build_time_splits(
        method=method,
        n_samples=len(out),
        split_cfg=dict(split_cfg),
        target_horizon=int(target_meta.get("horizon", 1)),
    )

    pred_prob = pd.Series(np.nan, index=out.index, name=pred_prob_col, dtype="float32")
    oos_mask = pd.Series(False, index=out.index, name="pred_is_oos")
    oos_assignment_count = pd.Series(0, index=out.index, dtype="int32")

    fold_meta: list[dict[str, Any]] = []
    model: object | None = None
    total_train_rows = 0
    total_test_pred_rows = 0
    total_trimmed_rows = 0
    target_horizon = int(target_meta["horizon"])
    all_eval_labels: list[np.ndarray] = []
    all_eval_probs: list[np.ndarray] = []

    for split in splits:
        raw_train_idx = split.train_idx
        safe_train_idx = trim_train_indices_for_horizon(
            raw_train_idx,
            test_start=int(split.test_start),
            target_horizon=target_horizon,
        )
        assert_no_forward_label_leakage(
            safe_train_idx,
            test_start=int(split.test_start),
            target_horizon=target_horizon,
        )

        trimmed_rows = int(len(raw_train_idx) - len(safe_train_idx))
        total_trimmed_rows += trimmed_rows

        train_df = out.iloc[safe_train_idx]
        test_df = out.iloc[split.test_idx]
        quantile_low_value: float | None = None
        quantile_high_value: float | None = None
        if target_meta.get("quantiles") is not None:
            q_low, q_high = target_meta["quantiles"]
            train_fwd = train_df[fwd_col].dropna()
            if train_fwd.empty:
                raise ValueError(f"Fold {split.fold} has no forward returns for quantile labeling.")
            quantile_low_value = float(train_fwd.quantile(float(q_low)))
            quantile_high_value = float(train_fwd.quantile(float(q_high)))
            train_df = train_df.copy()
            train_df[label_col] = _assign_quantile_labels(
                train_df[fwd_col],
                low_value=quantile_low_value,
                high_value=quantile_high_value,
            )

        train_fit = train_df.dropna(subset=feature_cols + [label_col])
        if train_fit.empty:
            raise ValueError(f"Fold {split.fold} has no train rows after dropping NaNs in features/labels.")

        X_train = train_fit[feature_cols]
        y_train = train_fit[label_col].astype(int)
        if int(y_train.nunique()) < 2:
            raise ValueError(f"Fold {split.fold} has a single target class after preprocessing.")

        model = estimator_factory(model_params)
        model.fit(X_train, y_train)

        test_features = test_df[feature_cols]
        valid_mask = test_features.notna().all(axis=1)
        pred_rows = int(valid_mask.sum())
        pred_index = test_features.loc[valid_mask].index
        fold_eval_metrics = _empty_classification_metrics()

        if pred_rows > 0:
            proba = model.predict_proba(test_features.loc[valid_mask])[:, 1].astype("float32")
            pred_series = pd.Series(proba, index=pred_index, dtype="float32")
            pred_prob.loc[pred_index] = pred_series

            if target_meta.get("quantiles") is not None:
                test_labels = _assign_quantile_labels(
                    test_df[fwd_col],
                    low_value=float(quantile_low_value),
                    high_value=float(quantile_high_value),
                )
            else:
                test_labels = test_df[label_col]

            eval_labels = test_labels.reindex(pred_index)
            labeled_mask = eval_labels.notna()
            if bool(labeled_mask.any()):
                y_eval = eval_labels.loc[labeled_mask].astype(int)
                p_eval = pred_series.loc[labeled_mask]
                fold_eval_metrics = _binary_classification_metrics(y_eval, p_eval)
                all_eval_labels.append(y_eval.to_numpy(dtype=int, copy=False))
                all_eval_probs.append(p_eval.to_numpy(dtype=float, copy=False))

        fold_test_idx = out.index[split.test_idx]
        oos_mask.loc[fold_test_idx] = True
        oos_assignment_count.loc[fold_test_idx] += 1

        total_train_rows += int(len(train_fit))
        total_test_pred_rows += pred_rows
        fold_meta.append(
            {
                "fold": int(split.fold),
                "train_start": int(split.train_start),
                "train_end": int(split.train_end),
                "effective_train_start": int(safe_train_idx.min()) if len(safe_train_idx) else None,
                "effective_train_end": int(safe_train_idx.max() + 1) if len(safe_train_idx) else None,
                "trimmed_for_horizon_rows": trimmed_rows,
                "test_start": int(split.test_start),
                "test_end": int(split.test_end),
                "train_rows": int(len(train_fit)),
                "test_rows": int(len(split.test_idx)),
                "test_pred_rows": pred_rows,
                "quantile_low_value": quantile_low_value,
                "quantile_high_value": quantile_high_value,
                "classification_metrics": fold_eval_metrics,
                "regression_metrics": _empty_regression_metrics(),
                "volatility_metrics": _empty_volatility_metrics(),
            }
        )

    if model is None:
        raise ValueError("Model training failed: no valid folds were trained.")

    if (oos_assignment_count > 1).any():
        raise ValueError("Overlapping test windows detected. Use non-overlapping split configuration.")

    oos_classification_summary = _empty_classification_metrics()
    if all_eval_labels and all_eval_probs:
        y_all = pd.Series(np.concatenate(all_eval_labels), dtype=int)
        p_all = pd.Series(np.concatenate(all_eval_probs), dtype=float)
        oos_classification_summary = _binary_classification_metrics(y_all, p_all)

    out[pred_prob_col] = pred_prob
    out["pred_is_oos"] = oos_mask

    meta = {
        "model_kind": model_kind,
        "runtime": runtime_meta,
        "feature_cols": feature_cols,
        "pred_prob_col": pred_prob_col,
        "label_col": label_col,
        "fwd_col": fwd_col,
        "split_method": method,
        "split_index": int(splits[0].test_start),
        "n_folds": int(len(splits)),
        "folds": fold_meta,
        "train_rows": int(total_train_rows),
        "test_pred_rows": int(total_test_pred_rows),
        "oos_rows": int(oos_mask.sum()),
        "oos_prediction_coverage": float(total_test_pred_rows / max(int(oos_mask.sum()), 1)),
        "oos_classification_summary": oos_classification_summary,
        "oos_regression_summary": _empty_regression_metrics(),
        "oos_volatility_summary": _empty_volatility_metrics(),
        "target": target_meta,
        "returns_col": returns_col,
        "contracts": contract_meta,
        "anti_leakage": {
            "target_horizon": target_horizon,
            "total_trimmed_train_rows": int(total_trimmed_rows),
        },
    }
    return out, model, meta


def _prepare_forecaster_inputs(
    *,
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    model_params: dict[str, Any],
    pred_ret_col: str,
    pred_prob_col: str,
    required_features: bool,
    runtime_estimator_family: str,
) -> tuple[
    pd.DataFrame,
    list[str],
    str,
    dict[str, Any],
    list[Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    """
    Resolve and validate shared inputs for forecasting model families.
    """
    runtime_meta = _resolve_runtime_for_model(
        model_cfg=model_cfg,
        model_params=model_params,
        estimator_family=runtime_estimator_family,
    )
    target_cfg = dict(model_cfg.get("target", {}) or {})
    target_kind = target_cfg.get("kind", "forward_return")
    if target_kind != "forward_return":
        raise ValueError(f"Unsupported target.kind: {target_kind}")

    out, label_col, fwd_col, target_meta = _build_forward_return_target(df=df, target_cfg=target_cfg)
    split_cfg = dict(model_cfg.get("split", {}) or {})
    split_method = split_cfg.get("method", "time")
    if split_method not in {"time", "walk_forward", "purged"}:
        raise ValueError(f"Unsupported split.method: {split_method}")

    feature_cols = infer_feature_columns(
        out,
        explicit_cols=model_cfg.get("feature_cols"),
        exclude={label_col, fwd_col, pred_ret_col, pred_prob_col},
    )
    use_exogenous_features = bool(model_cfg.get("use_features", True))
    active_feature_cols = feature_cols if use_exogenous_features else []
    if required_features and not active_feature_cols:
        raise ValueError("No feature columns resolved for model training.")
    contract_meta: dict[str, Any] = {}
    if active_feature_cols:
        contract_meta = validate_feature_target_contract(
            out,
            feature_cols=active_feature_cols,
            target=TargetContract(target_col=fwd_col, horizon=int(target_meta["horizon"])),
        )

    splits = build_time_splits(
        method=split_method,
        n_samples=len(out),
        split_cfg=split_cfg,
        target_horizon=int(target_meta.get("horizon", 1)),
    )
    return (
        out,
        active_feature_cols,
        fwd_col,
        target_meta,
        splits,
        runtime_meta,
        contract_meta,
        {"split_method": split_method},
    )


def _train_forward_forecaster(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    *,
    model_kind: str,
    fold_predictor: ForecasterFoldPredictor,
    returns_col: str | None = None,
    required_features: bool = False,
    runtime_estimator_family: str = "statsmodels",
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Train one-step forward forecasters with a shared anti-leakage split loop.
    """
    model_cfg = dict(model_cfg or {})
    model_params = dict(model_cfg.get("params", {}) or {})
    pred_ret_col = str(model_cfg.get("pred_ret_col", "pred_ret"))
    pred_prob_col = str(model_cfg.get("pred_prob_col", "pred_prob"))

    (
        out,
        feature_cols,
        fwd_col,
        target_meta,
        splits,
        runtime_meta,
        contract_meta,
        split_meta,
    ) = _prepare_forecaster_inputs(
        df=df,
        model_cfg=model_cfg,
        model_params=model_params,
        pred_ret_col=pred_ret_col,
        pred_prob_col=pred_prob_col,
        required_features=required_features,
        runtime_estimator_family=runtime_estimator_family,
    )

    pred_ret = pd.Series(np.nan, index=out.index, name=pred_ret_col, dtype="float32")
    pred_prob = pd.Series(np.nan, index=out.index, name=pred_prob_col, dtype="float32")
    oos_mask = pd.Series(False, index=out.index, name="pred_is_oos")
    oos_assignment_count = pd.Series(0, index=out.index, dtype="int32")
    extra_prediction_cols: dict[str, pd.Series] = {}

    fold_meta: list[dict[str, Any]] = []
    model: object | None = None
    total_train_rows = 0
    total_test_pred_rows = 0
    total_trimmed_rows = 0
    target_horizon = int(target_meta["horizon"])
    threshold = float(target_meta.get("threshold", 0.0))

    y_eval_all: list[np.ndarray] = []
    y_pred_all: list[np.ndarray] = []
    y_prob_all: list[np.ndarray] = []
    y_vol_pred_all: list[np.ndarray] = []
    y_vol_true_all: list[np.ndarray] = []

    for split in splits:
        raw_train_idx = np.asarray(split.train_idx, dtype=int)
        safe_train_idx = trim_train_indices_for_horizon(
            raw_train_idx,
            test_start=int(split.test_start),
            target_horizon=target_horizon,
        )
        assert_no_forward_label_leakage(
            safe_train_idx,
            test_start=int(split.test_start),
            target_horizon=target_horizon,
        )
        trimmed_rows = int(len(raw_train_idx) - len(safe_train_idx))
        total_trimmed_rows += trimmed_rows

        pred_ret_fold, extra_cols_fold, fitted_model, fold_extra_meta = fold_predictor(
            out,
            safe_train_idx,
            np.asarray(split.test_idx, dtype=int),
            feature_cols,
            fwd_col,
            model_params,
            runtime_meta,
        )
        model = fitted_model

        test_index = out.index[np.asarray(split.test_idx, dtype=int)]
        pred_ret_fold = pd.Series(pred_ret_fold, copy=False).astype(float)
        pred_ret_fold = pred_ret_fold.loc[pred_ret_fold.index.intersection(test_index)]
        pred_ret.loc[pred_ret_fold.index] = pred_ret_fold.astype("float32")

        for col_name, values in dict(extra_cols_fold or {}).items():
            if col_name not in extra_prediction_cols:
                extra_prediction_cols[col_name] = pd.Series(
                    np.nan, index=out.index, name=col_name, dtype="float32"
                )
            series = pd.Series(values, copy=False).astype(float)
            series = series.loc[series.index.intersection(test_index)]
            extra_prediction_cols[col_name].loc[series.index] = series.astype("float32")

        fold_scale = fold_extra_meta.get("prob_scale")
        fold_prob = _forecast_to_probability(pred_ret_fold, scale=fold_scale)
        pred_prob.loc[fold_prob.index] = fold_prob

        eval_true = out.loc[pred_ret_fold.index, fwd_col].astype(float)
        eval_true = eval_true.loc[eval_true.notna()]
        eval_pred = pred_ret_fold.reindex(eval_true.index).astype(float)
        eval_prob = fold_prob.reindex(eval_true.index).astype(float)

        regression_metrics = _regression_metrics(eval_true, eval_pred)
        classification_metrics = _binary_classification_metrics((eval_true > threshold).astype(int), eval_prob)
        volatility_metrics = _empty_volatility_metrics()
        pred_vol_col_name: str | None = None
        if "pred_vol" in extra_cols_fold:
            pred_vol_col_name = "pred_vol"
        else:
            for key in extra_cols_fold:
                if str(key).startswith("pred_vol"):
                    pred_vol_col_name = str(key)
                    break
        if pred_vol_col_name is not None:
            pred_vol = pd.Series(extra_cols_fold[pred_vol_col_name], copy=False).astype(float)
            pred_vol_eval = pred_vol.reindex(eval_true.index)
            realized_vol = eval_true.abs()
            volatility_metrics = _volatility_metrics(realized_vol, pred_vol_eval)
            if volatility_metrics["evaluation_rows"] and volatility_metrics["evaluation_rows"] > 0:
                y_vol_pred_all.append(pred_vol_eval.to_numpy(dtype=float))
                y_vol_true_all.append(realized_vol.to_numpy(dtype=float))

        if regression_metrics["evaluation_rows"] and regression_metrics["evaluation_rows"] > 0:
            y_eval_all.append(eval_true.to_numpy(dtype=float))
            y_pred_all.append(eval_pred.to_numpy(dtype=float))
        if classification_metrics["evaluation_rows"] and classification_metrics["evaluation_rows"] > 0:
            y_prob_all.append(eval_prob.to_numpy(dtype=float))

        fold_test_idx = out.index[np.asarray(split.test_idx, dtype=int)]
        oos_mask.loc[fold_test_idx] = True
        oos_assignment_count.loc[fold_test_idx] += 1

        train_target_rows = int(out.iloc[safe_train_idx][fwd_col].notna().sum())
        total_train_rows += train_target_rows
        total_test_pred_rows += int(len(pred_ret_fold))

        fold_record = {
            "fold": int(split.fold),
            "train_start": int(split.train_start),
            "train_end": int(split.train_end),
            "effective_train_start": int(safe_train_idx.min()) if len(safe_train_idx) else None,
            "effective_train_end": int(safe_train_idx.max() + 1) if len(safe_train_idx) else None,
            "trimmed_for_horizon_rows": trimmed_rows,
            "test_start": int(split.test_start),
            "test_end": int(split.test_end),
            "train_rows": train_target_rows,
            "test_rows": int(len(split.test_idx)),
            "test_pred_rows": int(len(pred_ret_fold)),
            "classification_metrics": classification_metrics,
            "regression_metrics": regression_metrics,
            "volatility_metrics": volatility_metrics,
        }
        fold_record.update(dict(fold_extra_meta or {}))
        fold_meta.append(fold_record)

    if model is None:
        raise ValueError("Model training failed: no valid folds were trained.")
    if (oos_assignment_count > 1).any():
        raise ValueError("Overlapping test windows detected. Use non-overlapping split configuration.")

    oos_regression_summary = _empty_regression_metrics()
    if y_eval_all and y_pred_all:
        y_true_series = pd.Series(np.concatenate(y_eval_all), dtype=float)
        y_pred_series = pd.Series(np.concatenate(y_pred_all), dtype=float)
        oos_regression_summary = _regression_metrics(y_true_series, y_pred_series)

    oos_classification_summary = _empty_classification_metrics()
    if y_eval_all and y_prob_all:
        y_bin_series = pd.Series(np.concatenate(y_eval_all) > threshold, dtype=int)
        y_prob_series = pd.Series(np.concatenate(y_prob_all), dtype=float)
        oos_classification_summary = _binary_classification_metrics(y_bin_series, y_prob_series)

    oos_volatility_summary = _empty_volatility_metrics()
    if y_vol_true_all and y_vol_pred_all:
        y_vol_true_series = pd.Series(np.concatenate(y_vol_true_all), dtype=float)
        y_vol_pred_series = pd.Series(np.concatenate(y_vol_pred_all), dtype=float)
        oos_volatility_summary = _volatility_metrics(y_vol_true_series, y_vol_pred_series)

    out[pred_ret_col] = pred_ret
    out[pred_prob_col] = pred_prob
    out["pred_is_oos"] = oos_mask
    for col_name, series in sorted(extra_prediction_cols.items(), key=lambda kv: str(kv[0])):
        out[col_name] = series

    meta = {
        "model_kind": model_kind,
        "runtime": runtime_meta,
        "feature_cols": feature_cols,
        "pred_ret_col": pred_ret_col,
        "pred_prob_col": pred_prob_col,
        "fwd_col": fwd_col,
        "split_method": split_meta["split_method"],
        "split_index": int(splits[0].test_start),
        "n_folds": int(len(splits)),
        "folds": fold_meta,
        "train_rows": int(total_train_rows),
        "test_pred_rows": int(total_test_pred_rows),
        "oos_rows": int(oos_mask.sum()),
        "oos_prediction_coverage": float(total_test_pred_rows / max(int(oos_mask.sum()), 1)),
        "oos_classification_summary": oos_classification_summary,
        "oos_regression_summary": oos_regression_summary,
        "oos_volatility_summary": oos_volatility_summary,
        "target": target_meta,
        "returns_col": returns_col,
        "contracts": contract_meta,
        "anti_leakage": {
            "target_horizon": target_horizon,
            "total_trimmed_train_rows": int(total_trimmed_rows),
        },
    }
    return out, model, meta


def train_lightgbm_classifier(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, LGBMClassifier, dict[str, Any]]:
    """
    Train lightgbm classifier using the data and split conventions defined by the experiment
    orchestration workflow. The function keeps model fitting, metadata capture, and leakage
    controls in one reusable place.
    """
    return _train_forward_classifier(
        df,
        model_cfg,
        model_kind="lightgbm_clf",
        estimator_family="lightgbm",
        estimator_factory=lambda params: LGBMClassifier(**params),
        returns_col=returns_col,
    )


def train_logistic_regression_classifier(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, LogisticRegression, dict[str, Any]]:
    """
    Train logistic regression classifier using the data and split conventions defined by the
    experiment orchestration workflow. The function keeps model fitting, metadata capture, and
    leakage controls in one reusable place.
    """
    model_cfg = dict(model_cfg or {})
    params = dict(model_cfg.get("params", {}) or {})
    params.setdefault("max_iter", 1000)
    params.setdefault("solver", "lbfgs")
    model_cfg["params"] = params

    out, model, meta = _train_forward_classifier(
        df,
        model_cfg,
        model_kind="logistic_regression_clf",
        estimator_family="sklearn",
        estimator_factory=lambda model_params: LogisticRegression(**model_params),
        returns_col=returns_col,
    )
    return out, model, meta


def train_sarimax_forecaster(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Train SARIMAX forecaster with walk-forward or purged split logic.
    """
    out, model, meta = _train_forward_forecaster(
        df=df,
        model_cfg=model_cfg,
        model_kind="sarimax_forecaster",
        fold_predictor=train_sarimax_fold,
        returns_col=returns_col,
        required_features=False,
        runtime_estimator_family="statsmodels",
    )
    return out, model, meta


def train_garch_forecaster(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Train GARCH(1,1) volatility forecaster and attach causal return/volatility forecasts.
    """
    cfg = dict(model_cfg or {})
    target_cfg = dict(cfg.get("target", {}) or {})
    params = dict(cfg.get("params", {}) or {})
    returns_input_col = str(params.get("returns_input_col") or cfg.get("returns_input_col") or returns_col or "close_ret")
    if returns_input_col not in df.columns:
        price_col = str(target_cfg.get("price_col", "close"))
        if price_col not in df.columns:
            raise KeyError(
                f"GARCH returns_input_col '{returns_input_col}' not found and price_col '{price_col}' is missing."
            )
        work_df = df.copy()
        work_df[returns_input_col] = work_df[price_col].pct_change()
    else:
        work_df = df

    params["returns_input_col"] = returns_input_col
    cfg["params"] = params
    out, model, meta = _train_forward_forecaster(
        df=work_df,
        model_cfg=cfg,
        model_kind="garch_forecaster",
        fold_predictor=make_garch_fold_predictor(returns_input_col=returns_input_col),
        returns_col=returns_col,
        required_features=False,
        runtime_estimator_family="statsmodels",
    )
    meta["returns_input_col"] = returns_input_col
    return out, model, meta


def train_tft_forecaster(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Train a compact TFT-style transformer forecaster under the shared anti-leakage split loop.
    """
    out, model, meta = _train_forward_forecaster(
        df=df,
        model_cfg=model_cfg,
        model_kind="tft_forecaster",
        fold_predictor=make_tft_fold_predictor(),
        returns_col=returns_col,
        required_features=True,
        runtime_estimator_family="torch",
    )
    return out, model, meta


__all__ = [
    "infer_feature_columns",
    "train_lightgbm_classifier",
    "train_logistic_regression_classifier",
    "train_sarimax_forecaster",
    "train_garch_forecaster",
    "train_tft_forecaster",
]
