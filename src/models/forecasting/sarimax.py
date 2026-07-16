from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX


def _normalized_order(
    value: Any,
    *,
    expected_len: int,
    name: str,
) -> tuple[int, ...]:
    """
    Normalize ARIMA-like order parameters to fixed-length integer tuples.
    """
    if not isinstance(value, (list, tuple)) or len(value) != expected_len:
        raise ValueError(f"{name} must be a list/tuple with length={expected_len}.")
    out = tuple(int(v) for v in value)
    if any(v < 0 for v in out):
        raise ValueError(f"{name} values must be >= 0.")
    return out


def train_sarimax_fold(
    full_df: pd.DataFrame,
    train_idx: np.ndarray,
    test_idx: np.ndarray,
    feature_cols: list[str],
    target_col: str,
    model_params: dict[str, Any],
    runtime_meta: dict[str, Any],
) -> tuple[pd.Series, dict[str, pd.Series], object, dict[str, Any]]:
    """
    Fit SARIMAX on one chronological fold and emit causal forecasts for the test window.
    """
    train_df = full_df.iloc[train_idx]
    test_df = full_df.iloc[test_idx]

    params = dict(model_params or {})
    order = _normalized_order(params.get("order", (1, 0, 1)), expected_len=3, name="model.params.order")
    seasonal_order = _normalized_order(
        params.get("seasonal_order", (0, 0, 0, 0)),
        expected_len=4,
        name="model.params.seasonal_order",
    )
    trend = params.get("trend", "c")
    enforce_stationarity = bool(params.get("enforce_stationarity", False))
    enforce_invertibility = bool(params.get("enforce_invertibility", False))
    maxiter = int(params.get("maxiter", 200))
    use_exog = bool(params.get("use_exog", True))
    allow_fallback = bool(params.get("allow_fallback", True))

    active_features = feature_cols if use_exog else []
    y_train = train_df[target_col].astype(float).dropna()
    if active_features:
        exog_train = train_df.loc[y_train.index, active_features].astype(float)
        valid_train = exog_train.notna().all(axis=1)
        y_train = y_train.loc[valid_train]
        exog_train = exog_train.loc[valid_train]
    else:
        exog_train = None

    min_rows = max(24, int(sum(order)) + 2)
    if len(y_train) < min_rows:
        raise ValueError(f"SARIMAX fold has only {len(y_train)} train rows; need at least {min_rows}.")

    test_positions = np.asarray(test_idx, dtype=int)
    pred_index = test_df.index
    train_positions = full_df.index.get_indexer(y_train.index)
    if bool((train_positions < 0).any()):
        raise ValueError("SARIMAX could not map fitted target rows back to the full timeline.")
    forecast_origin_position = int(train_positions[-1])
    forecast_steps = (
        int(test_positions.max()) - forecast_origin_position
        if len(test_positions)
        else 0
    )
    if len(test_positions) and (
        bool((np.diff(test_positions) <= 0).any())
        or int(test_positions.min()) <= forecast_origin_position
    ):
        raise ValueError("SARIMAX test positions must be unique, increasing, and after the fitted origin.")
    forecast_positions = np.arange(
        forecast_origin_position + 1,
        forecast_origin_position + forecast_steps + 1,
        dtype=int,
    )
    forecast_offsets = test_positions - forecast_origin_position - 1
    exog_forecast = None
    if active_features and forecast_steps:
        exog_forecast = full_df.iloc[forecast_positions][active_features].astype(float)
        valid_forecast_exog = exog_forecast.notna().all(axis=1)
        if not bool(valid_forecast_exog.all()):
            examples = ", ".join(
                str(ts) for ts in exog_forecast.index[~valid_forecast_exog][:5]
            )
            raise ValueError(
                "SARIMAX forecast path contains missing exogenous rows. "
                f"Cannot align forecasts safely for timestamps: {examples}"
            )

    used_fallback = False
    fallback_reason = None
    fit_result: object | dict[str, Any]
    try:
        model = SARIMAX(
            endog=y_train.to_numpy(dtype=float),
            exog=exog_train.to_numpy(dtype=float) if exog_train is not None else None,
            order=order,
            seasonal_order=seasonal_order,
            trend=trend,
            enforce_stationarity=enforce_stationarity,
            enforce_invertibility=enforce_invertibility,
        )
        fit_result = model.fit(disp=False, maxiter=maxiter)
        if len(pred_index) == 0:
            pred_mean_arr = np.asarray([], dtype=float)
            pred_var_arr = np.asarray([], dtype=float)
        else:
            forecast_res = fit_result.get_forecast(
                steps=forecast_steps,
                exog=exog_forecast.to_numpy(dtype=float) if exog_forecast is not None else None,
            )
            pred_mean_full = np.asarray(forecast_res.predicted_mean, dtype=float)
            pred_var_attr = getattr(forecast_res, "var_pred_mean", None)
            if pred_var_attr is None:
                pred_var_full = np.full(
                    len(pred_mean_full),
                    np.var(y_train.to_numpy(dtype=float)),
                    dtype=float,
                )
            else:
                pred_var_full = np.asarray(pred_var_attr, dtype=float)
            pred_mean_arr = pred_mean_full[forecast_offsets]
            pred_var_arr = pred_var_full[forecast_offsets]
    except Exception as exc:
        if not allow_fallback:
            raise
        used_fallback = True
        fallback_reason = f"{type(exc).__name__}: {exc}"
        fit_result = {"model": "sarimax", "fallback": True, "error": fallback_reason}
        fallback_mean = float(y_train.mean())
        fallback_var = float(np.var(y_train.to_numpy(dtype=float), ddof=1)) if len(y_train) >= 2 else 1e-6
        pred_mean_arr = np.full(len(pred_index), fallback_mean, dtype=float)
        pred_var_arr = np.full(len(pred_index), max(fallback_var, 1e-8), dtype=float)

    pred_mean = pd.Series(pred_mean_arr, index=pred_index, dtype="float32")
    pred_vol = pd.Series(np.sqrt(np.clip(pred_var_arr, 1e-12, None)), index=pred_index, dtype="float32")
    prob_scale = float(y_train.std(ddof=1)) if len(y_train) >= 2 else None
    fold_meta = {
        "order": list(order),
        "seasonal_order": list(seasonal_order),
        "trend": trend,
        "used_exog": bool(active_features),
        "used_fallback": used_fallback,
        "fallback_reason": fallback_reason,
        "prob_scale": prob_scale,
        "train_target_std": prob_scale,
        "forecast_origin_position": forecast_origin_position,
        "forecast_origin_gap_rows": (
            int(test_positions.min()) - forecast_origin_position - 1
            if len(test_positions)
            else 0
        ),
        "forecast_steps": forecast_steps,
        "runtime_threads": runtime_meta.get("threads"),
    }
    return pred_mean, {"pred_vol": pred_vol}, fit_result, fold_meta


__all__ = ["train_sarimax_fold"]
