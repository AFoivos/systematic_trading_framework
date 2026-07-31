from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.inspection import permutation_importance

from src.evaluation.time_splits import (
    assert_no_forward_label_leakage,
    build_time_splits,
    trim_train_indices_for_horizon,
)
from src.evaluation.contracts import TargetContract, validate_feature_target_contract
from src.evaluation.fold_reporting import report_optuna_fold
from src.evaluation.model_metrics import (
    binary_classification_metrics,
    empty_classification_metrics,
    empty_multiclass_classification_metrics,
    empty_regression_metrics,
    empty_volatility_metrics,
    multiclass_baseline_metrics,
    multiclass_classification_metrics,
)
from src.models.common.overlay import resolve_garch_overlay
from src.evaluation.diagnostics import (
    aggregate_feature_importance,
    aggregate_label_distributions,
    extract_feature_importance,
    summarize_feature_family_counts,
    summarize_feature_availability,
    summarize_feature_importance_stability,
    summarize_label_distribution,
    summarize_prediction_alignment,
)
from src.models.common.runtime import (
    describe_feature_set,
    infer_feature_columns,
    resolve_runtime_for_model,
)
from src.targets import assign_quantile_labels
from src.targets.registry import build_target
from src.models.types import EstimatorFactory


class FoldProbabilityCalibrator:
    """One-vs-rest probability calibration fitted on a later temporal window."""

    def __init__(self, *, method: str, models: list[object]) -> None:
        self.method = str(method)
        self.models = list(models)

    def predict(self, raw_probability: np.ndarray) -> np.ndarray:
        raw = np.asarray(raw_probability, dtype=float)
        if raw.ndim != 2 or raw.shape[1] != len(self.models):
            raise ValueError("Calibration input shape does not match fitted class calibrators.")
        calibrated = np.zeros_like(raw, dtype=float)
        for class_idx, model in enumerate(self.models):
            values = np.clip(raw[:, class_idx], 1e-6, 1.0 - 1e-6)
            if self.method == "sigmoid":
                logits = np.log(values / (1.0 - values)).reshape(-1, 1)
                calibrated[:, class_idx] = model.predict_proba(logits)[:, 1]
            else:
                calibrated[:, class_idx] = model.predict(values)
        row_sums = calibrated.sum(axis=1, keepdims=True)
        invalid = (~np.isfinite(row_sums[:, 0])) | (row_sums[:, 0] <= 1e-12)
        if bool(invalid.any()):
            calibrated[invalid] = raw[invalid]
            row_sums = calibrated.sum(axis=1, keepdims=True)
        return calibrated / np.maximum(row_sums, 1e-12)


class FittedClassifierPipeline:
    """Serializable deployment wrapper for preprocessing, estimator, and calibration."""

    def __init__(
        self,
        *,
        estimator: object,
        scaler: StandardScaler | RobustScaler | None,
        calibrator: FoldProbabilityCalibrator | None,
        estimator_family: str,
        classes: np.ndarray | list[int] | None = None,
    ) -> None:
        self.estimator = estimator
        self.scaler = scaler
        self.calibrator = calibrator
        self.estimator_family = str(estimator_family)
        self.classes_ = np.asarray(
            classes if classes is not None else getattr(estimator, "classes_", [0, 1])
        )

    def _transform(self, features: pd.DataFrame | np.ndarray) -> pd.DataFrame | np.ndarray:
        if isinstance(features, pd.DataFrame):
            raw: pd.DataFrame | np.ndarray = features.astype(float)
        else:
            raw = np.asarray(features, dtype=float)
        if self.scaler is not None:
            values = (
                raw.to_numpy(dtype=float, copy=False)
                if isinstance(raw, pd.DataFrame)
                else np.asarray(raw, dtype=float)
            )
            raw = self.scaler.transform(values)
        if self.estimator_family == "xgboost":
            raw = (
                raw.to_numpy(dtype=np.float32, copy=False)
                if isinstance(raw, pd.DataFrame)
                else np.asarray(raw, dtype=np.float32)
            )
        return raw

    def predict_proba(self, features: pd.DataFrame | np.ndarray) -> np.ndarray:
        estimator_probability = np.asarray(
            self.estimator.predict_proba(self._transform(features)),
            dtype=float,
        )
        raw_probability = _expand_estimator_probabilities(
            self.estimator,
            estimator_probability,
            class_count=len(self.classes_),
        )
        if self.calibrator is None:
            return raw_probability
        return self.calibrator.predict(raw_probability)

    def predict(self, features: pd.DataFrame | np.ndarray) -> np.ndarray:
        probability = self.predict_proba(features)
        return self.classes_[np.argmax(probability, axis=1)]


def _expand_estimator_probabilities(
    estimator: object,
    raw_probability: np.ndarray,
    *,
    class_count: int,
) -> np.ndarray:
    raw = np.asarray(raw_probability, dtype=float)
    estimator_classes = np.asarray(getattr(estimator, "classes_", np.arange(raw.shape[1])), dtype=int)
    if raw.ndim != 2 or raw.shape[1] != len(estimator_classes):
        raise ValueError("Estimator probability output does not match estimator.classes_.")
    expanded = np.zeros((raw.shape[0], int(class_count)), dtype=float)
    for source_idx, encoded_class in enumerate(estimator_classes):
        if encoded_class < 0 or encoded_class >= class_count:
            raise ValueError("Estimator emitted an encoded class outside the declared class range.")
        expanded[:, int(encoded_class)] = raw[:, source_idx]
    row_sums = expanded.sum(axis=1, keepdims=True)
    return expanded / np.maximum(row_sums, 1e-12)


