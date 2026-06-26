from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd

from ._dependency_fallbacks import ensure_close_based_returns


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
    Apply the registered ``volatility`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: volatility
            params:
              returns_col: close_logret
              rolling_windows: [10, 20, 60]
              ewma_spans: [10, 20]
              annualization_factor: 252.0
              inplace: false
    
    Required input columns
    ----------------------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``close_logret``.
    
    Parameters
    ----------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``close_logret``.
    rolling_windows:
        Trailing lookback or forecast horizon controlling this feature. Default: ``[10, 20, 60]``.
    ewma_spans:
        Configuration parameter accepted by this feature. Default: ``[10, 20]``.
    annualization_factor:
        Configuration parameter accepted by this feature. Default: ``252.0``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    """
    out = df if inplace else df.copy()
    out = ensure_close_based_returns(out, returns_col=returns_col)
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
