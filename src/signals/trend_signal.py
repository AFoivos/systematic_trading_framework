from __future__ import annotations

import pandas as pd


_ALLOWED_MODES = {"long_only", "short_only", "long_short", "long_short_hold"}


def compute_trend_state_signal(
    df: pd.DataFrame,
    state_col: str,
    signal_col: str = "trend_state_signal",
    long_value: float = 1.0,
    flat_value: float = 0.0,
    short_value: float = -1.0,
    mode: str = "long_short_hold",
) -> pd.DataFrame:
    """
    Long-only signal based on a trend state column.
    """
    if state_col not in df.columns:
        raise KeyError(f"state_col '{state_col}' not found in DataFrame")
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of {_ALLOWED_MODES}")

    out = df.copy()
    out[signal_col] = flat_value
    state = out[state_col].astype(float)
    long_mask = state > 0.0
    short_mask = state < 0.0

    if mode in {"long_only", "long_short", "long_short_hold"}:
        out.loc[long_mask, signal_col] = long_value
    if mode in {"short_only", "long_short", "long_short_hold"}:
        out.loc[short_mask, signal_col] = short_value
    return out
