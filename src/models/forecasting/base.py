from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.evaluation.time_splits import (
    assert_no_forward_label_leakage,
    build_time_splits,
    trim_train_indices_for_horizon,
)
from src.evaluation.contracts import TargetContract, validate_feature_target_contract
from src.evaluation.fold_reporting import report_optuna_fold
from src.evaluation.diagnostics import (
    aggregate_feature_importance,
    extract_feature_importance,
    summarize_feature_availability,
    summarize_feature_importance_stability,
    summarize_label_distribution,
    summarize_numeric_distribution,
    summarize_prediction_alignment,
)
from src.evaluation.model_metrics import (
    binary_classification_metrics,
    empty_classification_metrics,
    empty_regression_metrics,
    empty_volatility_metrics,
    forecast_to_probability,
    regression_metrics,
    volatility_metrics,
)
from src.models.common.overlay import resolve_garch_overlay
from src.models.common.runtime import describe_feature_set, infer_feature_columns, resolve_runtime_for_model
from src.targets.registry import build_target
from src.models.types import ForecasterFoldPredictor
from src.models.forecasting.garch import make_garch_fold_predictor
from src.models.forecasting.foundation import (
    make_chronos2_fold_predictor,
    make_chronos_bolt_fold_predictor,
    make_timesfm_fold_predictor,
)
from src.models.forecasting.lightgbm import make_lightgbm_regressor_fold_predictor
from src.models.forecasting.lstm import make_lstm_fold_predictor
from src.models.forecasting.patchtst import make_patchtst_fold_predictor
from src.models.forecasting.sarimax import train_sarimax_fold
from src.models.forecasting.tft import make_tft_fold_predictor


