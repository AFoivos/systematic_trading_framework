from __future__ import annotations

import pandas as pd


def compute_return_momentum(returns: pd.Series, window: int) -> pd.Series:
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas Series")
    mom = returns.rolling(window=window).sum()
    mom.name = f"{returns.name}_mom_{window}"
    return mom


__all__ = ["compute_return_momentum"]
