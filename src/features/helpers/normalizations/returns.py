from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.helpers.common import require_columns


def compute_returns(
    prices: pd.Series,
    log: bool = False,
    dropna: bool = True,
) -> pd.Series:
    """
    Compute one-bar simple or log returns from a price series.

    YAML declaration::

        normalizations:
          returns:
            params:
              close_col: close
              windows: [1]
              log_returns: true

    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on the supplied price Series directly.

    Parameters
    ----------
    prices:
        Input price series.
    log:
        If true, compute log returns; otherwise compute simple returns.
    dropna:
        If true, drop the initial missing return.
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series.")
    source = prices.astype(float)
    ratio = source / source.shift(1)
    if log:
        returns = np.log(ratio)
        returns[ratio <= 0] = np.nan
    else:
        returns = ratio - 1.0
    returns = pd.Series(returns, index=prices.index, name=prices.name)
    if dropna:
        returns = returns.dropna()
    returns.name = f"{prices.name}_{'logret' if log else 'ret'}"
    return returns


def add_close_returns(
    df: pd.DataFrame,
    log: bool = False,
    col_name: str | None = None,
) -> pd.DataFrame:
    """
    Apply the legacy-compatible ``returns`` feature transformation.

    YAML declaration::

        features:
          - step: returns
            params:
              log: true
              col_name: close_logret

    Required input columns
    ----------------------
    close:
        Input close price column.

    Parameters
    ----------
    log:
        If true, emit log returns; otherwise emit simple returns.
    col_name:
        Output column name. Defaults to ``close_logret`` or ``close_ret``.
    """
    require_columns(df, ["close"], owner="returns")
    resolved_col = col_name or ("close_logret" if log else "close_ret")
    out = df.copy()
    out[resolved_col] = compute_returns(out["close"], log=log, dropna=False)
    return out


def add_return_features(
    df: pd.DataFrame,
    *,
    close_col: str = "close",
    windows: list[int] | tuple[int, ...] = (1, 4, 8, 20, 48),
    log_returns: bool = True,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``returns`` normalization helper transformation.
    
    This normalization helper uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        normalizations:
          returns:
            params:
              close_col: close
              windows: [1, 4, 8, 20, 48]
              log_returns: true
              inplace: false
    
    Required input columns
    ----------------------
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    
    Parameters
    ----------
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    windows:
        Trailing lookback or forecast horizon controlling this normalization helper. Default: ``[1, 4, 8, 20, 48]``.
    log_returns:
        Boolean switch controlling optional normalization helper behavior. Default: ``true``.
    inplace:
        Boolean switch controlling optional normalization helper behavior. Default: ``false``.
    """
    require_columns(df, [close_col], owner="return normalization")
    out = df if inplace else df.copy()
    close = out[close_col].astype(float)

    for window in windows:
        if isinstance(window, bool) or int(window) <= 0:
            raise ValueError("Return windows must be positive integers.")
        resolved_window = int(window)
        out[f"return_{resolved_window}"] = close / close.shift(resolved_window) - 1.0
        if log_returns:
            out[f"log_return_{resolved_window}"] = np.log(close / close.shift(resolved_window))

    return out


__all__ = ["add_close_returns", "add_return_features", "compute_returns"]
