from __future__ import annotations

from numbers import Real

import numpy as np
import pandas as pd

from src.features.helpers.common import positive_int


def clean_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)


def optional_min_periods(min_periods: int | None, *, window: int) -> int:
    if min_periods is None:
        return window
    resolved = positive_int(min_periods, field="min_periods")
    if resolved > window:
        raise ValueError("min_periods must be <= window.")
    return resolved


def positive_float(value: float, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a positive finite number.")
    resolved = float(value)
    if not np.isfinite(resolved) or resolved <= 0.0:
        raise ValueError(f"{field} must be a positive finite number.")
    return resolved


def finite_non_negative(value: float, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a finite number >= 0.")
    resolved = float(value)
    if not np.isfinite(resolved) or resolved < 0.0:
        raise ValueError(f"{field} must be a finite number >= 0.")
    return resolved


__all__ = [
    "clean_numeric",
    "finite_non_negative",
    "optional_min_periods",
    "positive_float",
]
