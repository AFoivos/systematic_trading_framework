from __future__ import annotations

import numpy as np
import pandas as pd


def compute_mfi(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    window: int = 14,
) -> pd.Series:
    typical_price = (high + low + close) / 3.0
    raw_flow = typical_price * volume
    pos_flow = raw_flow.where(typical_price.diff() > 0, 0.0)
    neg_flow = raw_flow.where(typical_price.diff() < 0, 0.0)

    pos_sum = pos_flow.rolling(window=window, min_periods=window).sum()
    neg_sum = neg_flow.rolling(window=window, min_periods=window).sum()
    mfr = pos_sum / neg_sum.replace(0, np.nan)
    mfi = 100 - (100 / (1 + mfr))
    mfi = mfi.where(~((neg_sum == 0.0) & (pos_sum > 0.0)), other=100.0)
    mfi = mfi.where(~((pos_sum == 0.0) & (neg_sum > 0.0)), other=0.0)
    mfi.name = f"mfi_{window}"
    return mfi


__all__ = ["compute_mfi"]
