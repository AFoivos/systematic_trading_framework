from __future__ import annotations

import numpy as np
import pandas as pd


def compute_volume_zscore(volume: pd.Series, window: int = 20) -> pd.Series:
    mean = volume.rolling(window=window, min_periods=window).mean()
    std = volume.rolling(window=window, min_periods=window).std(ddof=0)
    z = (volume - mean) / std.replace(0, np.nan)
    z.name = f"volume_z_{window}"
    return z


def compute_volume_over_atr(volume: pd.Series, atr: pd.Series, *, window: int) -> pd.Series:
    out = volume.astype(float) / atr.astype(float)
    out.name = f"volume_over_atr_{window}"
    return out


__all__ = ["compute_volume_over_atr", "compute_volume_zscore"]
