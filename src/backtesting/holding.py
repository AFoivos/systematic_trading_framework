from __future__ import annotations

import pandas as pd


def apply_min_holding_bars_to_positions(
    positions: pd.Series,
    *,
    min_holding_bars: int = 0,
    atol: float = 1e-12,
) -> pd.Series:
    """
    Enforce a minimum number of bars between position changes on a 1D position path.

    The constraint is applied causally on the target position series and is model-agnostic,
    so it can be reused across rule-based, classifier, and forecaster workflows.
    """
    out = positions.astype(float).fillna(0.0).copy()
    bars = int(min_holding_bars)
    if bars <= 0 or out.empty:
        return out

    current = float(out.iloc[0])
    out.iloc[0] = current
    bars_since_switch = bars if abs(current) <= atol else 1

    for idx in range(1, len(out)):
        proposed = float(out.iloc[idx])
        switching = abs(proposed - current) > atol
        if switching and bars_since_switch < bars:
            out.iloc[idx] = current
            bars_since_switch += 1
            continue
        if switching:
            current = proposed
            bars_since_switch = 1
        else:
            bars_since_switch += 1
        out.iloc[idx] = current

    return out


def apply_min_holding_bars_to_weights(
    weights: pd.DataFrame,
    *,
    min_holding_bars: int = 0,
    atol: float = 1e-12,
) -> pd.DataFrame:
    """
    Enforce the same minimum-holding contract independently per asset weight column.
    """
    out = weights.astype(float).copy()
    bars = int(min_holding_bars)
    if bars <= 0 or out.empty:
        return out

    for col in out.columns:
        out[col] = apply_min_holding_bars_to_positions(
            out[col],
            min_holding_bars=bars,
            atol=atol,
        )
    return out


__all__ = [
    "apply_min_holding_bars_to_positions",
    "apply_min_holding_bars_to_weights",
]
