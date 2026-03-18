from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from src.portfolio.constraints import PortfolioConstraints, apply_constraints


def _prepare_covariance(assets: pd.Index, covariance: pd.DataFrame | None) -> pd.DataFrame:
    """
    Handle prepare covariance inside the portfolio construction layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    if covariance is None:
        return pd.DataFrame(np.eye(len(assets), dtype=float), index=assets, columns=assets)

    if not isinstance(covariance, pd.DataFrame):
        raise TypeError("covariance must be a pandas DataFrame when provided.")

    cov = covariance.reindex(index=assets, columns=assets).astype(float)
    cov = (cov + cov.T) / 2.0
    return cov


def _supported_assets_from_covariance(covariance: pd.DataFrame) -> pd.Index:
    """
    Keep only assets with a finite, positive variance estimate.
    """
    diag = pd.Series(
        np.diag(covariance.to_numpy(dtype=float)),
        index=covariance.index,
        dtype=float,
    )
    valid_diag = diag.notna() & np.isfinite(diag) & (diag > 0.0)
    return covariance.index[valid_diag]


def _meta_diagnostics(
    weights: pd.Series,
    *,
    constraints: PortfolioConstraints,
    prev_weights: pd.Series | None,
    asset_to_group: Mapping[str, str] | None,
) -> dict[str, float | dict[str, float]]:
    net_exposure = float(weights.sum())
    gross_exposure = float(np.abs(weights).sum())
    turnover = 0.0
    if prev_weights is not None:
        prev = prev_weights.reindex(weights.index).fillna(0.0).astype(float)
        turnover = float(np.abs(weights - prev).sum())

    diagnostics: dict[str, float | dict[str, float]] = {
        "net_exposure": net_exposure,
        "gross_exposure": gross_exposure,
        "turnover": turnover,
    }
    if constraints.group_max_exposure and asset_to_group:
        diagnostics["group_gross_exposure"] = {
            str(group): float(
                np.abs(
                    weights.loc[
                        [asset for asset in weights.index if asset_to_group.get(str(asset)) == group]
                    ]
                ).sum()
            )
            for group in constraints.group_max_exposure
        }
    return diagnostics


def _initial_weights(
    assets: pd.Index,
    *,
    constraints: PortfolioConstraints,
    prev_weights: pd.Series | None,
) -> np.ndarray:
    """
    Handle initial weights inside the portfolio construction layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
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


