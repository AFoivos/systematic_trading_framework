from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.evaluation.time_splits import (
    assert_no_forward_label_leakage,
    build_time_splits,
    trim_train_indices_for_horizon,
)
from src.experiments.contracts import TargetContract, validate_feature_target_contract
from src.experiments.optuna_runtime import report_optuna_fold
from src.experiments.support.diagnostics import (
    aggregate_feature_importance,
    extract_feature_importance,
    summarize_feature_availability,
    summarize_label_distribution,
    summarize_numeric_distribution,
    summarize_prediction_alignment,
)
from src.experiments.support.metrics import (
    binary_classification_metrics,
    empty_classification_metrics,
    empty_regression_metrics,
    empty_volatility_metrics,
    forecast_to_probability,
    regression_metrics,
    volatility_metrics,
)
from src.models.overlay import resolve_garch_overlay
from src.models.runtime import infer_feature_columns, resolve_runtime_for_model
from src.targets import build_forward_return_target
from src.models.types import ForecasterFoldPredictor
from src.models.garch import make_garch_fold_predictor
from src.models.lstm import make_lstm_fold_predictor
from src.models.patchtst import make_patchtst_fold_predictor
from src.models.sarimax import train_sarimax_fold
from src.models.tft import make_tft_fold_predictor


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
]:
    runtime_meta = resolve_runtime_for_model(
        model_cfg=model_cfg,
        model_params=model_params,
        estimator_family=runtime_estimator_family,
    )
    target_cfg = dict(model_cfg.get("target", {}) or {})
    target_kind = target_cfg.get("kind", "forward_return")
    if target_kind != "forward_return":
        raise ValueError(f"Unsupported target.kind: {target_kind}")

    out, label_col, fwd_col, target_meta = build_forward_return_target(df=df, target_cfg=target_cfg)
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
    model_cfg = dict(model_cfg or {})
    model_params = dict(model_cfg.get("params", {}) or {})
    pred_ret_col = str(model_cfg.get("pred_ret_col") or "pred_ret")
    pred_prob_col = str(model_cfg.get("pred_prob_col") or "pred_prob")
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
    out["pred_is_oos"] = oos_mask
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


def train_tft_forecaster(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
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
    return train_forward_forecaster(
        df,
        model_cfg,
        model_kind="patchtst_forecaster",
        fold_predictor=make_patchtst_fold_predictor(),
        returns_col=returns_col,
        required_features=True,
        runtime_estimator_family="torch",
    )


__all__ = [
    "prepare_forecaster_inputs",
    "train_forward_forecaster",
    "train_garch_forecaster",
    "train_lstm_forecaster",
    "train_patchtst_forecaster",
    "train_sarimax_forecaster",
    "train_tft_forecaster",
]