def _foundation_model_cfg(model_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(model_cfg or {})
    cfg.setdefault("use_features", False)
    params = dict(cfg.get("params", {}) or {})
    params["_target_cfg"] = dict(cfg.get("target", {}) or {})
    cfg["params"] = params
    return cfg


def prepare_forecaster_inputs(
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
    dict[str, Any],
]:
    """
    Apply the registered ``prepare_forecaster_inputs`` model transformation.
    
    This model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        model:
          kind: prepare_forecaster_inputs
          params:
            model_params: <required>
            pred_ret_col: <required>
            pred_prob_col: <required>
            required_features: <required>
            runtime_estimator_family: <required>
            feature_cols: <configured>
            feature_selectors: <configured>
            horizon: <configured>
            kind: <configured>
            method: <configured>
            minimum_expected_features: <configured>
            oriented_r_col: <configured>
            output_cols: <configured>
            r_col: <configured>
            regression_target_col: <configured>
            split: <configured>
            target: <configured>
            target_col: <configured>
            use_features: <configured>
          outputs:
            - configured by output_cols
    
    Required input columns
    ----------------------
    pred_ret_col:
        Input dataframe column configured by ``pred_ret_col``.
    pred_prob_col:
        Input dataframe column configured by ``pred_prob_col``.
    feature_cols:
        Configured dataframe columns used by this model. Default: ``<configured>``.
    oriented_r_col:
        Input dataframe column configured by ``oriented_r_col``. Default: ``<configured>``.
    r_col:
        Input dataframe column configured by ``r_col``. Default: ``<configured>``.
    regression_target_col:
        Input dataframe column configured by ``regression_target_col``. Default: ``<configured>``.
    target_col:
        Input dataframe column configured by ``target_col``. Default: ``<configured>``.
    
    Parameters
    ----------
    model_params:
        Configuration parameter accepted by this model.
    pred_ret_col:
        Input dataframe column configured by ``pred_ret_col``.
    pred_prob_col:
        Input dataframe column configured by ``pred_prob_col``.
    required_features:
        Configuration parameter accepted by this model.
    runtime_estimator_family:
        Configuration parameter accepted by this model.
    feature_cols:
        Configured dataframe columns used by this model. Default: ``<configured>``.
    feature_selectors:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    horizon:
        Trailing lookback or forecast horizon controlling this model. Default: ``<configured>``.
    kind:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    method:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    minimum_expected_features:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    oriented_r_col:
        Input dataframe column configured by ``oriented_r_col``. Default: ``<configured>``.
    output_cols:
        Configured dataframe columns used by this model. Default: ``<configured>``.
    r_col:
        Input dataframe column configured by ``r_col``. Default: ``<configured>``.
    regression_target_col:
        Input dataframe column configured by ``regression_target_col``. Default: ``<configured>``.
    split:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    target:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    target_col:
        Input dataframe column configured by ``target_col``. Default: ``<configured>``.
    use_features:
        Boolean switch controlling optional model behavior. Default: ``<configured>``.
    """
    runtime_meta = resolve_runtime_for_model(
        model_cfg=model_cfg,
        model_params=model_params,
        estimator_family=runtime_estimator_family,
    )
    target_cfg = dict(model_cfg.get("target", {}) or {})
    target_kind = target_cfg.get("kind", "forward_return")
    if target_kind not in {"forward_return", "future_return_regression", "triple_barrier"}:
        raise ValueError(f"Unsupported target.kind: {target_kind}")
    out, label_col, fwd_col, target_meta = build_target(df=df, target_cfg=target_cfg)
    if target_kind == "triple_barrier":
        event_col = fwd_col
        regression_target_col = str(
            target_cfg.get("target_col")
            or target_cfg.get("regression_target_col")
            or target_meta.get("oriented_r_col")
            or target_meta.get("r_col")
            or event_col
        )
        if regression_target_col not in out.columns:
            raise KeyError(
                f"Configured triple_barrier regression target_col '{regression_target_col}' was not emitted."
            )
        fwd_col = regression_target_col
        target_meta = dict(target_meta)
        target_meta["regression_target_col"] = regression_target_col
    split_cfg = dict(model_cfg.get("split", {}) or {})
    split_method = split_cfg.get("method", "time")
    if split_method not in {"time", "walk_forward", "purged"}:
        raise ValueError(f"Unsupported split.method: {split_method}")

    target_output_cols = set(str(col) for col in list(target_meta.get("output_cols", []) or []))
    feature_cols = infer_feature_columns(
        out,
        explicit_cols=model_cfg.get("feature_cols"),
        feature_selectors=model_cfg.get("feature_selectors"),
        exclude={label_col, fwd_col, pred_ret_col, pred_prob_col, *target_output_cols},
    )
    feature_cols = [col for col in feature_cols if col not in target_output_cols]
    use_exogenous_features = bool(model_cfg.get("use_features", True))
    active_feature_cols = feature_cols if use_exogenous_features else []
    if required_features and not active_feature_cols:
        raise ValueError("No feature columns resolved for model training.")
    minimum_expected_features = model_cfg.get(
        "minimum_expected_features",
        model_params.get("minimum_expected_features"),
    )
    if minimum_expected_features is not None:
        minimum_expected = int(minimum_expected_features)
        if len(active_feature_cols) <= minimum_expected:
            raise ValueError(
                "Resolved model feature count is below the configured integrity floor: "
                f"{len(active_feature_cols)} <= minimum_expected_features={minimum_expected}."
            )
    feature_selection_meta = describe_feature_set(
        active_feature_cols,
        feature_selectors=model_cfg.get("feature_selectors"),
    )
    feature_coverage: list[dict[str, Any]] = []
    if active_feature_cols:
        for feature in active_feature_cols:
            series = pd.to_numeric(out[feature], errors="coerce")
            non_missing = series.notna()
            feature_coverage.append(
                {
                    "feature": str(feature),
                    "coverage_pct": float(non_missing.mean()) if len(series) else 0.0,
                    "missingness_pct": float(1.0 - non_missing.mean()) if len(series) else 1.0,
                    "variance": float(series.dropna().var(ddof=1)) if int(non_missing.sum()) >= 2 else 0.0,
                }
            )
    feature_selection_meta.update(
        {
            "raw_feature_count": int(len(out.select_dtypes(include=["number"]).columns)),
            "active_feature_count": int(len(active_feature_cols)),
            "selected_feature_count": int(len(active_feature_cols)),
            "model_feature_count": int(len(active_feature_cols)),
            "actual_model_feature_count": int(len(active_feature_cols)),
            "reported_feature_count": int(len(active_feature_cols)),
            "resolved_features": list(active_feature_cols),
            "active_features": list(active_feature_cols),
            "selected_features": list(active_feature_cols),
            "final_feature_names": list(active_feature_cols),
            "dropped_features": [],
            "missing_features": [],
            "dropped_missing_count": 0,
            "dropped_constant_count": 0,
            "dropped_selector_count": 0,
            "feature_coverage": feature_coverage,
            "feature_coverage_heatmap": feature_coverage,
        }
    )
    if feature_selection_meta["reported_feature_count"] != feature_selection_meta["actual_model_feature_count"]:
        raise AssertionError("reported_feature_count must equal actual_model_feature_count.")
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
        feature_selection_meta,
        {"split_method": split_method},
    )


