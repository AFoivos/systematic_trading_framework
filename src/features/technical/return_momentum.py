from __future__ import annotations

from typing import Sequence

import pandas as pd


def add_return_momentum_features(
    df: pd.DataFrame,
    returns_col: str = "close_logret",
    windows: Sequence[int] = (5, 20, 60),
    inplace: bool = False,
) -> pd.DataFrame:
    if returns_col not in df.columns:
        raise KeyError(f"returns_col '{returns_col}' not found in DataFrame")
    out = df if inplace else df.copy()
    returns = out[returns_col].astype(float)
    for window in windows:
        out[f"{returns_col}_mom_{window}"] = compute_return_momentum(returns, window)
    return out


def compute_return_momentum(returns: pd.Series, window: int) -> pd.Series:
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas Series")
    mom = returns.rolling(window=window).sum()
    mom.name = f"{returns.name}_mom_{window}"
    return mom

__all__ = ["compute_return_momentum", "add_return_momentum_features"]
