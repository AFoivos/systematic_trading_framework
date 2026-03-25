from __future__ import annotations

import numpy as np
import pandas as pd


def add_volume_features(
    df: pd.DataFrame,
    volume_col: str = "volume",
    atr_col: str | None = None,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    atr_window: int = 14,
    vol_z_window: int = 20,
    inplace: bool = False,
) -> pd.DataFrame:
    if volume_col not in df.columns:
        raise KeyError(f"volume_col '{volume_col}' not found in DataFrame")

    out = df if inplace else df.copy()
    volume = out[volume_col].astype(float)
    out[f"volume_z_{vol_z_window}"] = compute_volume_zscore(volume, window=vol_z_window)

    resolved_atr_col = atr_col or f"atr_{atr_window}"
    if resolved_atr_col not in out.columns:
        missing = [c for c in (high_col, low_col, close_col) if c not in out.columns]
        if missing:
            raise KeyError(
                f"Missing columns for volume_over_atr features: {missing}; "
                f"or provide an existing atr_col='{resolved_atr_col}'."
            )
        from .atr import compute_atr

        out[resolved_atr_col] = compute_atr(
            out[high_col].astype(float),
            out[low_col].astype(float),
            out[close_col].astype(float),
            window=atr_window,
        )

    out[f"volume_over_atr_{atr_window}"] = compute_volume_over_atr(
        volume,
        out[resolved_atr_col].astype(float),
        window=atr_window,
    )
    return out


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

__all__ = ["compute_volume_over_atr", "compute_volume_zscore", "add_volume_features"]
