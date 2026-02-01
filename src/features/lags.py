from __future__ import annotations

from typing import Iterable, Sequence

import pandas as pd


def add_lagged_features(
    df: pd.DataFrame,
    cols: Iterable[str],
    lags: Sequence[int] = (1, 2, 5),
    prefix: str = "lag",
) -> pd.DataFrame:
    """Add lagged versions of specified columns.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe (will not be modified).
    cols : iterable of str
        Column names to lag.
    lags : sequence of int, default (1, 2, 5)
        Lags in periods.
    prefix : str
        Prefix for new lag columns.
    """

    out = df.copy()
    for col in cols:
        if col not in out.columns:
            raise KeyError(f"Column '{col}' not found for lagging")
        for lag in lags:
            out[f"{prefix}_{col}_{lag}"] = out[col].shift(lag)
    return out

