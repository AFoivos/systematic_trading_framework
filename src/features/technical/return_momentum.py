from __future__ import annotations

from typing import Sequence

import pandas as pd

from src.features._dependency_fallbacks import ensure_close_based_returns


def add_return_momentum_features(
    df: pd.DataFrame,
    returns_col: str = "close_logret",
    windows: Sequence[int] = (5, 20, 60),
    inplace: bool = False,
) -> pd.DataFrame:
    out = df if inplace else df.copy()
    out = ensure_close_based_returns(out, returns_col=returns_col)
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
