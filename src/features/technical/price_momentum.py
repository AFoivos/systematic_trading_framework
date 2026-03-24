from __future__ import annotations

import pandas as pd


def compute_price_momentum(prices: pd.Series, window: int) -> pd.Series:
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series")
    mom = prices / prices.shift(window) - 1.0
    mom.name = f"{prices.name}_mom_{window}"
    return mom


__all__ = ["compute_price_momentum"]
