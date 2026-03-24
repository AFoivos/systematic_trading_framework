from __future__ import annotations

import pandas as pd


def compute_roc(close: pd.Series, window: int = 10) -> pd.Series:
    roc = close / close.shift(window) - 1.0
    roc.name = f"roc_{window}"
    return roc


__all__ = ["compute_roc"]
