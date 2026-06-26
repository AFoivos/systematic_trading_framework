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
    add_ratios: bool = False,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``trend`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: trend
            params:
              price_col: close
              sma_windows: [20, 50, 200]
              ema_spans: [20, 50]
              sma_col_template: null
              ema_col_template: null
              add_ratios: false
              inplace: false
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    sma_windows:
        Trailing lookback or forecast horizon controlling this feature. Default: ``[20, 50, 200]``.
    ema_spans:
        Configuration parameter accepted by this feature. Default: ``[20, 50]``.
    sma_col_template:
        Configuration parameter accepted by this feature. Default: ``null``.
    ema_col_template:
        Configuration parameter accepted by this feature. Default: ``null``.
    add_ratios:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    """
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")
    if add_ratios:
        raise ValueError("add_ratios is no longer supported; use transforms.ratio helpers.")

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

    for span in ema_spans:
        ema = compute_ema(prices, span=span)
        ema_col = (
            ema_col_template.format(price_col=price_col, window=span, span=span)
            if ema_col_template is not None
            else f"{price_col}_ema_{span}"
        )
        out[ema_col] = ema

    return out


__all__ = ["compute_sma", "compute_ema", "add_trend_features", "add_trend_regime_features"]
