from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd
from scipy.optimize import minimize


@dataclass(frozen=True)
class PortfolioConstraints:
    """
    Define the admissible region for portfolio weights, leverage, turnover, and optional group
    exposures so optimization and signal-to-weight projection share one explicit constraint
    contract.
    """
    min_weight: float = -1.0
    max_weight: float = 1.0
    max_gross_leverage: float = 1.0
    target_net_exposure: float = 0.0
    turnover_limit: float | None = None
    group_max_exposure: Mapping[str, float] | None = None

    def __post_init__(self) -> None:
        """
        Validate the dataclass fields immediately after initialization so invalid constraint
        combinations fail fast and cannot leak deeper into the portfolio pipeline.
        """
        if self.min_weight > self.max_weight:
            raise ValueError("min_weight must be <= max_weight.")
        if self.max_gross_leverage <= 0:
            raise ValueError("max_gross_leverage must be > 0.")
        if self.turnover_limit is not None and self.turnover_limit < 0:
            raise ValueError("turnover_limit must be >= 0 when provided.")
        if self.group_max_exposure is not None:
            for group, cap in self.group_max_exposure.items():
                if cap <= 0:
                    raise ValueError(f"group_max_exposure[{group!r}] must be > 0.")


def _as_weight_series(weights: pd.Series) -> pd.Series:
    """
    Handle as weight series inside the portfolio construction layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    if not isinstance(weights, pd.Series):
        raise TypeError("weights must be a pandas Series.")
    return weights.astype(float).fillna(0.0).copy()


def apply_weight_bounds(
    weights: pd.Series,
    *,
    min_weight: float,
    max_weight: float,
) -> pd.Series:
    """
    Apply weight bounds to the provided inputs in a controlled and reusable way. The helper
    makes a single transformation step explicit inside the broader portfolio construction
    workflow.
    """
    out = _as_weight_series(weights)
    return out.clip(lower=min_weight, upper=max_weight)


def enforce_gross_leverage(
    weights: pd.Series,
    *,
    max_gross_leverage: float,
) -> pd.Series:
    """
    Enforce gross leverage as a hard constraint inside the portfolio construction layer. The
    helper projects candidate values back into an admissible region before later steps rely on
    them.
    """
    out = _as_weight_series(weights)
    gross = float(np.abs(out).sum())
    if gross <= max_gross_leverage or gross <= 0:
        return out
    return out * (max_gross_leverage / gross)


def _distribute_delta_with_bounds(
    weights: pd.Series,
    *,
    delta: float,
    min_weight: float,
    max_weight: float,
) -> pd.Series:
    """
    Handle distribute delta with bounds inside the portfolio construction layer. The helper
    isolates one focused responsibility so the surrounding code remains modular, readable, and
    easier to test.
    """
    out = _as_weight_series(weights)
    remaining = float(delta)
    if abs(remaining) < 1e-12:
        return out

    for _ in range(32):
        if abs(remaining) < 1e-10:
            break
        if remaining > 0:
            eligible = out < (max_weight - 1e-12)
            if not bool(eligible.any()):
                break
            capacity = (max_weight - out[eligible]).sum()
            if capacity <= 0:
                break
            applied = min(remaining, float(capacity))
            weights_step = max_weight - out[eligible]
            weights_step = weights_step / float(weights_step.sum())
            out.loc[eligible] = out.loc[eligible] + weights_step * applied
            remaining -= applied
            continue

        eligible = out > (min_weight + 1e-12)
        if not bool(eligible.any()):
            break
        capacity = (out[eligible] - min_weight).sum()
        if capacity <= 0:
            break
        applied = min(abs(remaining), float(capacity))
        weights_step = out[eligible] - min_weight
        weights_step = weights_step / float(weights_step.sum())
        out.loc[eligible] = out.loc[eligible] - weights_step * applied
        remaining += applied

    return out


def enforce_net_exposure(
    weights: pd.Series,
    *,
    target_net_exposure: float,
    min_weight: float,
    max_weight: float,
) -> pd.Series:
    """
    Enforce net exposure as a hard constraint inside the portfolio construction layer. The
    helper projects candidate values back into an admissible region before later steps rely on
    them.
    """
    out = _as_weight_series(weights)
    delta = float(target_net_exposure - out.sum())
    if abs(delta) < 1e-10:
        return out
    return _distribute_delta_with_bounds(
        out,
        delta=delta,
        min_weight=min_weight,
        max_weight=max_weight,
    )


def enforce_group_caps(
    weights: pd.Series,
    *,
    asset_to_group: Mapping[str, str] | None,
    group_max_exposure: Mapping[str, float] | None,
) -> pd.Series:
    """
    Enforce group caps as a hard constraint inside the portfolio construction layer. The helper
    projects candidate values back into an admissible region before later steps rely on them.
    """
    out = _as_weight_series(weights)
    if not asset_to_group or not group_max_exposure:
        return out

    for group, cap in group_max_exposure.items():
        members = [asset for asset in out.index if asset_to_group.get(str(asset)) == group]
        if not members:
            continue
        exposure = float(np.abs(out.loc[members]).sum())
        if exposure <= cap or exposure <= 0:
            continue
        scale = cap / exposure
        out.loc[members] = out.loc[members] * scale
    return out


def enforce_turnover_limit(
    weights: pd.Series,
    *,
    prev_weights: pd.Series | None,
    turnover_limit: float | None,
) -> pd.Series:
    """
    Enforce turnover limit as a hard constraint inside the portfolio construction layer. The
    helper projects candidate values back into an admissible region before later steps rely on
    them.
    """
    out = _as_weight_series(weights)
    if prev_weights is None or turnover_limit is None:
        return out

    prev = _as_weight_series(prev_weights).reindex(out.index).fillna(0.0)
    trades = out - prev
    turnover = float(np.abs(trades).sum())
    if turnover <= turnover_limit or turnover <= 0:
        return out
    scale = float(turnover_limit / turnover)
    return prev + trades * scale


def _compute_group_gross_exposure(
    weights: pd.Series,
    *,
    constraints: PortfolioConstraints,
    asset_to_group: Mapping[str, str] | None,
) -> dict[str, float]:
    """
    Compute per-group gross exposures for diagnostics and constraint validation.
    """
    group_gross: dict[str, float] = {}
    if constraints.group_max_exposure and asset_to_group:
        for group in constraints.group_max_exposure:
            members = [asset for asset in weights.index if asset_to_group.get(str(asset)) == group]
            group_gross[group] = float(np.abs(weights.loc[members]).sum()) if members else 0.0
    return group_gross


def _constraint_violations(
    weights: pd.Series,
    *,
    constraints: PortfolioConstraints,
    prev_weights: pd.Series | None,
    asset_to_group: Mapping[str, str] | None,
    tol: float = 1e-8,
) -> dict[str, float | dict[str, float]]:
    """
    Summarize hard-constraint violations so callers can fail loudly instead of accepting an
    invalid portfolio.
    """
    out = _as_weight_series(weights)
    violations: dict[str, float | dict[str, float]] = {}

    lower_violation = float(max(constraints.min_weight - float(out.min()), 0.0))
    upper_violation = float(max(float(out.max()) - constraints.max_weight, 0.0))
    if lower_violation > tol or upper_violation > tol:
        violations["bounds"] = max(lower_violation, upper_violation)

    net_error = float(abs(float(out.sum()) - constraints.target_net_exposure))
    if net_error > tol:
        violations["net_exposure"] = net_error

    gross_excess = float(np.abs(out).sum()) - float(constraints.max_gross_leverage)
    if gross_excess > tol:
        violations["gross_exposure"] = float(gross_excess)

    if prev_weights is not None and constraints.turnover_limit is not None:
        prev = _as_weight_series(prev_weights).reindex(out.index).fillna(0.0)
        turnover_excess = float(np.abs(out - prev).sum()) - float(constraints.turnover_limit)
        if turnover_excess > tol:
            violations["turnover"] = float(turnover_excess)

    group_gross = _compute_group_gross_exposure(
        out,
        constraints=constraints,
        asset_to_group=asset_to_group,
    )
    group_excess = {
        group: float(exposure - constraints.group_max_exposure[group])
        for group, exposure in group_gross.items()
        if constraints.group_max_exposure is not None
        and float(exposure - constraints.group_max_exposure[group]) > tol
    }
    if group_excess:
        violations["group_gross_exposure"] = group_excess

    return violations


def _build_diagnostics(
    weights: pd.Series,
    *,
    constraints: PortfolioConstraints,
    prev_weights: pd.Series | None,
    asset_to_group: Mapping[str, str] | None,
) -> dict[str, float | dict[str, float]]:
    """
    Build the standard diagnostics payload returned by constraint projection helpers.
    """
    out = _as_weight_series(weights)
    turnover = 0.0
    if prev_weights is not None:
        prev = _as_weight_series(prev_weights).reindex(out.index).fillna(0.0)
        turnover = float(np.abs(out - prev).sum())

    diagnostics: dict[str, float | dict[str, float]] = {
        "net_exposure": float(out.sum()),
        "gross_exposure": float(np.abs(out).sum()),
        "turnover": turnover,
    }
    group_gross = _compute_group_gross_exposure(
        out,
        constraints=constraints,
        asset_to_group=asset_to_group,
    )
    if group_gross:
        diagnostics["group_gross_exposure"] = group_gross
    return diagnostics


def _project_with_turnover_limit(
    weights: pd.Series,
    *,
    constraints: PortfolioConstraints,
    prev_weights: pd.Series,
    asset_to_group: Mapping[str, str] | None,
    n_projection_passes: int,
) -> pd.Series:
    """
    Solve a closest-feasible projection when turnover is a hard constraint. Sequential scaling
    can violate net or group exposures, so this path treats all hard constraints jointly.
    """
    target = _as_weight_series(weights)
    prev = _as_weight_series(prev_weights).reindex(target.index).fillna(0.0)

    x0 = target.copy()
    for _ in range(max(int(n_projection_passes), 1)):
        x0 = apply_weight_bounds(
            x0,
            min_weight=constraints.min_weight,
            max_weight=constraints.max_weight,
        )
        x0 = enforce_group_caps(
            x0,
            asset_to_group=asset_to_group,
            group_max_exposure=constraints.group_max_exposure,
        )
        x0 = enforce_net_exposure(
            x0,
            target_net_exposure=constraints.target_net_exposure,
            min_weight=constraints.min_weight,
            max_weight=constraints.max_weight,
        )
        x0 = enforce_gross_leverage(
            x0,
            max_gross_leverage=constraints.max_gross_leverage,
        )
    x0 = enforce_turnover_limit(
        x0,
        prev_weights=prev,
        turnover_limit=constraints.turnover_limit,
    )
    x0 = apply_weight_bounds(
        x0,
        min_weight=constraints.min_weight,
        max_weight=constraints.max_weight,
    )
    x0 = enforce_gross_leverage(
        x0,
        max_gross_leverage=constraints.max_gross_leverage,
    )

    if not _constraint_violations(
        x0,
        constraints=constraints,
        prev_weights=prev,
        asset_to_group=asset_to_group,
    ):
        return x0

    target_np = target.to_numpy(dtype=float)
    prev_np = prev.to_numpy(dtype=float)

    def objective(w: np.ndarray) -> float:
        diff = w - target_np
        return 0.5 * float(diff @ diff)

    cons: list[dict[str, object]] = [
        {
            "type": "eq",
            "fun": lambda w, t=constraints.target_net_exposure: float(np.sum(w) - t),
        },
        {
            "type": "ineq",
            "fun": lambda w, g=constraints.max_gross_leverage: float(g - np.abs(w).sum()),
        },
        {
            "type": "ineq",
            "fun": lambda w, p=prev_np, lim=float(constraints.turnover_limit): float(
                lim - np.abs(w - p).sum()
            ),
        },
    ]
    if constraints.group_max_exposure and asset_to_group:
        for group, cap in constraints.group_max_exposure.items():
            idx = [i for i, a in enumerate(target.index) if asset_to_group.get(str(a)) == group]
            if not idx:
                continue
            idx_arr = np.asarray(idx, dtype=int)
            cons.append(
                {
                    "type": "ineq",
                    "fun": lambda w, ii=idx_arr, c=cap: float(c - np.abs(w[ii]).sum()),
                }
            )

    result = minimize(
        objective,
        x0=x0.to_numpy(dtype=float),
        method="SLSQP",
        bounds=[(constraints.min_weight, constraints.max_weight) for _ in target.index],
        constraints=cons,
        options={"maxiter": 300, "ftol": 1e-9, "disp": False},
    )

    candidate = pd.Series(
        result.x if result.success else x0.to_numpy(dtype=float),
        index=target.index,
        dtype=float,
    )
    violations = _constraint_violations(
        candidate,
        constraints=constraints,
        prev_weights=prev,
        asset_to_group=asset_to_group,
    )
    if violations:
        raise ValueError(
            "Unable to satisfy portfolio constraints with the requested turnover limit. "
            f"Violations: {violations}"
        )
    return candidate


def apply_constraints(
    weights: pd.Series,
    *,
    constraints: PortfolioConstraints,
    prev_weights: pd.Series | None = None,
    asset_to_group: Mapping[str, str] | None = None,
    n_projection_passes: int = 3,
) -> tuple[pd.Series, dict[str, float | dict[str, float]]]:
    """
    Apply constraints to the provided inputs in a controlled and reusable way. The helper makes
    a single transformation step explicit inside the broader portfolio construction workflow.
    """
    out = _as_weight_series(weights)
    if constraints.turnover_limit is not None and prev_weights is not None:
        out = _project_with_turnover_limit(
            out,
            constraints=constraints,
            prev_weights=prev_weights,
            asset_to_group=asset_to_group,
            n_projection_passes=n_projection_passes,
        )
    else:
        for _ in range(max(int(n_projection_passes), 1)):
            out = apply_weight_bounds(
                out,
                min_weight=constraints.min_weight,
                max_weight=constraints.max_weight,
            )
            out = enforce_group_caps(
                out,
                asset_to_group=asset_to_group,
                group_max_exposure=constraints.group_max_exposure,
            )
            out = enforce_net_exposure(
                out,
                target_net_exposure=constraints.target_net_exposure,
                min_weight=constraints.min_weight,
                max_weight=constraints.max_weight,
            )
            out = enforce_gross_leverage(
                out,
                max_gross_leverage=constraints.max_gross_leverage,
            )

        out = apply_weight_bounds(
            out,
            min_weight=constraints.min_weight,
            max_weight=constraints.max_weight,
        )
        out = enforce_gross_leverage(
            out,
            max_gross_leverage=constraints.max_gross_leverage,
        )

    violations = _constraint_violations(
        out,
        constraints=constraints,
        prev_weights=prev_weights,
        asset_to_group=asset_to_group,
    )
    if violations:
        raise ValueError(f"Projected weights violate portfolio constraints: {violations}")

    diagnostics = _build_diagnostics(
        out,
        constraints=constraints,
        prev_weights=prev_weights,
        asset_to_group=asset_to_group,
    )
    return out, diagnostics


__all__ = [
    "PortfolioConstraints",
    "apply_weight_bounds",
    "enforce_net_exposure",
    "enforce_gross_leverage",
    "enforce_group_caps",
    "enforce_turnover_limit",
    "apply_constraints",
]
