from __future__ import annotations

from numbers import Integral

import pandas as pd


def add_zscore_momentum(
    df: pd.DataFrame,
    price_col: str = "close",
    window: int = 20,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Add causal rolling price z-score as a momentum feature.

    Positive values mean the current price is above its trailing rolling mean.

    YAML declaration::

        features:
          - step: zscore_momentum
            params: {}
    """
    _validate_columns(df, [price_col])
    _validate_window(window)
    col = _resolve_output_col(output_col, f"zscore_momentum_{window}")

    out = df.copy()
    price = out[price_col].astype(float)
    mean = price.rolling(window=window, min_periods=window).mean()
    std = price.rolling(window=window, min_periods=window).std(ddof=0)
    out[col] = (price - mean) / std.replace(0.0, float("nan"))
    return out


def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for z-score momentum: {missing}")


def _validate_window(window: int) -> None:
    if isinstance(window, bool) or not isinstance(window, Integral) or window <= 1:
        raise ValueError("window must be an integer greater than 1.")


def _resolve_output_col(output_col: str | None, default: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError("output_col must be a non-empty string.")
    return output_col


__all__ = [
    "add_zscore_momentum",
]