def train_forward_forecaster(
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
    Apply the registered ``forward_forecaster`` model transformation.
    
    This model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        model:
          kind: forward_forecaster
          params:
            model_kind: <required>
            fold_predictor: <required>
            returns_col: null
            required_features: false
            runtime_estimator_family: statsmodels
            active_feature_count: <configured>
            actual_model_feature_count: <configured>
            diagnostics: <configured>
            dropped_constant_count: <configured>
            dropped_missing_count: <configured>
            dropped_selector_count: <configured>
            feature_pipeline: <configured>
            final_feature_names: <configured>
            model_feature_count: <configured>
            model_train_rows: <configured>
            params: <configured>
            pred_is_oos_col: <configured>
            pred_prob_col: <configured>
            pred_ret_col: <configured>
            pred_vol: <configured>
            prob_scale: <configured>
            raw_feature_count: <configured>
            reported_feature_count: <configured>
            resolved_feature_count: <configured>
            selected_feature_count: <configured>
            threshold: <configured>
            train_rows_raw: <configured>
    
    Required input columns
    ----------------------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    pred_is_oos_col:
        Input dataframe column configured by ``pred_is_oos_col``. Default: ``<configured>``.
    pred_prob_col:
        Input dataframe column configured by ``pred_prob_col``. Default: ``<configured>``.
    pred_ret_col:
        Input dataframe column configured by ``pred_ret_col``. Default: ``<configured>``.
    
    Parameters
    ----------
    model_kind:
        Configuration parameter accepted by this model.
    fold_predictor:
        Configuration parameter accepted by this model.
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    required_features:
        Configuration parameter accepted by this model. Default: ``false``.
    runtime_estimator_family:
        Configuration parameter accepted by this model. Default: ``statsmodels``.
    active_feature_count:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    actual_model_feature_count:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    diagnostics:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    dropped_constant_count:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    dropped_missing_count:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    dropped_selector_count:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    feature_pipeline:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    final_feature_names:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    model_feature_count:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    model_train_rows:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    params:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    pred_is_oos_col:
        Input dataframe column configured by ``pred_is_oos_col``. Default: ``<configured>``.
    pred_prob_col:
        Input dataframe column configured by ``pred_prob_col``. Default: ``<configured>``.
    pred_ret_col:
        Input dataframe column configured by ``pred_ret_col``. Default: ``<configured>``.
    pred_vol:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    prob_scale:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    raw_feature_count:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    reported_feature_count:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    resolved_feature_count:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    selected_feature_count:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    threshold:
        Numeric threshold used by this model. Default: ``<configured>``.
    train_rows_raw:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    """
    model_cfg = dict(model_cfg or {})
    model_params = dict(model_cfg.get("params", {}) or {})
    pred_ret_col = str(model_cfg.get("pred_ret_col") or "pred_ret")
    pred_prob_col = str(model_cfg.get("pred_prob_col") or "pred_prob")
    pred_is_oos_col = str(model_cfg.get("pred_is_oos_col") or "pred_is_oos")
    work_df, overlay_predictor, overlay_params, overlay_meta = resolve_garch_overlay(
        df,
        model_cfg=model_cfg,
        returns_col=returns_col,
    )

    (
        out,
        feature_cols,
        fwd_col,
        target_meta,
        splits,
        runtime_meta,
        contract_meta,
        feature_selection_meta,
        split_meta,
    ) = prepare_forecaster_inputs(
        df=work_df,
        model_cfg=model_cfg,
        model_params=model_params,
        pred_ret_col=pred_ret_col,
        pred_prob_col=pred_prob_col,
        required_features=required_features,
        runtime_estimator_family=runtime_estimator_family,
    )

    pred_ret = pd.Series(np.nan, index=out.index, name=pred_ret_col, dtype="float32")
    pred_prob = pd.Series(np.nan, index=out.index, name=pred_prob_col, dtype="float32")
    oos_mask = pd.Series(False, index=out.index, name=pred_is_oos_col)
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
    fold_feature_importances: list[list[dict[str, Any]]] = []
    target_distributions: list[dict[str, Any]] = []
    total_test_rows_without_prediction = 0
    folds_with_zero_predictions = 0

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

        model_params_for_fold = dict(model_params)
        if model_cfg.get("diagnostics") is not None:
            model_params_for_fold["_diagnostics"] = dict(model_cfg.get("diagnostics", {}) or {})

        pred_ret_fold, extra_cols_fold, fitted_model, fold_extra_meta = fold_predictor(
            out,
            safe_train_idx,
            np.asarray(split.test_idx, dtype=int),
            feature_cols,
            fwd_col,
            model_params_for_fold,
            runtime_meta,
        )
        model = fitted_model

        test_index = out.index[np.asarray(split.test_idx, dtype=int)]
        fold_feature_importance = extract_feature_importance(fitted_model, feature_cols)
        fold_feature_importances.append(fold_feature_importance)
        pred_ret_fold = pd.Series(pred_ret_fold, copy=False).astype(float)
        pred_ret_fold = pred_ret_fold.loc[pred_ret_fold.index.intersection(test_index)]
        pred_ret.loc[pred_ret_fold.index] = pred_ret_fold.astype("float32")
        pred_rows = int(len(pred_ret_fold))
        total_test_rows_without_prediction += int(len(split.test_idx) - pred_rows)
        if pred_rows == 0:
            folds_with_zero_predictions += 1

        for col_name, values in dict(extra_cols_fold or {}).items():
            if col_name not in extra_prediction_cols:
                extra_prediction_cols[col_name] = pd.Series(
                    np.nan,
                    index=out.index,
                    name=col_name,
                    dtype="float32",
                )
            series = pd.Series(values, copy=False).astype(float)
            series = series.loc[series.index.intersection(test_index)]
            extra_prediction_cols[col_name].loc[series.index] = series.astype("float32")

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
                series = series.loc[series.index.intersection(test_index)]
                extra_prediction_cols[col_name].loc[series.index] = series.astype("float32")

        fold_scale = fold_extra_meta.get("prob_scale")
        fold_prob = forecast_to_probability(pred_ret_fold, scale=fold_scale)
        pred_prob.loc[fold_prob.index] = fold_prob

        eval_true = out.loc[pred_ret_fold.index, fwd_col].astype(float)
        eval_true = eval_true.loc[eval_true.notna()]
        eval_pred = pred_ret_fold.reindex(eval_true.index).astype(float)
        eval_prob = fold_prob.reindex(eval_true.index).astype(float)
        target_distribution = summarize_numeric_distribution(eval_true)
        prediction_distribution = summarize_numeric_distribution(eval_pred)
        target_distributions.append(target_distribution)

        regression_summary = regression_metrics(eval_true, eval_pred)
        classification_summary = binary_classification_metrics((eval_true > threshold).astype(int), eval_prob)
        volatility_summary = empty_volatility_metrics()
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
            volatility_summary = volatility_metrics(realized_vol, pred_vol_eval)
            if volatility_summary["evaluation_rows"] and volatility_summary["evaluation_rows"] > 0:
                y_vol_pred_all.append(pred_vol_eval.to_numpy(dtype=float))
                y_vol_true_all.append(realized_vol.to_numpy(dtype=float))

        if regression_summary["evaluation_rows"] and regression_summary["evaluation_rows"] > 0:
            y_eval_all.append(eval_true.to_numpy(dtype=float))
            y_pred_all.append(eval_pred.to_numpy(dtype=float))
        if classification_summary["evaluation_rows"] and classification_summary["evaluation_rows"] > 0:
            y_prob_all.append(eval_prob.to_numpy(dtype=float))

        fold_test_idx = out.index[np.asarray(split.test_idx, dtype=int)]
        oos_mask.loc[fold_test_idx] = True
        oos_assignment_count.loc[fold_test_idx] += 1

        train_target_rows = int(out.iloc[safe_train_idx][fwd_col].notna().sum())
        total_train_rows += train_target_rows
        total_test_pred_rows += pred_rows
        model_train_rows = int(fold_extra_meta.get("model_train_rows", train_target_rows) or 0)
        selected_feature_count = int(fold_extra_meta.get("selected_feature_count", len(feature_cols)) or 0)
        model_feature_count = int(fold_extra_meta.get("model_feature_count", len(feature_cols)) or 0)
        reported_feature_count = int(fold_extra_meta.get("reported_feature_count", model_feature_count) or 0)
        if reported_feature_count != model_feature_count:
            raise AssertionError("reported_feature_count must equal actual model_feature_count.")
        train_density = float(model_train_rows / max(int(len(safe_train_idx)), 1))
        target_density = float(train_target_rows / max(int(len(safe_train_idx)), 1))
        feature_pipeline_fold = {
            "raw_feature_count": int(feature_selection_meta.get("raw_feature_count", len(feature_cols)) or 0),
            "resolved_feature_count": int(feature_selection_meta.get("resolved_feature_count", len(feature_cols)) or 0),
            "active_feature_count": int(feature_selection_meta.get("active_feature_count", len(feature_cols)) or 0),
            "selected_feature_count": selected_feature_count,
            "model_feature_count": model_feature_count,
            "actual_model_feature_count": model_feature_count,
            "reported_feature_count": reported_feature_count,
            "dropped_missing_count": int(fold_extra_meta.get("dropped_missing_count", 0) or 0),
            "dropped_constant_count": int(fold_extra_meta.get("dropped_constant_count", 0) or 0),
            "dropped_selector_count": int(fold_extra_meta.get("dropped_selector_count", 0) or 0),
            "final_feature_names": list(fold_extra_meta.get("final_feature_names", feature_cols) or []),
            "train_density": train_density,
            "target_density": target_density,
            "usable_row_pct": train_density,
        }

        fold_record = {
            "fold": int(split.fold),
            "train_start": int(split.train_start),
            "train_end": int(split.train_end),
            "effective_train_start": int(safe_train_idx.min()) if len(safe_train_idx) else None,
            "effective_train_end": int(safe_train_idx.max() + 1) if len(safe_train_idx) else None,
            "trimmed_for_horizon_rows": trimmed_rows,
            "test_start": int(split.test_start),
            "test_end": int(split.test_end),
            "train_rows_raw": int(len(safe_train_idx)),
            "train_rows": train_target_rows,
            "test_rows": int(len(split.test_idx)),
            "test_pred_rows": pred_rows,
            "train_feature_availability": summarize_feature_availability(out.iloc[safe_train_idx], feature_cols),
            "test_feature_availability": summarize_feature_availability(out.iloc[np.asarray(split.test_idx, dtype=int)], feature_cols),
            "test_rows_without_prediction": int(len(split.test_idx) - pred_rows),
            "feature_importance": fold_feature_importance,
            "target_distribution": target_distribution,
            "prediction_distribution": prediction_distribution,
            "classification_metrics": classification_summary,
            "regression_metrics": regression_summary,
            "volatility_metrics": volatility_summary,
            "feature_pipeline": feature_pipeline_fold,
            "train_density": train_density,
            "target_density": target_density,
            "usable_row_pct": train_density,
            "regression_target_stats": target_distribution,
        }
        fold_record.update(dict(fold_extra_meta or {}))
        if overlay_fold_meta:
            fold_record["overlay"] = overlay_fold_meta
        fold_meta.append(fold_record)
        report_optuna_fold(model_kind, int(split.fold), dict(fold_record))

    if model is None:
        raise ValueError("Model training failed: no valid folds were trained.")
    if (oos_assignment_count > 1).any():
        raise ValueError("Overlapping test windows detected. Use non-overlapping split configuration.")

    oos_regression_summary = empty_regression_metrics()
    if y_eval_all and y_pred_all:
        y_true_series = pd.Series(np.concatenate(y_eval_all), dtype=float)
        y_pred_series = pd.Series(np.concatenate(y_pred_all), dtype=float)
        oos_regression_summary = regression_metrics(y_true_series, y_pred_series)

    oos_classification_summary = empty_classification_metrics()
    if y_eval_all and y_prob_all:
        y_bin_series = pd.Series(np.concatenate(y_eval_all) > threshold, dtype=int)
        y_prob_series = pd.Series(np.concatenate(y_prob_all), dtype=float)
        oos_classification_summary = binary_classification_metrics(y_bin_series, y_prob_series)

    oos_volatility_summary = empty_volatility_metrics()
    if y_vol_true_all and y_vol_pred_all:
        y_vol_true_series = pd.Series(np.concatenate(y_vol_true_all), dtype=float)
        y_vol_pred_series = pd.Series(np.concatenate(y_vol_pred_all), dtype=float)
        oos_volatility_summary = volatility_metrics(y_vol_true_series, y_vol_pred_series)

    out[pred_ret_col] = pred_ret
    out[pred_prob_col] = pred_prob
    out[pred_is_oos_col] = oos_mask
    for col_name, series in sorted(extra_prediction_cols.items(), key=lambda kv: str(kv[0])):
        out[col_name] = series

    prediction_diagnostics = summarize_prediction_alignment(
        index=out.index,
        oos_mask=oos_mask,
        prediction=pred_ret,
        probability=pred_prob,
        target=out[fwd_col],
        pred_vol=extra_prediction_cols.get("pred_vol"),
    )

    meta = {
        "model_kind": model_kind,
        "runtime": runtime_meta,
        "feature_cols": feature_cols,
        "pred_ret_col": pred_ret_col,
        "pred_prob_col": pred_prob_col,
        "pred_is_oos_col": pred_is_oos_col,
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
        "feature_importance": aggregate_feature_importance(fold_feature_importances),
        "feature_importance_stability": summarize_feature_importance_stability(fold_feature_importances),
        "feature_selection": feature_selection_meta,
        "feature_pipeline": {
            "raw_feature_count": int(feature_selection_meta.get("raw_feature_count", len(feature_cols)) or 0),
            "resolved_feature_count": int(feature_selection_meta.get("resolved_feature_count", len(feature_cols)) or 0),
            "active_feature_count": int(feature_selection_meta.get("active_feature_count", len(feature_cols)) or 0),
            "selected_feature_count": int(feature_selection_meta.get("selected_feature_count", len(feature_cols)) or 0),
            "model_feature_count": int(feature_selection_meta.get("model_feature_count", len(feature_cols)) or 0),
            "actual_model_feature_count": int(feature_selection_meta.get("actual_model_feature_count", len(feature_cols)) or 0),
            "reported_feature_count": int(feature_selection_meta.get("reported_feature_count", len(feature_cols)) or 0),
            "dropped_missing_count": int(
                sum(int(fold.get("feature_pipeline", {}).get("dropped_missing_count", 0) or 0) for fold in fold_meta)
            ),
            "dropped_constant_count": int(
                sum(int(fold.get("feature_pipeline", {}).get("dropped_constant_count", 0) or 0) for fold in fold_meta)
            ),
            "dropped_selector_count": int(
                sum(int(fold.get("feature_pipeline", {}).get("dropped_selector_count", 0) or 0) for fold in fold_meta)
            ),
            "final_feature_names": list(feature_cols),
            "train_density": float(total_train_rows / max(sum(int(fold.get("train_rows_raw", 0) or 0) for fold in fold_meta), 1)),
            "target_density": float(total_train_rows / max(sum(int(fold.get("train_rows_raw", 0) or 0) for fold in fold_meta), 1)),
            "usable_row_pct": float(total_train_rows / max(sum(int(fold.get("train_rows_raw", 0) or 0) for fold in fold_meta), 1)),
        },
        "target_distribution": {
            "oos_target": summarize_numeric_distribution(np.concatenate(y_eval_all) if y_eval_all else []),
            "oos_prediction": summarize_numeric_distribution(np.concatenate(y_pred_all) if y_pred_all else []),
            "oos_direction": summarize_label_distribution(
                pd.Series(np.concatenate(y_eval_all) > threshold, dtype=int) if y_eval_all else pd.Series(dtype=int)
            ),
            "folds": target_distributions,
        },
        "prediction_diagnostics": prediction_diagnostics,
        "missing_value_diagnostics": {
            "test_rows_without_prediction": int(total_test_rows_without_prediction),
            "folds_with_zero_predictions": int(folds_with_zero_predictions),
        },
        "target": target_meta,
        "returns_col": returns_col,
        "overlay": overlay_meta,
        "contracts": contract_meta,
        "anti_leakage": {
            "target_horizon": target_horizon,
            "total_trimmed_train_rows": int(total_trimmed_rows),
        },
    }
    return out, model, meta


def train_sarimax_forecaster(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Apply the registered ``sarimax_forecaster`` model transformation.
    
    This model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        model:
          kind: sarimax_forecaster
          params:
            returns_col: null
    
    Required input columns
    ----------------------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    
    Parameters
    ----------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    """
    return train_forward_forecaster(
        df=df,
        model_cfg=model_cfg,
        model_kind="sarimax_forecaster",
        fold_predictor=train_sarimax_fold,
        returns_col=returns_col,
        required_features=False,
        runtime_estimator_family="statsmodels",
    )


def train_garch_forecaster(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Apply the registered ``garch_forecaster`` model transformation.
    
    This model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        model:
          kind: garch_forecaster
          params:
            returns_col: null
            params: <configured>
            price_col: <configured>
            returns_input_col: <configured>
            target: <configured>
    
    Required input columns
    ----------------------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``<configured>``.
    returns_input_col:
        Input dataframe column configured by ``returns_input_col``. Default: ``<configured>``.
    
    Parameters
    ----------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    params:
        Configuration parameter accepted by this model. Default: ``<configured>``.
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``<configured>``.
    returns_input_col:
        Input dataframe column configured by ``returns_input_col``. Default: ``<configured>``.
    target:
        Configuration parameter accepted by this model. Default: ``<configured>``.
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
    out, model, meta = train_forward_forecaster(
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


def train_lightgbm_regressor(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Apply the registered ``lightgbm_regressor`` model transformation.
    
    This model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        model:
          kind: lightgbm_regressor
          params:
            returns_col: null
    
    Required input columns
    ----------------------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    
    Parameters
    ----------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    """
    return train_forward_forecaster(
        df=df,
        model_cfg=model_cfg,
        model_kind="lightgbm_regressor",
        fold_predictor=make_lightgbm_regressor_fold_predictor(),
        returns_col=returns_col,
        required_features=True,
        runtime_estimator_family="lightgbm",
    )


def train_tft_forecaster(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Apply the registered ``tft_forecaster`` model transformation.
    
    This model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        model:
          kind: tft_forecaster
          params:
            returns_col: null
    
    Required input columns
    ----------------------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    
    Parameters
    ----------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    """
    return train_forward_forecaster(
        df=df,
        model_cfg=model_cfg,
        model_kind="tft_forecaster",
        fold_predictor=make_tft_fold_predictor(),
        returns_col=returns_col,
        required_features=True,
        runtime_estimator_family="torch",
    )


def train_lstm_forecaster(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Apply the registered ``lstm_forecaster`` model transformation.
    
    This model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        model:
          kind: lstm_forecaster
          params:
            returns_col: null
    
    Required input columns
    ----------------------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    
    Parameters
    ----------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    """
    return train_forward_forecaster(
        df,
        model_cfg,
        model_kind="lstm_forecaster",
        fold_predictor=make_lstm_fold_predictor(),
        returns_col=returns_col,
        required_features=True,
        runtime_estimator_family="torch",
    )


def train_patchtst_forecaster(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Apply the registered ``patchtst_forecaster`` model transformation.
    
    This model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        model:
          kind: patchtst_forecaster
          params:
            returns_col: null
    
    Required input columns
    ----------------------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    
    Parameters
    ----------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    """
    return train_forward_forecaster(
        df,
        model_cfg,
        model_kind="patchtst_forecaster",
        fold_predictor=make_patchtst_fold_predictor(),
        returns_col=returns_col,
        required_features=True,
        runtime_estimator_family="torch",
    )


def train_chronos_bolt_forecaster(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Apply the registered ``chronos_bolt_forecaster`` model transformation.

    This model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.

    YAML declaration::

        model:
          kind: chronos_bolt_forecaster
          params:
            returns_col: null
            source_col: close
            source_kind: price
            model_id: amazon/chronos-bolt-tiny
            lookback: 256
            min_context: 16
            prediction_length: <target horizon>
            quantiles: [0.1, 0.5, 0.9]

    Required input columns
    ----------------------
    source_col:
        Input dataframe column configured by ``model.params.source_col``. Default: target ``price_col`` or ``close``.
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.

    Parameters
    ----------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    source_col:
        Observed causal series to forecast. Default: target ``price_col`` or ``close``.
    source_kind:
        Either ``price`` or ``returns``. Default is inferred from ``source_col``.
    model_id:
        Hugging Face Chronos-Bolt checkpoint. Default: ``amazon/chronos-bolt-tiny``.
    lookback:
        Maximum trailing observations passed as context. Default: ``256``.
    min_context:
        Minimum finite trailing observations required for a row prediction. Default: ``16``.
    prediction_length:
        Forecast horizon requested from Chronos-Bolt. Defaults to the target horizon.
    quantiles:
        Quantile levels used for ``pred_qXX`` and ``pred_vol`` outputs. Default: ``[0.1, 0.5, 0.9]``.
    """
    return train_forward_forecaster(
        df,
        _foundation_model_cfg(model_cfg),
        model_kind="chronos_bolt_forecaster",
        fold_predictor=make_chronos_bolt_fold_predictor(),
        returns_col=returns_col,
        required_features=False,
        runtime_estimator_family="foundation",
    )


def train_chronos_2_forecaster(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Apply the registered ``chronos_2_forecaster`` model transformation.

    This model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.

    YAML declaration::

        model:
          kind: chronos_2_forecaster
          params:
            returns_col: null
            source_col: close
            source_kind: price
            model_id: amazon/chronos-2
            lookback: 256
            min_context: 16
            prediction_length: <target horizon>
            quantiles: [0.1, 0.5, 0.9]

    Required input columns
    ----------------------
    source_col:
        Input dataframe column configured by ``model.params.source_col``. Default: target ``price_col`` or ``close``.
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.

    Parameters
    ----------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    source_col:
        Observed causal series to forecast. Default: target ``price_col`` or ``close``.
    source_kind:
        Either ``price`` or ``returns``. Default is inferred from ``source_col``.
    model_id:
        Hugging Face Chronos-2 checkpoint. Default: ``amazon/chronos-2``.
    lookback:
        Maximum trailing observations passed as context. Default: ``256``.
    min_context:
        Minimum finite trailing observations required for a row prediction. Default: ``16``.
    prediction_length:
        Forecast horizon requested from Chronos-2. Defaults to the target horizon.
    quantiles:
        Quantile levels used for ``pred_qXX`` and ``pred_vol`` outputs. Default: ``[0.1, 0.5, 0.9]``.
    """
    return train_forward_forecaster(
        df,
        _foundation_model_cfg(model_cfg),
        model_kind="chronos_2_forecaster",
        fold_predictor=make_chronos2_fold_predictor(),
        returns_col=returns_col,
        required_features=False,
        runtime_estimator_family="foundation",
    )


def train_timesfm_2p5_200m_forecaster(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Apply the registered ``timesfm_2p5_200m_forecaster`` model transformation.

    This model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.

    YAML declaration::

        model:
          kind: timesfm_2p5_200m_forecaster
          params:
            returns_col: null
            source_col: close
            source_kind: price
            model_id: google/timesfm-2.5-200m-pytorch
            lookback: 512
            max_context: 512
            prediction_length: <target horizon>
            quantiles: [0.1, 0.5, 0.9]

    Required input columns
    ----------------------
    source_col:
        Input dataframe column configured by ``model.params.source_col``. Default: target ``price_col`` or ``close``.
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.

    Parameters
    ----------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    source_col:
        Observed causal series to forecast. Default: target ``price_col`` or ``close``.
    source_kind:
        Either ``price`` or ``returns``. Default is inferred from ``source_col``.
    model_id:
        Hugging Face TimesFM checkpoint. Default: ``google/timesfm-2.5-200m-pytorch``.
    lookback:
        Maximum trailing observations passed as context. Default: ``256``.
    max_context:
        TimesFM compile-time maximum context. Default: ``lookback``.
    max_horizon:
        TimesFM compile-time maximum horizon. Default: ``prediction_length``.
    prediction_length:
        Forecast horizon requested from TimesFM. Defaults to the target horizon.
    quantiles:
        Quantile levels mapped from TimesFM quantile-head outputs when available. Default: ``[0.1, 0.5, 0.9]``.
    """
    return train_forward_forecaster(
        df,
        _foundation_model_cfg(model_cfg),
        model_kind="timesfm_2p5_200m_forecaster",
        fold_predictor=make_timesfm_fold_predictor(
            setup="2p5_200m",
            default_model_id="google/timesfm-2.5-200m-pytorch",
        ),
        returns_col=returns_col,
        required_features=False,
        runtime_estimator_family="foundation",
    )


def train_timesfm_1p0_200m_forecaster(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    """
    Apply the registered ``timesfm_1p0_200m_forecaster`` model transformation.

    This model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.

    YAML declaration::

        model:
          kind: timesfm_1p0_200m_forecaster
          params:
            returns_col: null
            source_col: close
            source_kind: price
            model_id: google/timesfm-1.0-200m-pytorch
            lookback: 512
            max_context: 512
            prediction_length: <target horizon>
            frequency: 0

    Required input columns
    ----------------------
    source_col:
        Input dataframe column configured by ``model.params.source_col``. Default: target ``price_col`` or ``close``.
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.

    Parameters
    ----------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    source_col:
        Observed causal series to forecast. Default: target ``price_col`` or ``close``.
    source_kind:
        Either ``price`` or ``returns``. Default is inferred from ``source_col``.
    model_id:
        Hugging Face TimesFM 1.0 checkpoint. Default: ``google/timesfm-1.0-200m-pytorch``.
    lookback:
        Maximum trailing observations passed as context. Default: ``256``.
    max_context:
        TimesFM hparams context length. Default: ``lookback``.
    prediction_length:
        Forecast horizon requested from TimesFM. Defaults to the target horizon.
    frequency:
        TimesFM 1.x frequency category: ``0`` high, ``1`` medium, ``2`` low. Default: ``0``.
    """
    return train_forward_forecaster(
        df,
        _foundation_model_cfg(model_cfg),
        model_kind="timesfm_1p0_200m_forecaster",
        fold_predictor=make_timesfm_fold_predictor(
            setup="1p0_200m",
            default_model_id="google/timesfm-1.0-200m-pytorch",
        ),
        returns_col=returns_col,
        required_features=False,
        runtime_estimator_family="foundation",
    )


__all__ = [
    "train_chronos_2_forecaster",
    "train_chronos_bolt_forecaster",
    "prepare_forecaster_inputs",
    "train_forward_forecaster",
    "train_garch_forecaster",
    "train_lightgbm_regressor",
    "train_lstm_forecaster",
    "train_patchtst_forecaster",
    "train_sarimax_forecaster",
    "train_timesfm_1p0_200m_forecaster",
    "train_timesfm_2p5_200m_forecaster",
    "train_tft_forecaster",
]
