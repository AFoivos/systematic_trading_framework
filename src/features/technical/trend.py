from __future__ import annotations

from typing import Sequence

import pandas as pd

from .ema import compute_ema
from .sma import compute_sma
from .trend_regime_feature import add_trend_regime_features


def add_trend_features(
    df: pd.DataFrame,
    price_col: str = "close",
    sma_windows: Sequence[int] = (20, 50, 200),
    ema_spans: Sequence[int] = (20, 50),
    sma_col_template: str | None = None,
    ema_col_template: str | None = None,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``trend`` feature transformation.
    
    YAML declaration::
    
        features:
          - step: trend
            params: {}
    
    Required input columns
    ----------------------
    price_col:
        Input column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column name consumed by the component. Default: ``close``.
    sma_windows:
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``(20, 50, 200)``.
    ema_spans:
        Configuration value used by the registered component. Default: ``(20, 50)``.
    sma_col_template:
        Configuration value used by the registered component. Default: ``None``.
    ema_col_template:
        Configuration value used by the registered component. Default: ``None``.
    inplace:
        Configuration value used by the registered component. Default: ``False``.
    """
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")

    out = df if inplace else df.copy()
    prices = out[price_col].astype(float)

    for window in sma_windows:
        sma = compute_sma(prices, window=window)
        sma_col = (
            sma_col_template.format(price_col=price_col, window=window, span=window)
            if sma_col_template is not None
            else f"{price_col}_sma_{window}"
        )
        out[sma_col] = sma
        out[f"{price_col}_over_sma_{window}"] = prices / sma - 1

    for span in ema_spans:
        ema = compute_ema(prices, span=span)
        ema_col = (
            ema_col_template.format(price_col=price_col, window=span, span=span)
            if ema_col_template is not None
            else f"{price_col}_ema_{span}"
        )
        out[ema_col] = ema
        out[f"{price_col}_over_ema_{span}"] = prices / ema - 1

    return out


__all__ = ["compute_sma", "compute_ema", "add_trend_features", "add_trend_regime_features"]
