from __future__ import annotations

import numpy as np
import pandas as pd

from .true_range import compute_true_range


def add_adx_features(
    df: pd.DataFrame,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    window: int = 14,
    inplace: bool = False,
) -> pd.DataFrame:
    missing = [c for c in (high_col, low_col, close_col) if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for ADX features: {missing}")
    out = df if inplace else df.copy()
    high = out[high_col].astype(float)
    low = out[low_col].astype(float)
    close = out[close_col].astype(float)
    return out.join(compute_adx(high, low, close, window=window))


def compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.DataFrame:
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    tr = compute_true_range(high, low, close)
    atr = tr.ewm(alpha=1 / window, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1 / window, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / window, adjust=False).mean() / atr)
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    adx = dx.ewm(alpha=1 / window, adjust=False).mean()

    return pd.DataFrame(
        {
            f"plus_di_{window}": plus_di,
            f"minus_di_{window}": minus_di,
            f"adx_{window}": adx,
        }
    )

__all__ = ["compute_adx", "add_adx_features"]
