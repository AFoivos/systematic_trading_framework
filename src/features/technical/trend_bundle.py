from __future__ import annotations

from typing import Sequence

import pandas as pd

from .ema import compute_ema
from .sma import compute_sma


def add_trend_features(
    df: pd.DataFrame,
    price_col: str = "close",
    sma_windows: Sequence[int] = (20, 50, 200),
    ema_spans: Sequence[int] = (20, 50),
    inplace: bool = False,
) -> pd.DataFrame:
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")

    out = df if inplace else df.copy()
    prices = out[price_col].astype(float)

    for w in sma_windows:
        sma = compute_sma(prices, window=w)
        out[f"{price_col}_sma_{w}"] = sma
        out[f"{price_col}_over_sma_{w}"] = prices / sma - 1

    for span in ema_spans:
        ema = compute_ema(prices, span=span)
        out[f"{price_col}_ema_{span}"] = ema
        out[f"{price_col}_over_ema_{span}"] = prices / ema - 1

    return out


__all__ = ["add_trend_features"]
