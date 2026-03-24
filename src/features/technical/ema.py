from __future__ import annotations

import pandas as pd


def compute_ema(prices: pd.Series, span: int, adjust: bool = False) -> pd.Series:
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series")
    ema = prices.ewm(span=span, adjust=adjust).mean()
    ema.name = f"{prices.name}_ema_{span}"
    return ema


__all__ = ["compute_ema"]