def _fit_deployment_preprocessor(
    features: pd.DataFrame,
    *,
    preprocessing_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame | np.ndarray, StandardScaler | RobustScaler | None, dict[str, Any]]:
    cfg = dict(preprocessing_cfg or {})
    scaler_kind = str(cfg.get("scaler", "none") or "none").strip().lower()
    if scaler_kind in {"", "none"}:
        return features, None, {"scaler": "none", "train_only": True}
    if scaler_kind == "standard":
        scaler: StandardScaler | RobustScaler = StandardScaler()
    elif scaler_kind == "robust":
        scaler = RobustScaler()
    else:
        raise ValueError(f"Unsupported model.preprocessing.scaler: {scaler_kind}")
    transformed = scaler.fit_transform(features.to_numpy(dtype=float, copy=False))
    return (
        transformed,
        scaler,
        {
            "scaler": scaler_kind,
            "train_only": True,
            "feature_count": int(features.shape[1]),
        },
    )


def _apply_fold_feature_preprocessing(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    *,
    preprocessing_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame | np.ndarray, pd.DataFrame | np.ndarray, dict[str, Any]]:
    cfg = dict(preprocessing_cfg or {})
    scaler_kind = str(cfg.get("scaler", "none") or "none").strip().lower()
    if scaler_kind in {"", "none"}:
        return X_train, X_test, {"scaler": "none", "train_only": True}
    if scaler_kind not in {"standard", "robust"}:
        raise ValueError(f"Unsupported model.preprocessing.scaler: {scaler_kind}")

    if scaler_kind == "standard":
        scaler = StandardScaler()
    else:
        scaler = RobustScaler()
    X_train_scaled = scaler.fit_transform(X_train.to_numpy(dtype=float, copy=False))
    X_test_values = X_test.to_numpy(dtype=float, copy=False)
    if X_test_values.shape[0] == 0:
        X_test_scaled = np.empty((0, X_train.shape[1]), dtype=float)
    else:
        X_test_scaled = scaler.transform(X_test_values)
    return (
        X_train_scaled,
        X_test_scaled,
        {
            "scaler": scaler_kind,
            "train_only": True,
            "feature_count": int(X_train.shape[1]),
        },
    )


