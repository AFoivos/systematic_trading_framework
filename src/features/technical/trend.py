from __future__ import annotations

from typing import Optional, Sequence

import pandas as pd
import numpy as np


def compute_sma(
    prices: pd.Series,
    window: int,
    min_periods: Optional[int] = None,
) -> pd.Series:
    """
    Simple Moving Average (SMA) .

    Parameters
    ----------
    prices : pd.Series
        Serries prices (π.χ. close).
    window : int
        window size (σε points, π.χ. 20 για 20 ημέρες).
    min_periods : int, optional
        Minimum number of observations in window required to have a value.
        if None, uses window.

    Returns
    -------
    sma : pd.Series
        Σειρά με SMA, ίδια index με τις τιμές.
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series")

    if min_periods is None:
        min_periods = window

    sma = prices.rolling(window=window, min_periods=min_periods).mean()
    sma.name = f"{prices.name}_sma_{window}"
    return sma

def compute_ema(
    prices: pd.Series,
    span: int,
    adjust: bool = False,
) -> pd.Series:
    """
    Exponential Moving Average (EMA) .

    Parameters
    ----------
    prices : pd.Series
        Serries prices (π.χ. close).
    span : int
        Span parameter forEMA (όπως στο pandas ewm).
    adjust : bool, default False
        Αν False, η EMA είναι πιο κοντά στο κλασικό recursive EMA.

    Returns
    -------
    ema : pd.Series
        Σειρά με EMA, ίδια index με τις τιμές.
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series")

    ema = prices.ewm(span=span, adjust=adjust).mean()
    ema.name = f"{prices.name}_ema_{span}"
    return ema


def add_trend_features(
    df: pd.DataFrame,
    price_col: str = "close",
    sma_windows: Sequence[int] = (20, 50, 200),
    ema_spans: Sequence[int] = (20, 50),
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Προσθέτει βασικά trend features σε OHLCV DataFrame.

    Features που προστίθενται:
    - close_sma_{w}
    - close_ema_{span}
    - close_over_sma_{w}  = close / SMA_w - 1
    - close_over_ema_{span} = close / EMA_span - 1

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame με τουλάχιστον price_col.
    price_col : str, default "close"
        Όνομα στήλης τιμής.
    sma_windows : sequence of int
        Παράθυρα για SMA.
    ema_spans : sequence of int
        Spans για EMA.
    inplace : bool, default False
        Αν True, τροποποιεί το df in-place.

    Returns
    -------
    out : pd.DataFrame
        DataFrame με trend features.
    """
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")

    out = df if inplace else df.copy()
    prices = out[price_col].astype(float)

    for w in sma_windows:
        sma = compute_sma(prices, window=w)
        sma_col = f"{price_col}_sma_{w}"
        rel_col = f"{price_col}_over_sma_{w}"

        out[sma_col] = sma
        out[rel_col] = prices / sma - 1

    for span in ema_spans:
        ema = compute_ema(prices, span=span)
        ema_col = f"{price_col}_ema_{span}"
        rel_col = f"{price_col}_over_ema_{span}"

        out[ema_col] = ema
        out[rel_col] = prices / ema - 1

    return out

def add_trend_regime_features(
    df: pd.DataFrame,
    price_col: str = "close",
    base_sma_for_sign: int = 50,
    short_sma: int = 20,
    long_sma: int = 50,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    trend "regime" features based on MAs.

    Features:
    - {price_col}_trend_regime_sma_{base_sma_for_sign}  ∈ {-1, 0, 1}
      sign(close_over_sma_{base_sma_for_sign})
    - {price_col}_trend_state_sma_{short_sma}_{long_sma} ∈ {-1, 0, 1}
      1  → short_sma πάνω από long_sma (bull)
      -1 → short_sma κάτω από long_sma (bear)
      0  → neutral / NaN

    Assumes:
    - add_trend_features() has been run with sma_windows including:
      - {price_col}_over_sma_{base_sma_for_sign}
      - {price_col}_sma_{short_sma}, {price_col}_sma_{long_sma}
    """
    out = df if inplace else df.copy()

    over_col = f"{price_col}_over_sma_{base_sma_for_sign}"
    if over_col not in out.columns:
        raise KeyError(
            f"Required column '{over_col}' not found. "
            "Run add_trend_features() first with appropriate sma_windows."
        )

    regime_col = f"{price_col}_trend_regime_sma_{base_sma_for_sign}"
    regime = np.sign(out[over_col].astype(float))
    regime = regime.where(~out[over_col].isna(), other=np.nan)
    out[regime_col] = regime.astype("float32")

    short_col = f"{price_col}_sma_{short_sma}"
    long_col = f"{price_col}_sma_{long_sma}"

    missing = [c for c in (short_col, long_col) if c not in out.columns]
    if missing:
        raise KeyError(
            f"Missing SMA columns {missing}. "
            "Run add_trend_features() with matching sma_windows."
        )

    state_col = f"{price_col}_trend_state_sma_{short_sma}_{long_sma}"
    state = pd.Series(index=out.index, dtype="float32")

    short = out[short_col].astype(float)
    long_ = out[long_col].astype(float)

    state[short > long_] = 1.0   
    state[short < long_] = -1.0  
    state[(short.isna()) | (long_.isna())] = 0.0  

    out[state_col] = state

    return out
