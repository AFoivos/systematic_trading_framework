from __future__ import annotations

import numpy as np
import pandas as pd

from src.signals._common import ALLOWED_DIRECTIONAL_MODES, resolve_signal_output_name


def probabilistic_signal(
    df: pd.DataFrame,
    prob_col: str,
    signal_col: str | None = None,
    upper: float = 0.55,
    lower: float = 0.45,
    upper_exit: float | None = None,
    lower_exit: float | None = None,
    mode: str = "long_short_hold",
    base_signal_col: str | None = None,
) -> pd.Series:
    """
    Map probability forecasts to {-1,0,1} signal with dead-zone.
    """
    if prob_col not in df.columns:
        raise KeyError(f"prob_col '{prob_col}' not found in DataFrame")
    if mode not in ALLOWED_DIRECTIONAL_MODES:
        raise ValueError(f"mode must be one of {sorted(ALLOWED_DIRECTIONAL_MODES)}")
    if base_signal_col is not None and base_signal_col not in df.columns:
        raise KeyError(f"base_signal_col '{base_signal_col}' not found in DataFrame")

    upper_entry = float(upper)
    lower_entry = float(lower)
    upper_exit_value = float(upper_exit if upper_exit is not None else upper_entry)
    lower_exit_value = float(lower_exit if lower_exit is not None else lower_entry)
    if not 0.0 < lower_entry <= lower_exit_value <= upper_exit_value <= upper_entry < 1.0:
        raise ValueError(
            "Thresholds must satisfy 0 < lower <= lower_exit <= upper_exit <= upper < 1."
        )

    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_prob",
    )
    prob = df[prob_col].astype(float)
    if base_signal_col is None and upper_exit is None and lower_exit is None:
        long_mask = prob > upper_entry
        short_mask = prob < lower_entry

        if mode == "long_short_hold":
            sig = pd.Series(pd.NA, index=df.index, name=output_col, dtype="Float64")
            sig.loc[long_mask] = 1.0
            sig.loc[short_mask] = -1.0
            return sig.ffill().fillna(0.0).astype(float)

        sig = pd.Series(0.0, index=df.index, name=output_col)
        if mode in {"long_only", "long_short"}:
            sig.loc[long_mask] = 1.0
        if mode in {"short_only", "long_short"}:
            sig.loc[short_mask] = -1.0
        return sig

    allow_long = mode in {"long_only", "long_short", "long_short_hold"}
    allow_short = mode in {"short_only", "long_short", "long_short_hold"}
    base_side = None
    if base_signal_col is not None:
        base_side = np.sign(df[base_signal_col].astype(float).fillna(0.0)).astype(float)
        if not allow_long:
            base_side = base_side.where(base_side < 0.0, 0.0)
        if not allow_short:
            base_side = base_side.where(base_side > 0.0, 0.0)

    states: list[float] = []
    state = 0.0
    for idx, p in prob.items():
        desired_side = None if base_side is None else float(base_side.loc[idx])
        has_prob = pd.notna(p)
        p_val = float(p) if has_prob else 0.0

        if desired_side == 0.0:
            state = 0.0
            states.append(state)
            continue

        if state > 0.0:
            if desired_side is not None and desired_side < 0.0:
                state = -1.0 if has_prob and allow_short and p_val <= lower_entry else 0.0
            elif has_prob and p_val <= upper_exit_value:
                state = 0.0
            else:
                state = 1.0
        elif state < 0.0:
            if desired_side is not None and desired_side > 0.0:
                state = 1.0 if has_prob and allow_long and p_val >= upper_entry else 0.0
            elif has_prob and p_val >= lower_exit_value:
                state = 0.0
            else:
                state = -1.0
        else:
            if desired_side is None:
                if has_prob and allow_long and p_val >= upper_entry:
                    state = 1.0
                elif has_prob and allow_short and p_val <= lower_entry:
                    state = -1.0
            elif desired_side > 0.0:
                state = 1.0 if has_prob and allow_long and p_val >= upper_entry else 0.0
            elif desired_side < 0.0:
                state = -1.0 if has_prob and allow_short and p_val <= lower_entry else 0.0
        states.append(state)

    return pd.Series(states, index=df.index, name=output_col, dtype=float)


__all__ = ["probabilistic_signal"]