def _resolve_calibration_cfg(model_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(model_cfg.get("calibration", {}) or {})
    method = str(cfg.get("method", "none") or "none").strip().lower()
    if method not in {"none", "sigmoid", "isotonic"}:
        raise ValueError("model.calibration.method must be one of: none, sigmoid, isotonic.")
    fraction = float(cfg.get("fraction", 0.20))
    if not 0.0 < fraction < 0.5:
        raise ValueError("model.calibration.fraction must be in (0, 0.5).")
    min_rows = int(cfg.get("min_rows", 200))
    if min_rows <= 0:
        raise ValueError("model.calibration.min_rows must be positive.")
    min_class_rows = int(cfg.get("min_class_rows", 25 if method == "isotonic" else 5))
    if min_class_rows <= 0:
        raise ValueError("model.calibration.min_class_rows must be positive.")
    return {
        "method": method,
        "fraction": fraction,
        "min_rows": min_rows,
        "min_class_rows": min_class_rows,
    }


def _split_fit_and_calibration_rows(
    train_fit: pd.DataFrame,
    *,
    full_index: pd.Index,
    target_horizon: int,
    calibration_cfg: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    method = str(calibration_cfg["method"])
    if method == "none":
        return train_fit, train_fit.iloc[0:0], {"enabled": False, "method": "none"}

    calibration_rows = max(
        int(round(len(train_fit) * float(calibration_cfg["fraction"]))),
        int(calibration_cfg["min_rows"]),
    )
    if calibration_rows >= len(train_fit):
        raise ValueError("Not enough training rows for the requested fold-local calibration window.")
    calibration = train_fit.iloc[-calibration_rows:].copy()
    calibration_start = int(full_index.get_loc(calibration.index[0]))
    fit_cutoff = calibration_start - int(target_horizon)
    train_positions = full_index.get_indexer(train_fit.index)
    fit = train_fit.iloc[train_positions < fit_cutoff].copy()
    if fit.empty:
        raise ValueError("Fold-local calibration purge removed all estimator fit rows.")
    return fit, calibration, {
        "enabled": True,
        "method": method,
        "fit_rows": int(len(fit)),
        "calibration_rows": int(len(calibration)),
        "calibration_start_position": calibration_start,
        "fit_end_position": int(full_index.get_loc(fit.index[-1])),
        "purge_bars": int(target_horizon),
    }


def _fit_sigmoid_calibrator(raw_probability: np.ndarray, labels: pd.Series) -> LogisticRegression:
    raw = np.asarray(raw_probability, dtype=float)
    clipped = np.clip(raw, 1e-6, 1.0 - 1e-6)
    logits = np.log(clipped / (1.0 - clipped)).reshape(-1, 1)
    calibrator = LogisticRegression(random_state=0, max_iter=500)
    calibrator.fit(logits, labels.to_numpy(dtype=int, copy=False))
    return calibrator


def _apply_sigmoid_calibrator(calibrator: LogisticRegression, raw_probability: np.ndarray) -> np.ndarray:
    raw = np.asarray(raw_probability, dtype=float)
    clipped = np.clip(raw, 1e-6, 1.0 - 1e-6)
    logits = np.log(clipped / (1.0 - clipped)).reshape(-1, 1)
    return calibrator.predict_proba(logits)[:, 1].astype("float32")


def _fit_probability_calibrator(
    raw_probability: np.ndarray,
    labels_encoded: pd.Series,
    *,
    method: str,
    min_class_rows: int,
) -> FoldProbabilityCalibrator:
    raw = np.asarray(raw_probability, dtype=float)
    labels = labels_encoded.to_numpy(dtype=int, copy=False)
    if raw.ndim != 2:
        raise ValueError("Calibration probabilities must be a 2D matrix.")
    models: list[object] = []
    for class_idx in range(raw.shape[1]):
        binary = (labels == class_idx).astype(int)
        positives = int(binary.sum())
        negatives = int(len(binary) - positives)
        if positives < int(min_class_rows) or negatives < int(min_class_rows):
            raise ValueError(
                "Fold-local calibration requires at least "
                f"{min_class_rows} positive and negative rows for class {class_idx}."
            )
        values = np.clip(raw[:, class_idx], 1e-6, 1.0 - 1e-6)
        if method == "sigmoid":
            logits = np.log(values / (1.0 - values)).reshape(-1, 1)
            calibrator: object = LogisticRegression(random_state=0, max_iter=500)
            calibrator.fit(logits, binary)
        elif method == "isotonic":
            if len(np.unique(values)) < 3:
                raise ValueError("Isotonic calibration requires at least three distinct probabilities per class.")
            calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            calibrator.fit(values, binary)
        else:
            raise ValueError("Probability calibrator method must be sigmoid or isotonic.")
        models.append(calibrator)
    return FoldProbabilityCalibrator(method=method, models=models)


def _barrier_fold_ambiguity(
    train_frame: pd.DataFrame,
    eval_frame: pd.DataFrame,
    *,
    target_meta: dict[str, Any],
) -> dict[str, float | int] | None:
    if target_meta.get("kind") != "first_passage_barrier_multiclass":
        return None
    ambiguous_col = str(target_meta.get("ambiguous_col", "ambiguous"))
    entry_price_col = str(target_meta.get("entry_price_col", "entry_price"))

    def summarize(frame: pd.DataFrame) -> tuple[int, int, float]:
        if ambiguous_col not in frame.columns:
            return 0, 0, 0.0
        evaluated = (
            frame[entry_price_col].notna()
            if entry_price_col in frame.columns
            else pd.Series(True, index=frame.index, dtype=bool)
        )
        count = int(frame.loc[evaluated, ambiguous_col].fillna(False).astype(bool).sum())
        rows = int(evaluated.sum())
        return count, rows, float(count / rows) if rows else 0.0

    train_count, train_rows, train_rate = summarize(train_frame)
    eval_count, eval_rows, eval_rate = summarize(eval_frame)
    return {
        "train_ambiguous_count": train_count,
        "train_evaluated_rows": train_rows,
        "train_ambiguous_rate": train_rate,
        "eval_ambiguous_count": eval_count,
        "eval_evaluated_rows": eval_rows,
        "eval_ambiguous_rate": eval_rate,
    }


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
    preprocessing_cfg = dict(model_cfg.get("preprocessing", {}) or {})
    work_df, overlay_predictor, overlay_params, overlay_meta = resolve_garch_overlay(
        df,
        model_cfg=model_cfg,
        returns_col=returns_col,
    )
    runtime_meta = resolve_runtime_for_model(
        model_cfg=model_cfg,
        model_params=model_params,
        estimator_family=estimator_family,
    )

    pred_prob_col = str(model_cfg.get("pred_prob_col") or "pred_prob")
    pred_is_oos_col = str(model_cfg.get("pred_is_oos_col") or "pred_is_oos")
    calibration_cfg = _resolve_calibration_cfg(model_cfg)
    emit_raw_probability = bool(
        model_cfg.get("pred_raw_prob_col")
        or calibration_cfg["method"] != "none"
    )
    pred_raw_prob_col = str(model_cfg.get("pred_raw_prob_col") or f"{pred_prob_col}_raw")
    target_cfg = dict(model_cfg.get("target", {}) or {})
    if str(target_cfg.get("kind", "")) == "first_passage_barrier_multiclass":
        risk_cfg = dict(model_cfg.get("risk", {}) or {})
        target_cfg.setdefault(
            "round_trip_cost",
            2.0
            * (
                float(risk_cfg.get("cost_per_turnover", 0.0) or 0.0)
                + float(risk_cfg.get("slippage_per_turnover", 0.0) or 0.0)
            ),
        )
    out, label_col, fwd_col, target_meta = build_target(df=work_df, target_cfg=target_cfg)
    class_labels = np.asarray(target_meta.get("class_labels", [0, 1]), dtype=int)
    if class_labels.ndim != 1 or len(class_labels) < 2 or len(np.unique(class_labels)) != len(class_labels):
        raise ValueError("Classifier targets must declare at least two unique class_labels.")
    class_to_encoded = {int(label): idx for idx, label in enumerate(class_labels)}
    is_multiclass = len(class_labels) > 2
    primary_class = int(target_meta.get("primary_probability_class", class_labels[-1]))
    if primary_class not in class_to_encoded:
        raise ValueError("target primary_probability_class must be present in class_labels.")
    primary_class_idx = int(class_to_encoded[primary_class])
    class_names = {
        int(label): str(dict(target_meta.get("class_names", {}) or {}).get(str(int(label)), int(label)))
        for label in class_labels
    }
    class_probability_cols = {
        int(label): f"{pred_prob_col}_{class_names[int(label)]}"
        for label in class_labels
    }
    class_raw_probability_cols = {
        int(label): f"{pred_raw_prob_col}_{class_names[int(label)]}"
        for label in class_labels
    }
    probability_calibrated_col = str(
        model_cfg.get("probability_calibrated_col") or "pred_probability_calibrated"
    )

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

    target_output_cols = set(str(col) for col in list(target_meta.get("output_cols", []) or []))
    feature_cols = infer_feature_columns(
        out,
        explicit_cols=model_cfg.get("feature_cols"),
        feature_selectors=model_cfg.get("feature_selectors"),
        exclude={label_col, fwd_col, pred_prob_col, pred_raw_prob_col, *target_output_cols},
    )
    feature_cols = [col for col in feature_cols if col not in target_output_cols]
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
    pred_raw_prob = (
        pd.Series(np.nan, index=out.index, name=pred_raw_prob_col, dtype="float32")
        if emit_raw_probability
        else None
    )
    class_probabilities = (
        {
            int(label): pd.Series(
                np.nan,
                index=out.index,
                name=class_probability_cols[int(label)],
                dtype="float32",
            )
            for label in class_labels
        }
        if is_multiclass
        else {}
    )
    class_raw_probabilities = (
        {
            int(label): pd.Series(
                np.nan,
                index=out.index,
                name=class_raw_probability_cols[int(label)],
                dtype="float32",
            )
            for label in class_labels
        }
        if is_multiclass and emit_raw_probability
        else {}
    )
    probability_calibrated = pd.Series(
        False,
        index=out.index,
        name=probability_calibrated_col,
        dtype=bool,
    )
    oos_mask = pd.Series(False, index=out.index, name=pred_is_oos_col)
    oos_assignment_count = pd.Series(0, index=out.index, dtype="int32")
    extra_prediction_cols: dict[str, pd.Series] = {}

    fold_meta: list[dict[str, Any]] = []
    model: object | None = None
    total_train_rows = 0
    total_test_pred_rows = 0
    total_trimmed_rows = 0
    target_horizon = int(target_meta["horizon"])
    all_eval_labels: list[np.ndarray] = []
    all_eval_probs: list[np.ndarray] = []
    all_eval_raw_probs: list[np.ndarray] = []
    fold_feature_importances: list[list[dict[str, Any]]] = []
    fold_permutation_importances: list[list[dict[str, Any]]] = []
    train_label_distributions: list[dict[str, Any]] = []
    eval_label_distributions: list[dict[str, Any]] = []
    total_train_rows_dropped_missing = 0
    total_train_rows_not_labeled = 0
    total_train_rows_without_fit = 0
    total_test_rows_missing_features = 0
    total_test_rows_not_candidates = 0
    total_test_rows_without_prediction = 0
    folds_with_zero_predictions = 0
    preprocessing_meta: dict[str, Any] = {"scaler": "none", "train_only": True}
    prediction_candidate_col = (
        str(target_meta.get("candidate_col"))
        if target_meta.get("candidate_col") is not None
        else None
    )

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
        fold_ambiguity = _barrier_fold_ambiguity(
            train_df,
            test_df,
            target_meta=target_meta,
        )
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

        train_features = train_df[feature_cols]
        train_feature_complete_mask = train_features.notna().all(axis=1)
        train_labeled_mask = train_df[label_col].notna()
        train_fit = train_df.loc[train_feature_complete_mask & train_labeled_mask]
        if train_fit.empty:
            raise ValueError(f"Fold {split.fold} has no train rows after dropping NaNs in features/labels.")
        train_availability = summarize_feature_availability(train_df, feature_cols)
        train_rows_dropped_missing = int((~train_feature_complete_mask).sum())
        train_rows_not_labeled = int((train_feature_complete_mask & ~train_labeled_mask).sum())
        train_rows_without_fit = int(len(train_df) - len(train_fit))
        total_train_rows_dropped_missing += train_rows_dropped_missing
        total_train_rows_not_labeled += train_rows_not_labeled
        total_train_rows_without_fit += train_rows_without_fit

        estimator_fit, calibration_fit, fold_calibration_meta = _split_fit_and_calibration_rows(
            train_fit,
            full_index=out.index,
            target_horizon=target_horizon,
            calibration_cfg=calibration_cfg,
        )
        X_train = estimator_fit[feature_cols]
        y_train = estimator_fit[label_col].astype(int)
        if int(y_train.nunique()) < 2:
            raise ValueError(f"Fold {split.fold} has a single target class after preprocessing.")
        unknown_train_labels = sorted(set(y_train.unique()) - set(class_to_encoded))
        if unknown_train_labels:
            raise ValueError(f"Fold {split.fold} contains undeclared target classes: {unknown_train_labels}")
        y_train_encoded = y_train.map(class_to_encoded).astype(int)
        train_label_distribution = summarize_label_distribution(y_train)
        train_label_distributions.append(train_label_distribution)

        model = estimator_factory(model_params)
        test_features = test_df[feature_cols]
        feature_complete_mask = test_features.notna().all(axis=1)
        candidate_mask = pd.Series(True, index=test_features.index, dtype=bool)
        if prediction_candidate_col is not None:
            if prediction_candidate_col not in test_df.columns:
                raise KeyError(
                    f"Target candidate_col '{prediction_candidate_col}' not found in test fold DataFrame."
                )
            candidate_mask = test_df[prediction_candidate_col].fillna(0).astype(bool)
            candidate_mask = candidate_mask.reindex(test_features.index).fillna(False)
        valid_mask = feature_complete_mask & candidate_mask
        test_rows_missing_features = int((~feature_complete_mask).sum())
        test_rows_not_candidates = int((feature_complete_mask & ~candidate_mask).sum())
        test_rows_without_prediction = int((~valid_mask).sum())
        pred_rows = int(valid_mask.sum())
        if pred_rows == 0:
            folds_with_zero_predictions += 1
        total_test_rows_missing_features += test_rows_missing_features
        total_test_rows_not_candidates += test_rows_not_candidates
        total_test_rows_without_prediction += test_rows_without_prediction
        pred_index = test_features.loc[valid_mask].index
        X_test = test_features.loc[valid_mask]

        X_train_input, X_test_input, fold_preprocessing_meta = _apply_fold_feature_preprocessing(
            X_train,
            X_test,
            preprocessing_cfg=preprocessing_cfg,
        )
        preprocessing_meta = dict(fold_preprocessing_meta)
        y_train_input: pd.Series | np.ndarray = y_train_encoded
        if estimator_family == "xgboost":
            if isinstance(X_train_input, pd.DataFrame):
                X_train_input = X_train_input.to_numpy(dtype=np.float32, copy=False)
            else:
                X_train_input = np.asarray(X_train_input, dtype=np.float32)
            y_train_input = y_train_encoded.to_numpy(dtype=np.int32, copy=False)
        fit_kwargs: dict[str, Any] = {}
        if model_cfg.get("_class_weight") is not None:
            fit_kwargs["sample_weight"] = compute_sample_weight(
                class_weight=model_cfg["_class_weight"],
                y=np.asarray(y_train_input, dtype=int),
            )
        model.fit(X_train_input, y_train_input, **fit_kwargs)
        calibrator: FoldProbabilityCalibrator | None = None
        if bool(fold_calibration_meta.get("enabled", False)):
            calibration_labels = calibration_fit[label_col].astype(int)
            calibration_labels_encoded = calibration_labels.map(class_to_encoded)
            if calibration_labels_encoded.isna().any():
                raise ValueError(f"Fold {split.fold} calibration window contains undeclared classes.")
            calibration_labels_encoded = calibration_labels_encoded.astype(int)
            calibration_features = calibration_fit[feature_cols]
            _, calibration_input, _ = _apply_fold_feature_preprocessing(
                estimator_fit[feature_cols],
                calibration_features,
                preprocessing_cfg=preprocessing_cfg,
            )
            if estimator_family == "xgboost":
                calibration_input = np.asarray(calibration_input, dtype=np.float32)
            calibration_raw = _expand_estimator_probabilities(
                model,
                model.predict_proba(calibration_input),
                class_count=len(class_labels),
            )
            calibrator = _fit_probability_calibrator(
                calibration_raw,
                calibration_labels_encoded,
                method=str(calibration_cfg["method"]),
                min_class_rows=int(calibration_cfg["min_class_rows"]),
            )
            calibration_calibrated = calibrator.predict(calibration_raw)
            fold_calibration_meta["calibration_class_rates"] = {
                str(int(label)): float(np.mean(calibration_labels.to_numpy(dtype=int) == label))
                for label in class_labels
            }
            fold_calibration_meta["raw_probability_mean_by_class"] = {
                str(int(label)): float(np.mean(calibration_raw[:, idx]))
                for idx, label in enumerate(class_labels)
            }
            fold_calibration_meta["calibrated_probability_mean_by_class"] = {
                str(int(label)): float(np.mean(calibration_calibrated[:, idx]))
                for idx, label in enumerate(class_labels)
            }
        fold_feature_importance = extract_feature_importance(model, feature_cols)
        fold_feature_importances.append(fold_feature_importance)

        fold_eval_metrics: dict[str, object] = (
            empty_multiclass_classification_metrics() if is_multiclass else empty_classification_metrics()
        )
        fold_raw_eval_metrics: dict[str, object] = (
            empty_multiclass_classification_metrics() if is_multiclass else empty_classification_metrics()
        )
        fold_baselines: dict[str, dict[str, object]] = {}
        fold_permutation_importance: list[dict[str, Any]] = []
        eval_label_distribution = summarize_label_distribution(pd.Series(dtype=float))

        if pred_rows > 0:
            test_input: pd.DataFrame | np.ndarray = X_test_input
            if estimator_family == "xgboost":
                if isinstance(test_input, pd.DataFrame):
                    test_input = test_input.to_numpy(dtype=np.float32, copy=False)
                else:
                    test_input = np.asarray(test_input, dtype=np.float32)
            raw_probability_matrix = _expand_estimator_probabilities(
                model,
                model.predict_proba(test_input),
                class_count=len(class_labels),
            )
            probability_matrix = (
                calibrator.predict(raw_probability_matrix)
                if calibrator is not None
                else raw_probability_matrix
            )
            raw_pred_series = pd.Series(
                raw_probability_matrix[:, primary_class_idx],
                index=pred_index,
                dtype="float32",
            )
            if pred_raw_prob is not None:
                pred_raw_prob.loc[pred_index] = raw_pred_series
            pred_series = pd.Series(
                probability_matrix[:, primary_class_idx],
                index=pred_index,
                dtype="float32",
            )
            pred_prob.loc[pred_index] = pred_series
            if is_multiclass:
                for class_idx, class_label in enumerate(class_labels):
                    class_probabilities[int(class_label)].loc[pred_index] = probability_matrix[
                        :, class_idx
                    ].astype("float32")
                    if emit_raw_probability:
                        class_raw_probabilities[int(class_label)].loc[pred_index] = raw_probability_matrix[
                            :, class_idx
                        ].astype("float32")
            if calibrator is not None:
                probability_calibrated.loc[pred_index] = True

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
                if is_multiclass:
                    p_eval_frame = pd.DataFrame(
                        probability_matrix[labeled_mask.to_numpy(dtype=bool)],
                        index=y_eval.index,
                        columns=class_labels,
                    )
                    raw_eval_frame = pd.DataFrame(
                        raw_probability_matrix[labeled_mask.to_numpy(dtype=bool)],
                        index=y_eval.index,
                        columns=class_labels,
                    )
                    fold_eval_metrics = multiclass_classification_metrics(
                        y_eval,
                        p_eval_frame,
                        class_labels=class_labels,
                    )
                    fold_raw_eval_metrics = multiclass_classification_metrics(
                        y_eval,
                        raw_eval_frame,
                        class_labels=class_labels,
                    )
                    last_returns = (
                        pd.to_numeric(out["close"], errors="coerce").pct_change()
                        if "close" in out.columns
                        else None
                    )
                    fold_baselines = multiclass_baseline_metrics(
                        y_train,
                        y_eval,
                        class_labels=class_labels,
                        last_returns=last_returns,
                        random_seed=int(dict(model_cfg.get("diagnostics", {}) or {}).get("baselines", {}).get("random_seed", 7)) + int(split.fold),
                    )
                    all_eval_probs.append(p_eval_frame.to_numpy(dtype=float, copy=False))
                    all_eval_raw_probs.append(raw_eval_frame.to_numpy(dtype=float, copy=False))
                else:
                    p_eval = pred_series.loc[labeled_mask]
                    raw_p_eval = raw_pred_series.loc[labeled_mask]
                    fold_eval_metrics = binary_classification_metrics(y_eval, p_eval)
                    fold_raw_eval_metrics = binary_classification_metrics(y_eval, raw_p_eval)
                    all_eval_probs.append(p_eval.to_numpy(dtype=float, copy=False))
                    all_eval_raw_probs.append(raw_p_eval.to_numpy(dtype=float, copy=False))
                eval_label_distribution = summarize_label_distribution(y_eval)
                all_eval_labels.append(y_eval.to_numpy(dtype=int, copy=False))
                permutation_cfg = dict(
                    dict(dict(model_cfg.get("diagnostics", {}) or {}).get("model", {}) or {}).get(
                        "permutation_importance", {}
                    )
                    or {}
                )
                if bool(permutation_cfg.get("enabled", False)):
                    eval_encoded = y_eval.map(class_to_encoded).astype(int).to_numpy(dtype=int)
                    labeled_positions = np.flatnonzero(labeled_mask.to_numpy(dtype=bool))
                    max_rows = int(permutation_cfg.get("max_rows", 2000))
                    labeled_positions = labeled_positions[-max_rows:]
                    if isinstance(test_input, pd.DataFrame):
                        permutation_features = test_input.iloc[labeled_positions]
                    else:
                        permutation_features = np.asarray(test_input)[labeled_positions]
                    permutation_labels = eval_encoded[-len(labeled_positions) :]
                    permutation_result = permutation_importance(
                        model,
                        permutation_features,
                        permutation_labels,
                        scoring="neg_log_loss",
                        n_repeats=int(permutation_cfg.get("n_repeats", 3)),
                        random_state=int(permutation_cfg.get("random_state", 7)) + int(split.fold),
                        n_jobs=1,
                    )
                    fold_permutation_importance = sorted(
                        [
                            {
                                "feature": str(feature),
                                "importance": float(permutation_result.importances_mean[idx]),
                                "importance_std": float(permutation_result.importances_std[idx]),
                            }
                            for idx, feature in enumerate(feature_cols)
                        ],
                        key=lambda row: abs(float(row["importance"])),
                        reverse=True,
                    )
        eval_label_distributions.append(eval_label_distribution)
        fold_permutation_importances.append(fold_permutation_importance)

        overlay_fold_meta: dict[str, Any] = {}
        if overlay_predictor is not None:
            _, overlay_extra_cols, _, overlay_fold_meta = overlay_predictor(
                out,
                np.asarray(safe_train_idx, dtype=int),
                np.asarray(split.test_idx, dtype=int),
                [],
                fwd_col,
                overlay_params,
                runtime_meta,
            )
            for col_name, values in dict(overlay_extra_cols or {}).items():
                if col_name not in extra_prediction_cols:
                    extra_prediction_cols[col_name] = pd.Series(
                        np.nan,
                        index=out.index,
                        name=col_name,
                        dtype="float32",
                    )
                series = pd.Series(values, copy=False).astype(float)
                series = series.loc[series.index.intersection(test_df.index)]
                extra_prediction_cols[col_name].loc[series.index] = series.astype("float32")

        fold_test_idx = out.index[split.test_idx]
        oos_mask.loc[fold_test_idx] = True
        oos_assignment_count.loc[fold_test_idx] += 1

        total_train_rows += int(len(estimator_fit))
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
                "train_rows_raw": int(len(train_df)),
                "train_rows": int(len(train_fit)),
                "train_rows_dropped_missing": train_rows_dropped_missing,
                "train_rows_not_labeled": train_rows_not_labeled,
                "train_rows_without_fit": train_rows_without_fit,
                "train_feature_availability": train_availability,
                "test_rows": int(len(split.test_idx)),
                "test_pred_rows": pred_rows,
                "test_feature_availability": summarize_feature_availability(test_df, feature_cols),
                "test_rows_missing_features": test_rows_missing_features,
                "test_rows_not_candidates": test_rows_not_candidates,
                "test_rows_without_prediction": test_rows_without_prediction,
                "quantile_low_value": quantile_low_value,
                "quantile_high_value": quantile_high_value,
                "train_label_distribution": train_label_distribution,
                "eval_label_distribution": eval_label_distribution,
                "preprocessing": fold_preprocessing_meta,
                "calibration": fold_calibration_meta,
                "feature_importance": fold_feature_importance,
                "classification_metrics": fold_eval_metrics,
                "raw_classification_metrics": fold_raw_eval_metrics,
                "baseline_metrics": fold_baselines,
                "permutation_importance": fold_permutation_importance,
                "regression_metrics": empty_regression_metrics(),
                "volatility_metrics": empty_volatility_metrics(),
            }
        )
        if fold_ambiguity is not None:
            fold_meta[-1]["ambiguity"] = fold_ambiguity
        if overlay_fold_meta:
            fold_meta[-1]["overlay"] = overlay_fold_meta
        report_optuna_fold(model_kind, int(split.fold), dict(fold_meta[-1]))

    final_refit_meta: dict[str, Any] = {"enabled": False}
    if bool(model_cfg.get("final_refit", True)):
        cutoff_source = out[fwd_col] if target_meta.get("quantiles") is not None else out[label_col]
        labeled_positions = np.flatnonzero(cutoff_source.notna().to_numpy(dtype=bool))
        if len(labeled_positions) == 0:
            raise ValueError("Final classifier refit has no fully observed label rows.")
        final_cutoff = int(labeled_positions[-1])
        final_train_df = out.iloc[: final_cutoff + 1].copy()
        final_quantile_low: float | None = None
        final_quantile_high: float | None = None
        if target_meta.get("quantiles") is not None:
            q_low, q_high = target_meta["quantiles"]
            final_fwd = final_train_df[fwd_col].dropna().astype(float)
            final_quantile_low = float(final_fwd.quantile(float(q_low)))
            final_quantile_high = float(final_fwd.quantile(float(q_high)))
            final_train_df[label_col] = assign_quantile_labels(
                final_train_df[fwd_col],
                low_value=final_quantile_low,
                high_value=final_quantile_high,
            )

        final_complete = final_train_df[feature_cols].notna().all(axis=1)
        final_labeled = final_train_df[label_col].notna()
        final_train_fit = final_train_df.loc[final_complete & final_labeled]
        if final_train_fit.empty:
            raise ValueError("Final classifier refit has no complete labeled rows.")
        final_estimator_fit, final_calibration_fit, final_calibration_meta = (
            _split_fit_and_calibration_rows(
                final_train_fit,
                full_index=out.index,
                target_horizon=target_horizon,
                calibration_cfg=calibration_cfg,
            )
        )
        final_labels = final_estimator_fit[label_col].astype(int)
        if int(final_labels.nunique()) < 2:
            raise ValueError("Final classifier refit has a single target class.")
        final_labels_encoded = final_labels.map(class_to_encoded)
        if final_labels_encoded.isna().any():
            raise ValueError("Final classifier refit contains undeclared target classes.")
        final_labels_encoded = final_labels_encoded.astype(int)
        final_train_input, final_scaler, final_preprocessing_meta = (
            _fit_deployment_preprocessor(
                final_estimator_fit[feature_cols],
                preprocessing_cfg=preprocessing_cfg,
            )
        )
        final_label_input: pd.Series | np.ndarray = final_labels_encoded
        if estimator_family == "xgboost":
            final_train_input = np.asarray(final_train_input, dtype=np.float32)
            final_label_input = final_labels_encoded.to_numpy(dtype=np.int32, copy=False)
        final_estimator = estimator_factory(model_params)
        final_fit_kwargs: dict[str, Any] = {}
        if model_cfg.get("_class_weight") is not None:
            final_fit_kwargs["sample_weight"] = compute_sample_weight(
                class_weight=model_cfg["_class_weight"],
                y=np.asarray(final_label_input, dtype=int),
            )
        final_estimator.fit(final_train_input, final_label_input, **final_fit_kwargs)

        final_calibrator: FoldProbabilityCalibrator | None = None
        if bool(final_calibration_meta.get("enabled", False)):
            calibration_labels = final_calibration_fit[label_col].astype(int)
            calibration_labels_encoded = calibration_labels.map(class_to_encoded)
            if calibration_labels_encoded.isna().any():
                raise ValueError("Final classifier calibration window contains undeclared classes.")
            calibration_labels_encoded = calibration_labels_encoded.astype(int)
            calibration_values: pd.DataFrame | np.ndarray = final_calibration_fit[feature_cols]
            if final_scaler is not None:
                calibration_values = final_scaler.transform(
                    final_calibration_fit[feature_cols].to_numpy(dtype=float, copy=False)
                )
            if estimator_family == "xgboost":
                calibration_values = (
                    calibration_values.to_numpy(dtype=np.float32, copy=False)
                    if isinstance(calibration_values, pd.DataFrame)
                    else np.asarray(calibration_values, dtype=np.float32)
                )
            calibration_raw = _expand_estimator_probabilities(
                final_estimator,
                final_estimator.predict_proba(calibration_values),
                class_count=len(class_labels),
            )
            final_calibrator = _fit_probability_calibrator(
                calibration_raw,
                calibration_labels_encoded,
                method=str(calibration_cfg["method"]),
                min_class_rows=int(calibration_cfg["min_class_rows"]),
            )

        model = FittedClassifierPipeline(
            estimator=final_estimator,
            scaler=final_scaler,
            calibrator=final_calibrator,
            estimator_family=estimator_family,
            classes=class_labels,
        )
        preprocessing_meta = dict(final_preprocessing_meta)
        final_refit_meta = {
            "enabled": True,
            "train_start_position": 0,
            "train_end_position": int(final_cutoff),
            "train_start_timestamp": out.index[0],
            "train_end_timestamp": out.index[final_cutoff],
            "train_rows_raw": int(final_cutoff + 1),
            "complete_labeled_rows": int(len(final_train_fit)),
            "estimator_fit_rows": int(len(final_estimator_fit)),
            "calibration_rows": int(len(final_calibration_fit)),
            "target_horizon": int(target_horizon),
            "quantile_low_value": final_quantile_low,
            "quantile_high_value": final_quantile_high,
            "preprocessing": dict(final_preprocessing_meta),
            "calibration": dict(final_calibration_meta),
        }

    if model is None:
        raise ValueError("Model training failed: no valid folds were trained.")

    if (oos_assignment_count > 1).any():
        raise ValueError("Overlapping test windows detected. Use non-overlapping split configuration.")

    oos_classification_summary: dict[str, object] = (
        empty_multiclass_classification_metrics() if is_multiclass else empty_classification_metrics()
    )
    oos_raw_classification_summary: dict[str, object] = (
        empty_multiclass_classification_metrics() if is_multiclass else empty_classification_metrics()
    )
    if all_eval_labels and all_eval_probs:
        y_all = pd.Series(np.concatenate(all_eval_labels), dtype=int)
        if is_multiclass:
            p_all = pd.DataFrame(np.concatenate(all_eval_probs), columns=class_labels)
            raw_p_all = pd.DataFrame(np.concatenate(all_eval_raw_probs), columns=class_labels)
            oos_classification_summary = multiclass_classification_metrics(
                y_all,
                p_all,
                class_labels=class_labels,
            )
            oos_raw_classification_summary = multiclass_classification_metrics(
                y_all,
                raw_p_all,
                class_labels=class_labels,
            )
        else:
            p_all = pd.Series(np.concatenate(all_eval_probs), dtype=float)
            raw_p_all = pd.Series(np.concatenate(all_eval_raw_probs), dtype=float)
            oos_classification_summary = binary_classification_metrics(y_all, p_all)
            oos_raw_classification_summary = binary_classification_metrics(y_all, raw_p_all)

    out[pred_prob_col] = pred_prob
    if pred_raw_prob is not None:
        out[pred_raw_prob_col] = pred_raw_prob
    for class_label, series in class_probabilities.items():
        out[class_probability_cols[int(class_label)]] = series
    for class_label, series in class_raw_probabilities.items():
        out[class_raw_probability_cols[int(class_label)]] = series
    out[probability_calibrated_col] = probability_calibrated
    out[pred_is_oos_col] = oos_mask
    for col_name, series in sorted(extra_prediction_cols.items(), key=lambda kv: str(kv[0])):
        out[col_name] = series

    label_distribution = {
        "train": aggregate_label_distributions(train_label_distributions),
        "oos_evaluation": aggregate_label_distributions(eval_label_distributions),
    }
    prediction_diagnostics = summarize_prediction_alignment(
        index=out.index,
        oos_mask=oos_mask,
        prediction=pred_prob,
        probability=pred_prob,
        target=out[label_col],
        pred_vol=extra_prediction_cols.get("pred_vol"),
    )

    meta = {
        "model_kind": model_kind,
        "task_type": "classification",
        "runtime": runtime_meta,
        "feature_cols": feature_cols,
        "feature_selection": describe_feature_set(
            feature_cols,
            feature_selectors=model_cfg.get("feature_selectors"),
        ),
        "pred_prob_col": pred_prob_col,
        "pred_raw_prob_col": pred_raw_prob_col if pred_raw_prob is not None else None,
        "class_labels": [int(value) for value in class_labels],
        "class_probability_cols": {
            str(int(label)): column for label, column in class_probability_cols.items()
        } if is_multiclass else {},
        "class_raw_probability_cols": {
            str(int(label)): column for label, column in class_raw_probability_cols.items()
        } if is_multiclass and emit_raw_probability else {},
        "probability_calibrated_col": probability_calibrated_col,
        "pred_is_oos_col": pred_is_oos_col,
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
        "oos_raw_classification_summary": oos_raw_classification_summary,
        "oos_regression_summary": empty_regression_metrics(),
        "oos_volatility_summary": empty_volatility_metrics(),
        "feature_importance": aggregate_feature_importance(fold_feature_importances),
        "feature_importance_stability": summarize_feature_importance_stability(fold_feature_importances),
        "permutation_importance": aggregate_feature_importance(fold_permutation_importances),
        "feature_family_counts": summarize_feature_family_counts(feature_cols),
        "label_distribution": label_distribution,
        "prediction_diagnostics": prediction_diagnostics,
        "missing_value_diagnostics": {
            "train_rows_dropped_missing": int(total_train_rows_dropped_missing),
            "train_rows_not_labeled": int(total_train_rows_not_labeled),
            "train_rows_without_fit": int(total_train_rows_without_fit),
            "test_rows_missing_features": int(total_test_rows_missing_features),
            "test_rows_not_candidates": int(total_test_rows_not_candidates),
            "test_rows_without_prediction": int(total_test_rows_without_prediction),
            "folds_with_zero_predictions": int(folds_with_zero_predictions),
        },
        "preprocessing": preprocessing_meta,
        "calibration": calibration_cfg,
        "target": target_meta,
        "returns_col": returns_col,
        "overlay": overlay_meta,
        "contracts": contract_meta,
        "anti_leakage": {
            "target_horizon": target_horizon,
            "total_trimmed_train_rows": int(total_trimmed_rows),
        },
        "final_refit": final_refit_meta,
    }
    return out, model, meta




__all__ = ["_apply_fold_feature_preprocessing", "train_forward_classifier"]
