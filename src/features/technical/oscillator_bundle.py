from __future__ import annotations

from typing import Sequence

import pandas as pd

from .rsi import compute_rsi
from .stochastic import compute_stoch_d, compute_stoch_k


def add_oscillator_features(
    df: pd.DataFrame,
    price_col: str = "close",
    high_col: str = "high",
    low_col: str = "low",
    rsi_windows: Sequence[int] = (14,),
    stoch_windows: Sequence[int] = (14,),
    stoch_smooth: int = 3,
    inplace: bool = False,
) -> pd.DataFrame:
    missing = [c for c in (price_col, high_col, low_col) if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for oscillators: {missing}")

    out = df if inplace else df.copy()
    close = out[price_col].astype(float)
    high = out[high_col].astype(float)
    low = out[low_col].astype(float)

    for w in rsi_windows:
        out[f"{price_col}_rsi_{w}"] = compute_rsi(close, window=w, method="wilder")

    for w in stoch_windows:
        k = compute_stoch_k(close, high, low, window=w)
        d = compute_stoch_d(k, smooth=stoch_smooth)
        out[f"{price_col}_stoch_k_{w}"] = k
        out[f"{price_col}_stoch_d_{w}"] = d

    return out


__all__ = ["add_oscillator_features"]
