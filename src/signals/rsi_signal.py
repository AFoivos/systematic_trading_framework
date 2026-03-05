from __future__ import annotations

import pandas as pd


_ALLOWED_MODES = {"long_only", "short_only", "long_short", "long_short_hold"}

def compute_rsi_signal(
    df: pd.DataFrame,
    rsi_col: str,
    buy_level: float,
    sell_level: float,
    signal_col: str = "rsi_signal",
    mode: str = "long_short_hold",
) -> pd.DataFrame:

    """
    Compute RSI signal for the signal generation layer. The helper keeps the calculation
    isolated so the calling pipeline can reuse the same logic consistently across experiments.
    """
    if rsi_col not in df.columns:
        raise KeyError(f"rsi_col '{rsi_col}' not found in DataFrame")
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of {_ALLOWED_MODES}")

    df = df.copy()
    df[signal_col] = 0.0

    long_mask = df[rsi_col] < buy_level
    short_mask = df[rsi_col] > sell_level

    if mode == "long_short_hold":
        hold = pd.Series(pd.NA, index=df.index, dtype="Float64")
        hold.loc[long_mask] = 1.0
        hold.loc[short_mask] = -1.0
        df[signal_col] = hold.ffill().fillna(0.0).astype(float)
        return df

    if mode in {"long_only", "long_short"}:
        df.loc[long_mask, signal_col] = 1.0
    if mode in {"short_only", "long_short"}:
        df.loc[short_mask, signal_col] = -1.0

    return df
