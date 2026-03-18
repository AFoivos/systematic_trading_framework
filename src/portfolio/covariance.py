from __future__ import annotations

from typing import Mapping

import pandas as pd


def build_rolling_covariance_by_date(
    asset_returns: pd.DataFrame,
    *,
    window: int = 60,
    min_periods: int | None = None,
    rebalance_step: int = 1,
) -> dict[pd.Timestamp, pd.DataFrame]:
    """
    Build rolling covariance by date as an explicit intermediate object used by the portfolio
    construction pipeline. Keeping this assembly step separate makes the orchestration code
    easier to reason about and test.
    """
    if not isinstance(asset_returns, pd.DataFrame):
        raise TypeError("asset_returns must be a pandas DataFrame.")
    if window <= 1:
        raise ValueError("window must be > 1.")
    if rebalance_step <= 0:
        raise ValueError("rebalance_step must be > 0.")

    min_periods = int(min_periods or max(5, min(window, 20)))
    if min_periods <= 1:
        raise ValueError("min_periods must be > 1.")

    returns = asset_returns.sort_index().astype(float)
    covariances: dict[pd.Timestamp, pd.DataFrame] = {}

    for i, ts in enumerate(returns.index):
        start = max(0, i - window + 1)
        hist = returns.iloc[start : i + 1]
        if len(hist) < min_periods:
            continue
        if (i - (min_periods - 1)) % rebalance_step != 0:
            continue
        cov = hist.cov()
        covariances[pd.Timestamp(ts)] = cov

    return covariances


__all__ = ["build_rolling_covariance_by_date"]
