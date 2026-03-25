from __future__ import annotations

import numpy as np
import pandas as pd


def add_mfi_features(
    df: pd.DataFrame,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    volume_col: str = "volume",
    window: int = 14,
    inplace: bool = False,
) -> pd.DataFrame:
    missing = [c for c in (high_col, low_col, close_col, volume_col) if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for MFI features: {missing}")
    out = df if inplace else df.copy()
    out[f"mfi_{window}"] = compute_mfi(
        out[high_col].astype(float),
        out[low_col].astype(float),
        out[close_col].astype(float),
        out[volume_col].astype(float),
        window=window,
    )
    return out


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

__all__ = ["compute_mfi", "add_mfi_features"]
