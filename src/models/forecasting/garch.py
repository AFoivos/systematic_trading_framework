from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd
from scipy.optimize import minimize


@dataclass(frozen=True)
class GarchState:
    """
    Carry fitted GARCH(1,1) parameters and the latest latent state for recursive forecasts.
    """
    mu: float
    omega: float
    alpha: float
    beta: float
    phi: float
    last_eps: float
    last_h: float
    used_fallback: bool
    optimizer_message: str


def fit_garch11_state(
    returns: pd.Series,
    *,
    mean_model: str = "constant",
) -> GarchState:
    """
    Fit a simple Gaussian GARCH(1,1) with optional AR(1) mean term.
    """
    x = returns.astype(float).dropna().to_numpy(dtype=float)
    if len(x) < 30:
        raise ValueError("GARCH requires at least 30 non-null training returns.")

    if mean_model not in {"zero", "constant", "ar1"}:
        raise ValueError("mean_model for GARCH must be one of: zero, constant, ar1.")

    mu = 0.0 if mean_model == "zero" else float(np.mean(x))
    eps = x - mu
    variance = float(np.var(eps, ddof=1))
    variance = max(variance, 1e-8)

    def objective(theta: np.ndarray) -> float:
        omega, alpha, beta = float(theta[0]), float(theta[1]), float(theta[2])
        if omega <= 0.0 or alpha < 0.0 or beta < 0.0 or (alpha + beta) >= 0.999:
            return 1e12
        h = np.empty_like(eps, dtype=float)
        h[0] = variance
        for t in range(1, len(eps)):
            h[t] = omega + alpha * (eps[t - 1] ** 2) + beta * h[t - 1]
            if h[t] <= 1e-12:
                h[t] = 1e-12
        ll = 0.5 * np.sum(np.log(2.0 * np.pi) + np.log(h) + (eps**2) / h)
        if not np.isfinite(ll):
            return 1e12
        return float(ll)

    x0 = np.array([variance * 0.05, 0.05, 0.90], dtype=float)
    bounds = [(1e-10, None), (1e-6, 0.999), (1e-6, 0.999)]
    res = minimize(objective, x0=x0, method="L-BFGS-B", bounds=bounds, options={"maxiter": 400})

    used_fallback = False
    if not res.success or not np.isfinite(res.fun):
        used_fallback = True
        omega, alpha, beta = variance * 0.05, 0.05, 0.90
        optimizer_message = f"fallback_after_optimizer_failure: {res.message}"
    else:
        omega, alpha, beta = map(float, res.x)
        if alpha + beta >= 0.999:
            used_fallback = True
            omega, alpha, beta = variance * 0.05, 0.05, 0.90
            optimizer_message = "fallback_after_nonstationary_solution"
        else:
            optimizer_message = str(res.message)

    h = np.empty_like(eps, dtype=float)
    h[0] = variance
    for t in range(1, len(eps)):
        h[t] = omega + alpha * (eps[t - 1] ** 2) + beta * h[t - 1]
        if h[t] <= 1e-12:
            h[t] = 1e-12

    phi = 0.0
    if mean_model == "ar1" and len(x) >= 4:
        lagged = x[:-1] - mu
        forward = x[1:] - mu
        denom = float(np.dot(lagged, lagged))
        if denom > 1e-12:
            phi = float(np.dot(lagged, forward) / denom)
            phi = float(np.clip(phi, -0.99, 0.99))

    return GarchState(
        mu=mu,
        omega=float(omega),
        alpha=float(alpha),
        beta=float(beta),
        phi=phi,
        last_eps=float(eps[-1]),
        last_h=float(max(h[-1], 1e-12)),
        used_fallback=used_fallback,
        optimizer_message=optimizer_message,
    )


