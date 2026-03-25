from __future__ import annotations

from typing import Optional, Sequence

import pandas as pd

from .price_momentum import compute_price_momentum
from .return_momentum import compute_return_momentum
from .vol_normalized_momentum import compute_vol_normalized_momentum


def add_momentum_features(
    df: pd.DataFrame,
    price_col: str = "close",
    returns_col: str = "close_logret",
    vol_col: Optional[str] = "vol_rolling_20",
    windows: Sequence[int] = (5, 20, 60),
    inplace: bool = False,
) -> pd.DataFrame:
    out = df if inplace else df.copy()
    missing = [c for c in (price_col, returns_col) if c not in out.columns]
    if missing:
        raise KeyError(f"Missing columns for momentum features: {missing}")

    prices = out[price_col].astype(float)
    returns = out[returns_col].astype(float)

    for window in windows:
        out[f"{price_col}_mom_{window}"] = compute_price_momentum(prices, window)
        out[f"{returns_col}_mom_{window}"] = compute_return_momentum(returns, window)
        if vol_col is not None and vol_col in out.columns:
            out[f"{returns_col}_norm_mom_{window}"] = compute_vol_normalized_momentum(
                returns,
                out[vol_col].astype(float),
                window=window,
            )

    return out


__all__ = [
    "compute_price_momentum",
    "compute_return_momentum",
    "compute_vol_normalized_momentum",
    "add_momentum_features",
]
