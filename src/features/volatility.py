from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd


def compute_rolling_vol(
    returns: pd.Series,
    window: int,
    ddof: int = 1,
    annualization_factor: Optional[float] = None,
) -> pd.Series:
    """
    Rolling realized volatility on a series of returns.

    returns: monoperiodic returns (usually log-returns).
    window: size of the rolling window.
    ddof: degrees of freedom (1 για sample std).
    annualization_factor: αν δοθεί (π.χ. 252 για daily) → σ * sqrt(annualization_factor).
    """
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas Series")

    rets = returns.astype(float)
    vol = rets.rolling(window=window).std(ddof=ddof)

    if annualization_factor is not None:
        vol = vol * np.sqrt(annualization_factor)

    vol.name = f"{returns.name}_rollvol_{window}"
    return vol

def compute_ewma_vol(
    returns: pd.Series,
    span: int,
    annualization_factor: Optional[float] = None,
) -> pd.Series:
    """
    EWMA volatility (Exponentially Weighted Moving Std) 

    span: like pandas ewm(span=...).
    """
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas Series")

    rets = returns.astype(float)

    vol = rets.ewm(span=span, adjust=False).std()

    if annualization_factor is not None:
        vol = vol * np.sqrt(annualization_factor)

    vol.name = f"{returns.name}_ewmvol_{span}"
    return vol


def add_volatility_features(
    df: pd.DataFrame,
    returns_col: str = "close_logret",
    rolling_windows: Sequence[int] = (10, 20, 60),
    ewma_spans: Sequence[int] = (10, 20),
    annualization_factor: Optional[float] = 252.0,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Assumes:
    - df[returns_col] 

    Adds volatility features to DataFrame:
    - vol_rolling_{w}
    - vol_ewma_{span}
    """
    if returns_col not in df.columns:
        raise KeyError(f"returns_col '{returns_col}' not found in DataFrame")

    out = df if inplace else df.copy()
    ret_series = out[returns_col].astype(float)

    # Rolling vols
    for w in rolling_windows:
        col_name = f"vol_rolling_{w}"
        out[col_name] = compute_rolling_vol(
            ret_series,
            window=w,
            ddof=1,
            annualization_factor=annualization_factor,
        )

    # EWMA vols
    for span in ewma_spans:
        col_name = f"vol_ewma_{span}"
        out[col_name] = compute_ewma_vol(
            ret_series,
            span=span,
            annualization_factor=annualization_factor,
        )

    return out
