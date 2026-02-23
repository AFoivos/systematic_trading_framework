from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from src.portfolio.constraints import PortfolioConstraints, apply_constraints


def _prepare_covariance(assets: pd.Index, covariance: pd.DataFrame | None) -> pd.DataFrame:
    if covariance is None:
        return pd.DataFrame(np.eye(len(assets), dtype=float), index=assets, columns=assets)

    if not isinstance(covariance, pd.DataFrame):
        raise TypeError("covariance must be a pandas DataFrame when provided.")

    cov = covariance.reindex(index=assets, columns=assets).astype(float)
    cov = cov.fillna(0.0)
    cov = (cov + cov.T) / 2.0
    return cov


def _initial_weights(
    assets: pd.Index,
    *,
    constraints: PortfolioConstraints,
    prev_weights: pd.Series | None,
) -> np.ndarray:
    n_assets = len(assets)
    if prev_weights is not None:
        w0 = prev_weights.reindex(assets).fillna(0.0).astype(float).to_numpy()
    else:
        base = constraints.target_net_exposure / max(n_assets, 1)
        w0 = np.full(n_assets, base, dtype=float)
    w0 = np.clip(w0, constraints.min_weight, constraints.max_weight)
    gross = np.abs(w0).sum()
    if gross > constraints.max_gross_leverage and gross > 0:
        w0 = w0 * (constraints.max_gross_leverage / gross)
    return w0


def optimize_mean_variance(
    expected_returns: pd.Series,
    *,
    covariance: pd.DataFrame | None = None,
    constraints: PortfolioConstraints | None = None,
    prev_weights: pd.Series | None = None,
    asset_to_group: Mapping[str, str] | None = None,
    risk_aversion: float = 5.0,
    trade_aversion: float = 0.0,
    allow_fallback: bool = True,
) -> tuple[pd.Series, dict[str, float | str | bool | dict[str, float]]]:
    if not isinstance(expected_returns, pd.Series):
        raise TypeError("expected_returns must be a pandas Series.")
    if risk_aversion < 0:
        raise ValueError("risk_aversion must be >= 0.")
    if trade_aversion < 0:
        raise ValueError("trade_aversion must be >= 0.")

    mu = expected_returns.astype(float).fillna(0.0)
    assets = mu.index
    if len(assets) == 0:
        raise ValueError("expected_returns is empty.")

    constraints = constraints or PortfolioConstraints()
    cov = _prepare_covariance(assets, covariance)
    mu_np = mu.to_numpy(dtype=float)
    cov_np = cov.to_numpy(dtype=float)

    prev_np: np.ndarray | None = None
    if prev_weights is not None:
        prev_np = prev_weights.reindex(assets).fillna(0.0).astype(float).to_numpy()

    def objective(w: np.ndarray) -> float:
        alpha_term = -float(mu_np @ w)
        risk_term = 0.5 * float(risk_aversion) * float(w @ cov_np @ w)
        trade_term = 0.0
        if prev_np is not None and trade_aversion > 0:
            diff = w - prev_np
            trade_term = 0.5 * float(trade_aversion) * float(diff @ diff)
        return alpha_term + risk_term + trade_term

    cons: list[dict] = [
        {
            "type": "eq",
            "fun": lambda w, t=constraints.target_net_exposure: float(np.sum(w) - t),
        },
        {
            "type": "ineq",
            "fun": lambda w, g=constraints.max_gross_leverage: float(g - np.abs(w).sum()),
        },
    ]

    if constraints.turnover_limit is not None and prev_np is not None:
        cons.append(
            {
                "type": "ineq",
                "fun": lambda w, p=prev_np, lim=constraints.turnover_limit: float(
                    lim - np.abs(w - p).sum()
                ),
            }
        )

    if constraints.group_max_exposure and asset_to_group:
        for group, cap in constraints.group_max_exposure.items():
            idx = [i for i, a in enumerate(assets) if asset_to_group.get(str(a)) == group]
            if not idx:
                continue
            idx_arr = np.asarray(idx, dtype=int)
            cons.append(
                {
                    "type": "ineq",
                    "fun": lambda w, ii=idx_arr, c=cap: float(c - np.abs(w[ii]).sum()),
                }
            )

    bounds = [(constraints.min_weight, constraints.max_weight) for _ in assets]
    x0 = _initial_weights(assets, constraints=constraints, prev_weights=prev_weights)

    result = minimize(
        objective,
        x0=x0,
        method="SLSQP",
        bounds=bounds,
        constraints=cons,
        options={"maxiter": 300, "ftol": 1e-9, "disp": False},
    )

    used_fallback = False
    if result.success:
        w = pd.Series(result.x, index=assets, dtype=float)
    else:
        if not allow_fallback:
            raise ValueError(f"Optimizer failed: {result.message}")
        used_fallback = True
        centered = mu - float(mu.mean())
        denom = float(np.abs(centered).sum())
        if denom > 0:
            raw = centered / denom
        else:
            raw = pd.Series(0.0, index=assets, dtype=float)
        w = raw * float(constraints.max_gross_leverage)

    w, diag = apply_constraints(
        w,
        constraints=constraints,
        prev_weights=prev_weights,
        asset_to_group=asset_to_group,
    )

    meta: dict[str, float | str | bool | dict[str, float]] = {
        "solver_success": bool(result.success),
        "solver_status": float(result.status),
        "solver_message": str(result.message),
        "used_fallback": used_fallback,
        "objective_value": float(objective(w.to_numpy(dtype=float))),
    }
    meta.update(diag)
    return w, meta


__all__ = ["optimize_mean_variance"]
