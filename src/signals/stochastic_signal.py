from __future__ import annotations

import pandas as pd


_ALLOWED_MODES = {"long_only", "short_only", "long_short", "long_short_hold"}


def compute_stochastic_signal(
    df: pd.DataFrame,
    k_col: str,
    buy_level: float = 20.0,
    sell_level: float = 80.0,
    signal_col: str = "stochastic_signal",
    mode: str = "long_short_hold",
) -> pd.DataFrame:
    """
    Stochastic signal from %K.
    Long when %K < buy_level, short when %K > sell_level.
    """
    if k_col not in df.columns:
        raise KeyError(f"k_col '{k_col}' not found in DataFrame")
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of {_ALLOWED_MODES}")

    out = df.copy()
    out[signal_col] = 0.0

    k = out[k_col].astype(float)
    long_mask = k < buy_level
    short_mask = k > sell_level

    if mode in {"long_only", "long_short", "long_short_hold"}:
        out.loc[long_mask, signal_col] = 1.0
    if mode in {"short_only", "long_short", "long_short_hold"}:
        out.loc[short_mask, signal_col] = -1.0

    return out
