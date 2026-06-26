from __future__ import annotations

from typing import Sequence

import pandas as pd

from src.features._dependency_fallbacks import ensure_close_based_returns


def add_return_momentum_features(
    df: pd.DataFrame,
    returns_col: str = "close_logret",
    windows: Sequence[int] = (5, 20, 60),
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``return_momentum`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: return_momentum
            params:
              returns_col: close_logret
              windows: [5, 20, 60]
              inplace: false
    
    Required input columns
    ----------------------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``close_logret``.
    
    Parameters
    ----------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``close_logret``.
    windows:
        Trailing lookback or forecast horizon controlling this feature. Default: ``[5, 20, 60]``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    """
    out = df if inplace else df.copy()
    out = ensure_close_based_returns(out, returns_col=returns_col)
    returns = out[returns_col].astype(float)
    for window in windows:
        out[f"{returns_col}_mom_{window}"] = compute_return_momentum(returns, window)
    return out


def compute_return_momentum(returns: pd.Series, window: int) -> pd.Series:
    """
    Compute the ``compute_return_momentum`` feature value.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: compute_return_momentum
            params:
              window: <required>
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    window:
        Trailing lookback or forecast horizon controlling this feature.
    """
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas Series")
    mom = returns.rolling(window=window).sum()
    mom.name = f"{returns.name}_mom_{window}"
    return mom

__all__ = ["compute_return_momentum", "add_return_momentum_features"]
