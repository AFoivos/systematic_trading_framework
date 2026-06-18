from __future__ import annotations

from numbers import Integral

import pandas as pd


def add_rate_of_change(
    df: pd.DataFrame,
    price_col: str = "close",
    window: int = 10,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Add causal rate of change, ``price / price.shift(window) - 1``.

    YAML declaration::

        features:
          - step: rate_of_change
            params: {}
    """
    _validate_columns(df, [price_col])
    _validate_window(window)
    col = _resolve_output_col(output_col, f"roc_{window}")

    out = df.copy()
    price = out[price_col].astype(float)
    out[col] = price / price.shift(window) - 1.0
    return out


def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for rate of change: {missing}")


def _validate_window(window: int) -> None:
    if isinstance(window, bool) or not isinstance(window, Integral) or window <= 0:
        raise ValueError("window must be a positive integer.")


def _resolve_output_col(output_col: str | None, default: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError("output_col must be a non-empty string.")
    return output_col


__all__ = [
    "add_rate_of_change",
]
