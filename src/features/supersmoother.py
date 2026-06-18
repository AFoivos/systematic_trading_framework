from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd


def add_supersmoother(
    df: pd.DataFrame,
    price_col: str = "close",
    period: int = 10,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Add John Ehlers' causal two-pole SuperSmoother filter.

    The filter is low lag relative to a same-period SMA and only uses current
    and prior observations.

    YAML declaration::

        features:
          - step: supersmoother
            params: {}
    """
    _validate_columns(df, [price_col])
    _validate_period(period)
    col = _resolve_output_col(output_col, f"supersmoother_{period}")

    out = df.copy()
    out[col] = _compute_supersmoother(out[price_col].astype(float).to_numpy(), period=period)
    return out


def _compute_supersmoother(values: np.ndarray, *, period: int) -> np.ndarray:
    result = np.full(values.size, np.nan, dtype=float)
    if values.size == 0:
        return result
    a1 = np.exp(-np.sqrt(2.0) * np.pi / period)
    b1 = 2.0 * a1 * np.cos(np.sqrt(2.0) * np.pi / period)
    c2 = b1
    c3 = -(a1**2)
    c1 = 1.0 - c2 - c3

    state = np.zeros(values.size, dtype=float)
    if np.isfinite(values[0]):
        state[0] = values[0]
        result[0] = state[0]
    if values.size > 1 and np.isfinite(values[:2]).all():
        state[1] = (values[0] + values[1]) / 2.0
        result[1] = state[1]
    for idx in range(2, values.size):
        sample = values[idx - 1 : idx + 1]
        if not np.isfinite(sample).all():
            continue
        state[idx] = c1 * (values[idx] + values[idx - 1]) / 2.0 + c2 * state[idx - 1] + c3 * state[idx - 2]
        result[idx] = state[idx]
    return result


def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for SuperSmoother: {missing}")


def _validate_period(period: int) -> None:
    if isinstance(period, bool) or not isinstance(period, Integral) or period <= 1:
        raise ValueError("period must be an integer greater than 1.")


def _resolve_output_col(output_col: str | None, default: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError("output_col must be a non-empty string.")
    return output_col


__all__ = [
    "add_supersmoother",
]
