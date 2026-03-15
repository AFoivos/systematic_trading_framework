from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.linear_model import LogisticRegression

from src.evaluation.time_splits import (
    assert_no_forward_label_leakage,
    build_time_splits,
    trim_train_indices_for_horizon,
)
from src.experiments.contracts import TargetContract, validate_feature_target_contract
from src.experiments.modeling.metrics import (
    binary_classification_metrics,
    empty_classification_metrics,
    empty_regression_metrics,
    empty_volatility_metrics,
)
from src.experiments.modeling.runtime import infer_feature_columns, resolve_runtime_for_model
from src.experiments.modeling.targets import assign_quantile_labels, build_forward_return_target
from src.experiments.modeling.types import EstimatorFactory


def train_forward_classifier(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    *,
    model_kind: str,
    estimator_family: str,
    estimator_factory: EstimatorFactory,
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Train a classifier under the shared anti-leakage split discipline.
    """
    model_cfg = dict(model_cfg or {})
    model_params = dict(model_cfg.get("params", {}) or {})
    runtime_meta = resolve_runtime_for_model(
        model_cfg=model_cfg,
        model_params=model_params,
        estimator_family=estimator_family,
    )

    pred_prob_col = str(model_cfg.get("pred_prob_col") or "pred_prob")
    target_cfg = model_cfg.get("target", {}) or {}
    target_kind = target_cfg.get("kind", "forward_return")
    if target_kind != "forward_return":
        raise ValueError(f"Unsupported target.kind: {target_kind}")

    out, label_col, fwd_col, target_meta = build_forward_return_target(df=df, target_cfg=target_cfg)

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
            train_df[label_col] = assign_quantile_labels(
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
        fold_eval_metrics = empty_classification_metrics()

        if pred_rows > 0:
            proba = model.predict_proba(test_features.loc[valid_mask])[:, 1].astype("float32")
            pred_series = pd.Series(proba, index=pred_index, dtype="float32")
            pred_prob.loc[pred_index] = pred_series

            if target_meta.get("quantiles") is not None:
                test_labels = assign_quantile_labels(
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
                fold_eval_metrics = binary_classification_metrics(y_eval, p_eval)
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
                "regression_metrics": empty_regression_metrics(),
                "volatility_metrics": empty_volatility_metrics(),
            }
        )

    if model is None:
        raise ValueError("Model training failed: no valid folds were trained.")

    if (oos_assignment_count > 1).any():
        raise ValueError("Overlapping test windows detected. Use non-overlapping split configuration.")

    oos_classification_summary = empty_classification_metrics()
    if all_eval_labels and all_eval_probs:
        y_all = pd.Series(np.concatenate(all_eval_labels), dtype=int)
        p_all = pd.Series(np.concatenate(all_eval_probs), dtype=float)
        oos_classification_summary = binary_classification_metrics(y_all, p_all)

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
        "oos_regression_summary": empty_regression_metrics(),
        "oos_volatility_summary": empty_volatility_metrics(),
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
    return train_forward_classifier(
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
    cfg = dict(model_cfg or {})
    params = dict(cfg.get("params", {}) or {})
    params.setdefault("max_iter", 1000)
    params.setdefault("solver", "lbfgs")
    cfg["params"] = params

    out, model, meta = train_forward_classifier(
        df,
        cfg,
        model_kind="logistic_regression_clf",
        estimator_family="sklearn",
        estimator_factory=lambda model_params: LogisticRegression(**model_params),
        returns_col=returns_col,
    )
    return out, model, meta


__all__ = [
    "train_forward_classifier",
    "train_lightgbm_classifier",
    "train_logistic_regression_classifier",
]
