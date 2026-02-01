from __future__ import annotations

import pandas as pd
import numpy as np

def compute_returns(
    prices: pd.Series,
    log: bool = False,
    dropna: bool = True,
) -> pd.Series:
    """
    r_t = P_t / P_{t-1} - 1           (log=False)
    r_t = log(P_t / P_{t-1})          (log=True)

    """
    prices = prices.astype(float)
    prev = prices.shift(1)

    ratio = prices / prev

    if log:
        rets = np.log(ratio)
        rets[ratio <= 0] = np.nan
    else:
        rets = ratio - 1.0

    rets = pd.Series(rets, index=prices.index, name=prices.name)

    if dropna:
        rets = rets.dropna()

    rets.name = f"{prices.name}_{'logret' if log else 'ret'}"
    return rets

def add_close_returns(
    df: pd.DataFrame,
    log: bool = False,
    col_name: str | None = None,
) -> pd.DataFrame:
    """
    Parameters
    ----------
    df : pd.DataFrame
        OHLCV dataframe 
    log : bool
        If True -> log-returns, else returns.
    col_name : str | None
        Name of the returns column to add. If None, uses "close_logret" or "close_ret".

    Returns
    -------
    pd.DataFrame
        DataFrame with added returns column.
    """
    if "close" not in df.columns:
        raise ValueError("Expected column 'close' in df.")

    if col_name is None:
        col_name = "close_logret" if log else "close_ret"

    rets = compute_returns(df["close"], log=log, dropna=False)
    df = df.copy()
    df[col_name] = rets
    return df
