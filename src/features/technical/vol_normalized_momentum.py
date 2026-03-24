from __future__ import annotations

import pandas as pd


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


__all__ = ["compute_vol_normalized_momentum"]
