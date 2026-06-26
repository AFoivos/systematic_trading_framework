from __future__ import annotations

import re
from typing import Sequence

import pandas as pd

from src.features._dependency_fallbacks import ensure_close_based_returns
from src.features.volatility import compute_rolling_vol


def _resolve_vol_feature_window(
    vol_col: str,
    *,
    vol_window: int | None,
) -> int:
    match = re.fullmatch(r"vol_rolling_(\d+)", str(vol_col).strip())
    if match:
        return int(match.group(1))
    if vol_window is not None:
        return int(vol_window)
    return 20


def _ensure_volatility_input(
    df: pd.DataFrame,
    *,
    returns_col: str,
    vol_col: str,
    vol_window: int | None,
) -> pd.DataFrame:
    out = ensure_close_based_returns(df, returns_col=returns_col)
    if vol_col in out.columns:
        return out

    resolved_window = _resolve_vol_feature_window(vol_col, vol_window=vol_window)
    # Fallback vol uses local rolling std because this step has no reliable access to
    # experiment-level annualization settings.
    out[vol_col] = compute_rolling_vol(
        out[returns_col].astype(float),
        window=resolved_window,
        ddof=1,
        annualization_factor=None,
    )
    return out


def add_vol_normalized_momentum_features(
    df: pd.DataFrame,
    returns_col: str = "close_logret",
    vol_col: str | None = "vol_rolling_20",
    vol_window: int | None = None,
    windows: Sequence[int] = (5, 20, 60),
    eps: float = 1e-8,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``vol_normalized_momentum`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: vol_normalized_momentum
            params:
              returns_col: close_logret
              vol_col: vol_rolling_20
              vol_window: null
              windows: [5, 20, 60]
              eps: 1e-08
              inplace: false
    
    Required input columns
    ----------------------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``close_logret``.
    vol_col:
        Input dataframe column configured by ``vol_col``. Default: ``vol_rolling_20``.
    
    Parameters
    ----------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``close_logret``.
    vol_col:
        Input dataframe column configured by ``vol_col``. Default: ``vol_rolling_20``.
    vol_window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``null``.
    windows:
        Trailing lookback or forecast horizon controlling this feature. Default: ``[5, 20, 60]``.
    eps:
        Configuration parameter accepted by this feature. Default: ``1e-08``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    """
    if vol_window is not None and (
        isinstance(vol_window, bool) or not isinstance(vol_window, int) or vol_window <= 0
    ):
        raise ValueError("vol_window must be a positive integer when provided.")
    resolved_vol_col = str(vol_col or f"vol_rolling_{int(vol_window or 20)}")
    out = df if inplace else df.copy()
    out = _ensure_volatility_input(
        out,
        returns_col=returns_col,
        vol_col=resolved_vol_col,
        vol_window=vol_window,
    )
    returns = out[returns_col].astype(float)
    volatility = out[resolved_vol_col].astype(float)
    for window in windows:
        out[f"{returns_col}_norm_mom_{window}"] = compute_vol_normalized_momentum(
            returns,
            volatility,
            window=window,
            eps=eps,
        )
    return out


def compute_vol_normalized_momentum(
    returns: pd.Series,
    volatility: pd.Series,
    window: int,
    eps: float = 1e-8,
) -> pd.Series:
    """
    Compute the ``compute_vol_normalized_momentum`` feature value.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: compute_vol_normalized_momentum
            params:
              volatility: <required>
              window: <required>
              eps: 1e-08
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    volatility:
        Configuration parameter accepted by this feature.
    window:
        Trailing lookback or forecast horizon controlling this feature.
    eps:
        Configuration parameter accepted by this feature. Default: ``1e-08``.
    """
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas Series")
    if not isinstance(volatility, pd.Series):
        raise TypeError("volatility must be a pandas Series")
    raw_mom = returns.rolling(window=window).sum()
    norm_mom = raw_mom / (volatility + eps)
    norm_mom.name = f"{returns.name}_norm_mom_{window}"
    return norm_mom

__all__ = [
    "compute_vol_normalized_momentum",
    "add_vol_normalized_momentum_features",
]
