from __future__ import annotations

from typing import Sequence

import pandas as pd


def add_vol_normalized_momentum_features(
    df: pd.DataFrame,
    returns_col: str = "close_logret",
    vol_col: str = "vol_rolling_20",
    windows: Sequence[int] = (5, 20, 60),
    eps: float = 1e-8,
    inplace: bool = False,
) -> pd.DataFrame:
    missing = [c for c in (returns_col, vol_col) if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for vol-normalized momentum features: {missing}")
    out = df if inplace else df.copy()
    returns = out[returns_col].astype(float)
    volatility = out[vol_col].astype(float)
    for window in windows:
        out[f"{returns_col}_norm_mom_{window}"] = compute_vol_normalized_momentum(
            returns,
            volatility,
            window=window,
            eps=eps,
        )
    return out


def compute_vol_normalized_momentum(
    returns: pd.Series,
    volatility: pd.Series,
    window: int,
    eps: float = 1e-8,
) -> pd.Series:
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas Series")
    if not isinstance(volatility, pd.Series):
        raise TypeError("volatility must be a pandas Series")
    raw_mom = returns.rolling(window=window).sum()
    norm_mom = raw_mom / (volatility + eps)
    norm_mom.name = f"{returns.name}_norm_mom_{window}"
    return norm_mom

__all__ = ["compute_vol_normalized_momentum", "add_vol_normalized_momentum_features"]