def _fallback_weights(
    expected_returns: pd.Series,
    *,
    constraints: PortfolioConstraints,
) -> pd.Series:
    """
    Build a deterministic fallback portfolio from centered expected returns when optimization is
    unavailable or infeasible.
    """
    centered = expected_returns.astype(float) - float(expected_returns.astype(float).mean())
    denom = float(np.abs(centered).sum())
    if denom > 0:
        raw = centered / denom
    else:
        raw = pd.Series(0.0, index=expected_returns.index, dtype=float)
    return raw * float(constraints.max_gross_leverage)


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
    """
    Handle optimize mean variance inside the portfolio construction layer. The helper isolates
    one focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    if not isinstance(expected_returns, pd.Series):
        raise TypeError("expected_returns must be a pandas Series.")
    if risk_aversion < 0:
        raise ValueError("risk_aversion must be >= 0.")
    if trade_aversion < 0:
        raise ValueError("trade_aversion must be >= 0.")

    mu_full = expected_returns.astype(float).fillna(0.0)
    all_assets = mu_full.index
    if len(all_assets) == 0:
        raise ValueError("expected_returns is empty.")

    constraints = constraints or PortfolioConstraints()
    cov_full = _prepare_covariance(all_assets, covariance)

    prev_full: pd.Series | None = None
    if prev_weights is not None:
        prev_full = prev_weights.reindex(all_assets).fillna(0.0).astype(float)

    effective_constraints = constraints
    unsupported_assets = pd.Index([], dtype=all_assets.dtype)
    if covariance is not None:
        supported_assets = _supported_assets_from_covariance(cov_full)
        unsupported_assets = all_assets.difference(supported_assets)
        if len(supported_assets) == 0:
            if allow_fallback and bool(np.isinf(cov_full.to_numpy(dtype=float)).any()):
                w = _fallback_weights(mu_full, constraints=constraints)
                w, _ = apply_constraints(
                    w,
                    constraints=constraints,
                    prev_weights=prev_full,
                    asset_to_group=asset_to_group,
                )
                meta: dict[str, float | str | bool | dict[str, float]] = {
                    "solver_success": False,
                    "solver_status": -1.0,
                    "solver_message": "Skipped optimizer because covariance contains no finite risk estimates.",
                    "used_fallback": True,
                    "objective_value": float("nan"),
                }
                meta.update(
                    _meta_diagnostics(
                        w,
                        constraints=constraints,
                        prev_weights=prev_full,
                        asset_to_group=asset_to_group,
                    )
                )
                if len(unsupported_assets) > 0:
                    meta["unsupported_covariance_assets"] = [str(asset) for asset in unsupported_assets]
                return w, meta
            raise ValueError("Covariance does not contain any assets with valid risk estimates.")

        if prev_full is not None and constraints.turnover_limit is not None and len(unsupported_assets) > 0:
            forced_turnover = float(np.abs(prev_full.reindex(unsupported_assets).fillna(0.0)).sum())
            remaining_turnover = float(constraints.turnover_limit) - forced_turnover
            if remaining_turnover < -1e-12:
                raise ValueError(
                    "Turnover limit is infeasible after forcing unsupported-covariance assets to zero."
                )
            effective_constraints = PortfolioConstraints(
                min_weight=constraints.min_weight,
                max_weight=constraints.max_weight,
                max_gross_leverage=constraints.max_gross_leverage,
                target_net_exposure=constraints.target_net_exposure,
                turnover_limit=max(remaining_turnover, 0.0),
                group_max_exposure=constraints.group_max_exposure,
            )

        mu = mu_full.loc[supported_assets]
        assets = mu.index
        cov = cov_full.loc[assets, assets].fillna(0.0)
    else:
        mu = mu_full
        assets = mu.index
        cov = cov_full

    mu_np = mu.to_numpy(dtype=float)
    cov_np = cov.to_numpy(dtype=float)

    prev_np: np.ndarray | None = None
    prev_supported: pd.Series | None = None
    if prev_full is not None:
        prev_supported = prev_full.reindex(assets).fillna(0.0)
        prev_np = prev_supported.to_numpy(dtype=float)

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

    if effective_constraints.turnover_limit is not None and prev_np is not None:
        cons.append(
            {
                "type": "ineq",
                "fun": lambda w, p=prev_np, lim=effective_constraints.turnover_limit: float(
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
    if not bool(np.isfinite(cov_np).all()):
        if not allow_fallback:
            raise ValueError("Covariance contains non-finite values.")

        w = _fallback_weights(mu, constraints=effective_constraints)
        w, _ = apply_constraints(
            w,
            constraints=effective_constraints,
            prev_weights=prev_supported,
            asset_to_group=asset_to_group,
        )

        meta: dict[str, float | str | bool | dict[str, float]] = {
            "solver_success": False,
            "solver_status": -1.0,
            "solver_message": "Skipped optimizer because covariance contains non-finite values.",
            "used_fallback": True,
            "objective_value": float("nan"),
        }
        full_w = pd.Series(0.0, index=all_assets, dtype=float)
        full_w.loc[w.index] = w
        meta.update(
            _meta_diagnostics(
                full_w,
                constraints=constraints,
                prev_weights=prev_full,
                asset_to_group=asset_to_group,
            )
        )
        if len(unsupported_assets) > 0:
            meta["unsupported_covariance_assets"] = [str(asset) for asset in unsupported_assets]
        return full_w, meta

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
        w = _fallback_weights(mu, constraints=effective_constraints)

    w, _ = apply_constraints(
        w,
        constraints=effective_constraints,
        prev_weights=prev_supported,
        asset_to_group=asset_to_group,
    )

    full_w = pd.Series(0.0, index=all_assets, dtype=float)
    full_w.loc[w.index] = w

    meta: dict[str, float | str | bool | dict[str, float]] = {
        "solver_success": bool(result.success),
        "solver_status": float(result.status),
        "solver_message": str(result.message),
        "used_fallback": used_fallback,
        "objective_value": float(objective(w.to_numpy(dtype=float))),
    }
    meta.update(
        _meta_diagnostics(
            full_w,
            constraints=constraints,
            prev_weights=prev_full,
            asset_to_group=asset_to_group,
        )
    )
    if len(unsupported_assets) > 0:
        meta["unsupported_covariance_assets"] = [str(asset) for asset in unsupported_assets]
    return full_w, meta


__all__ = ["optimize_mean_variance"]
