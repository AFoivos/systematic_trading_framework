from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PortfolioConstraints:
    min_weight: float = -1.0
    max_weight: float = 1.0
    max_gross_leverage: float = 1.0
    target_net_exposure: float = 0.0
    turnover_limit: float | None = None
    group_max_exposure: Mapping[str, float] | None = None

    def __post_init__(self) -> None:
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
    if not isinstance(weights, pd.Series):
        raise TypeError("weights must be a pandas Series.")
    return weights.astype(float).fillna(0.0).copy()


def apply_weight_bounds(
    weights: pd.Series,
    *,
    min_weight: float,
    max_weight: float,
) -> pd.Series:
    out = _as_weight_series(weights)
    return out.clip(lower=min_weight, upper=max_weight)


def enforce_gross_leverage(
    weights: pd.Series,
    *,
    max_gross_leverage: float,
) -> pd.Series:
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


def apply_constraints(
    weights: pd.Series,
    *,
    constraints: PortfolioConstraints,
    prev_weights: pd.Series | None = None,
    asset_to_group: Mapping[str, str] | None = None,
    n_projection_passes: int = 3,
) -> tuple[pd.Series, dict[str, float | dict[str, float]]]:
    out = _as_weight_series(weights)

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

    out = enforce_turnover_limit(
        out,
        prev_weights=prev_weights,
        turnover_limit=constraints.turnover_limit,
    )

    # Final clamp for numerical drift.
    out = apply_weight_bounds(
        out,
        min_weight=constraints.min_weight,
        max_weight=constraints.max_weight,
    )
    out = enforce_gross_leverage(
        out,
        max_gross_leverage=constraints.max_gross_leverage,
    )

    turnover = 0.0
    if prev_weights is not None:
        prev = _as_weight_series(prev_weights).reindex(out.index).fillna(0.0)
        turnover = float(np.abs(out - prev).sum())

    group_gross: dict[str, float] = {}
    if constraints.group_max_exposure and asset_to_group:
        for group in constraints.group_max_exposure:
            members = [asset for asset in out.index if asset_to_group.get(str(asset)) == group]
            group_gross[group] = float(np.abs(out.loc[members]).sum()) if members else 0.0

    diagnostics: dict[str, float | dict[str, float]] = {
        "net_exposure": float(out.sum()),
        "gross_exposure": float(np.abs(out).sum()),
        "turnover": turnover,
    }
    if group_gross:
        diagnostics["group_gross_exposure"] = group_gross

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

