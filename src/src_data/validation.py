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
        try:
            o = df["open"].to_numpy(dtype=float)
            h = df["high"].to_numpy(dtype=float)
            l = df["low"].to_numpy(dtype=float)
            c = df["close"].to_numpy(dtype=float)
        except (TypeError, ValueError):
            problems.append("Open/high/low/close must be numeric.")
        else:
            prices = np.column_stack((o, h, l, c))
            if not np.isfinite(prices).all():
                problems.append("Found non-finite values in open/high/low/close.")
            if np.any(prices <= 0.0):
                problems.append("Found non-positive values in open/high/low/close.")

            finite_rows = np.isfinite(prices).all(axis=1)
            if np.any(finite_rows & (l > h)):
                problems.append("Found rows with low > high.")
            if np.any(finite_rows & ((o < l) | (o > h))):
                problems.append("Found rows with open outside [low, high].")
            if np.any(finite_rows & ((c < l) | (c > h))):
                problems.append("Found rows with close outside [low, high].")

    if "volume" in df.columns:
        volume = pd.to_numeric(df["volume"], errors="coerce")
        if not allow_missing_volume and volume.isna().any():
            problems.append("Found missing or non-numeric volume while allow_missing_volume=False.")
        finite_volume = volume.dropna().to_numpy(dtype=float)
        if not np.isfinite(finite_volume).all():
            problems.append("Found non-finite volume.")
        if np.any(finite_volume < 0.0):
            problems.append("Found negative volume.")

    if problems:
        msg = "OHLCV validation failed:\n- " + "\n- ".join(problems)
        raise ValueError(msg)
