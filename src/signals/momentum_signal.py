from __future__ import annotations

import pandas as pd


_ALLOWED_MODES = {"long_only", "short_only", "long_short", "long_short_hold"}


def compute_momentum_signal(
    df: pd.DataFrame,
    momentum_col: str,
    long_threshold: float = 0.0,
    short_threshold: float | None = None,
    signal_col: str = "momentum_signal",
    mode: str = "long_short_hold",
) -> pd.DataFrame:
    """
    Momentum signal from a precomputed momentum column.
    """
    if momentum_col not in df.columns:
        raise KeyError(f"momentum_col '{momentum_col}' not found in DataFrame")
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of {_ALLOWED_MODES}")

    out = df.copy()
    out[signal_col] = 0.0

    series = out[momentum_col].astype(float)
    long_mask = series > long_threshold

    if short_threshold is None and mode in {"short_only", "long_short", "long_short_hold"}:
        short_threshold = -abs(long_threshold)
    short_mask = series < short_threshold if short_threshold is not None else None

    if mode in {"long_only", "long_short", "long_short_hold"}:
        out.loc[long_mask, signal_col] = 1.0
    if short_mask is not None and mode in {"short_only", "long_short", "long_short_hold"}:
        out.loc[short_mask, signal_col] = -1.0

    return out
