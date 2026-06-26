from __future__ import annotations

from math import factorial
from numbers import Integral

import numpy as np
import pandas as pd


def add_permutation_entropy(
    df: pd.DataFrame,
    source_col: str = "close",
    window: int = 64,
    order: int = 3,
    delay: int = 1,
    normalize: bool = True,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Apply the registered ``permutation_entropy`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: permutation_entropy
            params:
              source_col: close
              window: 64
              order: 3
              delay: 1
              normalize: true
              output_col: null
          output_cols:
            - configured by output_col
    
    Required input columns
    ----------------------
    source_col:
        Input dataframe column configured by ``source_col``. Default: ``close``.
    
    Parameters
    ----------
    source_col:
        Input dataframe column configured by ``source_col``. Default: ``close``.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``64``.
    order:
        Configuration parameter accepted by this feature. Default: ``3``.
    delay:
        Configuration parameter accepted by this feature. Default: ``1``.
    normalize:
        Configuration parameter accepted by this feature. Default: ``true``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    """
    _validate_columns(df, [source_col])
    _validate_positive_int(window, name="window")
    _validate_positive_int(order, name="order")
    _validate_positive_int(delay, name="delay")
    if order < 2:
        raise ValueError("order must be at least 2.")
    min_required = delay * (order - 1) + 1
    if window < min_required:
        raise ValueError("window must be at least delay * (order - 1) + 1.")
    col = _resolve_output_col(output_col, f"permutation_entropy_{window}")

    out = df.copy()
    source = out[source_col].astype(float)
    out[col] = source.rolling(window=window, min_periods=window).apply(
        lambda values: _permutation_entropy(values, order=order, delay=delay, normalize=normalize),
        raw=True,
    )
    return out


def _permutation_entropy(values: np.ndarray, *, order: int, delay: int, normalize: bool) -> float:
    series = np.asarray(values, dtype=float)
    if not np.isfinite(series).all():
        return np.nan
    pattern_count = series.size - delay * (order - 1)
    if pattern_count <= 0:
        return np.nan

    counts: dict[tuple[int, ...], int] = {}
    offsets = delay * np.arange(order)
    for start in range(pattern_count):
        pattern = tuple(np.argsort(series[start + offsets], kind="stable").tolist())
        counts[pattern] = counts.get(pattern, 0) + 1

    probabilities = np.asarray(list(counts.values()), dtype=float)
    probabilities /= probabilities.sum()
    entropy = float(-np.sum(probabilities * np.log(probabilities)))
    if normalize:
        entropy /= float(np.log(factorial(order)))
    return entropy


def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for permutation entropy: {missing}")


def _validate_positive_int(value: int, *, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Integral) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def _resolve_output_col(output_col: str | None, default: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError("output_col must be a non-empty string.")
    return output_col


__all__ = [
    "add_permutation_entropy",
]
