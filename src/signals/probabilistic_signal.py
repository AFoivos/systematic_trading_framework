from __future__ import annotations

import pandas as pd

from src.signals._common import ALLOWED_DIRECTIONAL_MODES, resolve_signal_output_name


def probabilistic_signal(
    df: pd.DataFrame,
    prob_col: str,
    signal_col: str | None = None,
    upper: float = 0.55,
    lower: float = 0.45,
    mode: str = "long_short_hold",
) -> pd.Series:
    """
    Map probability forecasts to {-1,0,1} signal with dead-zone.
    """
    if prob_col not in df.columns:
        raise KeyError(f"prob_col '{prob_col}' not found in DataFrame")
    if mode not in ALLOWED_DIRECTIONAL_MODES:
        raise ValueError(f"mode must be one of {sorted(ALLOWED_DIRECTIONAL_MODES)}")

    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_prob",
    )
    prob = df[prob_col].astype(float)
    long_mask = prob > float(upper)
    short_mask = prob < float(lower)

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


__all__ = ["probabilistic_signal"]
