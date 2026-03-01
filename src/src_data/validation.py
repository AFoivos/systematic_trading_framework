from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def validate_ohlcv(
    df: pd.DataFrame,
    required_columns: Iterable[str] = ("open", "high", "low", "close", "volume"),
    allow_missing_volume: bool = True,
) -> None:

    """
    Validate OHLCV before downstream logic depends on it. The function raises early when
    assumptions of the data ingestion and storage layer are violated, which keeps failures
    deterministic and easier to diagnose.
    """
    problems: list[str] = []

    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        problems.append(f"Missing required columns: {missing}")

    if not isinstance(df.index, pd.DatetimeIndex):
        problems.append(f"Index is not a DatetimeIndex (got {type(df.index)})")

    if isinstance(df.index, pd.DatetimeIndex) and not df.index.is_monotonic_increasing:
        problems.append("DatetimeIndex is not monotonic increasing.")

    if df.index.has_duplicates:
        problems.append("DatetimeIndex has duplicate entries.")

    for col in ("open", "high", "low", "close"):
        if col not in df.columns:
            break
    else:
        o = df["open"].to_numpy(dtype=float)
        h = df["high"].to_numpy(dtype=float)
        l = df["low"].to_numpy(dtype=float)
        c = df["close"].to_numpy(dtype=float)

        if np.isnan(o).any() or np.isnan(h).any() or np.isnan(l).any() or np.isnan(c).any():
            problems.append("Found NaNs in open/high/low/close.")

        if np.any(l > h):
            problems.append("Found rows with low > high.")
        if np.any(o < l) or np.any(o > h):
            problems.append("Found rows with open outside [low, high].")
        if np.any(c < l) or np.any(c > h):
            problems.append("Found rows with close outside [low, high].")

    if "volume" in df.columns and not allow_missing_volume:
        if df["volume"].isna().any():
            problems.append("Found NaNs in volume while allow_missing_volume=False.")

    if problems:
        msg = "OHLCV validation failed:\n- " + "\n- ".join(problems)
        raise ValueError(msg)
