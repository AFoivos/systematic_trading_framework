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

    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of {_ALLOWED_MODES}")

    df = df.copy()
    df[signal_col] = 0

    long_mask = df[rsi_col] < buy_level
    short_mask = df[rsi_col] > sell_level

    if mode in {"long_only", "long_short", "long_short_hold"}:
        df.loc[long_mask, signal_col] = 1
    if mode in {"short_only", "long_short", "long_short_hold"}:
        df.loc[short_mask, signal_col] = -1

    return df
