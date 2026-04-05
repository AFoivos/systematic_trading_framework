from __future__ import annotations

import numpy as np
import pandas as pd


def coerce_numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise KeyError(f"Column '{column}' is not present in the plotting frame.")
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def zscore_series(series: pd.Series) -> pd.Series:
    clean = series.replace([np.inf, -np.inf], np.nan).astype(float)
    mean = clean.mean()
    std = clean.std(ddof=0)
    if not np.isfinite(std) or std == 0.0:
        return (clean - mean).fillna(0.0)
    return ((clean - mean) / std).fillna(0.0)