def make_garch_fold_predictor(
    *,
    returns_input_col: str,
) -> Callable[
    [pd.DataFrame, np.ndarray, np.ndarray, list[str], str, dict[str, Any], dict[str, Any]],
    tuple[pd.Series, dict[str, pd.Series], object, dict[str, Any]],
]:
    """
    Build the fold predictor closure used by the experiment layer for the GARCH model family.
    """
    def _predictor(
        full_df: pd.DataFrame,
        train_idx: np.ndarray,
        test_idx: np.ndarray,
        feature_cols: list[str],
        target_col: str,
        model_params: dict[str, Any],
        runtime_meta: dict[str, Any],
    ) -> tuple[pd.Series, dict[str, pd.Series], object, dict[str, Any]]:
        del feature_cols, target_col
        train_df = full_df.iloc[train_idx]
        test_df = full_df.iloc[test_idx]
        mean_model = str(model_params.get("mean_model", "constant"))
        if mean_model not in {"zero", "constant", "ar1"}:
            raise ValueError("model.params.mean_model for GARCH must be one of: zero, constant, ar1.")
        if returns_input_col not in train_df.columns:
            raise KeyError(f"GARCH returns input column '{returns_input_col}' not found.")
        forecast_horizon = int(model_params.get("_target_horizon", 1))
        if forecast_horizon <= 0:
            raise ValueError("GARCH target forecast horizon must be positive.")

        garch_state = fit_garch11_state(train_df[returns_input_col], mean_model=mean_model)
        test_index = test_df.index
        if len(test_index) == 0:
            empty = pd.Series(dtype="float32", index=test_index)
            return (
                empty,
                {"pred_vol": empty},
                garch_state,
                {
                    "mean_model": mean_model,
                    "returns_input_col": returns_input_col,
                    "forecast_horizon": forecast_horizon,
                    "prob_scale": None,
                    "used_fallback": garch_state.used_fallback,
                    "optimizer_message": garch_state.optimizer_message,
                },
            )

        test_positions = np.asarray(test_idx, dtype=int)
        if bool((np.diff(test_positions) <= 0).any()):
            raise ValueError("GARCH test positions must be unique and increasing.")
        observed_returns = full_df[returns_input_col].astype(float)
        valid_train_returns = train_df[returns_input_col].astype(float).dropna()
        valid_train_positions = full_df.index.get_indexer(valid_train_returns.index)
        if bool((valid_train_positions < 0).any()):
            raise ValueError("GARCH could not map fitted return rows back to the full timeline.")
        state_origin_position = int(valid_train_positions[-1])
        if int(test_positions.min()) <= state_origin_position:
            raise ValueError("GARCH test positions must occur after the fitted state origin.")

        prev_r = float(valid_train_returns.iloc[-1])
        prev_eps = float(garch_state.last_eps)
        prev_h = float(garch_state.last_h)
        last_observed_position = state_origin_position

        pred_ret_values: list[float] = []
        pred_vol_values: list[float] = []
        for position in test_positions:
            # A row-t forward target is predicted after all row-t inputs are observed.
            # Roll the latent state through the label-purge gap and through the current
            # row before forecasting t+1...t+h.
            for observed_position in range(last_observed_position + 1, int(position) + 1):
                current_h = (
                    garch_state.omega
                    + garch_state.alpha * (prev_eps**2)
                    + garch_state.beta * prev_h
                )
                current_h = float(max(current_h, 1e-12))
                current_mean = (
                    garch_state.mu + garch_state.phi * (prev_r - garch_state.mu)
                    if mean_model == "ar1"
                    else garch_state.mu
                )
                realized = float(observed_returns.iloc[observed_position])
                if not np.isfinite(realized):
                    realized = float(current_mean)
                prev_eps = float(realized - garch_state.mu)
                prev_r = realized
                prev_h = current_h
            last_observed_position = int(position)

            horizon_variances: list[float] = []
            next_h = float(
                max(
                    garch_state.omega
                    + garch_state.alpha * (prev_eps**2)
                    + garch_state.beta * prev_h,
                    1e-12,
                )
            )
            forecast_prev_r = prev_r
            forecast_gross_return = 1.0
            for step in range(forecast_horizon):
                if step:
                    next_h = float(
                        max(
                            garch_state.omega
                            + (garch_state.alpha + garch_state.beta) * next_h,
                            1e-12,
                        )
                    )
                horizon_variances.append(next_h)
                expected_step_return = (
                    garch_state.mu
                    + garch_state.phi * (forecast_prev_r - garch_state.mu)
                    if mean_model == "ar1"
                    else garch_state.mu
                )
                forecast_gross_return *= 1.0 + float(expected_step_return)
                forecast_prev_r = float(expected_step_return)

            pred_ret_values.append(float(forecast_gross_return - 1.0))
            pred_vol_values.append(float(np.sqrt(np.sum(horizon_variances))))

        pred_ret = pd.Series(pred_ret_values, index=test_index, dtype="float32")
        pred_vol = pd.Series(pred_vol_values, index=test_index, dtype="float32")
        prob_scale = float(np.nanmean(pred_vol_values)) if pred_vol_values else None
        fold_meta = {
            "mean_model": mean_model,
            "returns_input_col": returns_input_col,
            "forecast_horizon": forecast_horizon,
            "state_origin_position": state_origin_position,
            "first_prediction_state_position": int(test_positions[0]),
            "variance_aggregation": "sum_conditional_variances",
            "return_aggregation": "compound_expected_step_returns",
            "garch_params": {
                "mu": garch_state.mu,
                "omega": garch_state.omega,
                "alpha": garch_state.alpha,
                "beta": garch_state.beta,
                "phi": garch_state.phi,
            },
            "used_fallback": bool(garch_state.used_fallback),
            "optimizer_message": garch_state.optimizer_message,
            "prob_scale": prob_scale,
            "runtime_threads": runtime_meta.get("threads"),
        }
        return pred_ret, {"pred_vol": pred_vol}, garch_state, fold_meta

    return _predictor


__all__ = ["GarchState", "fit_garch11_state", "make_garch_fold_predictor"]
