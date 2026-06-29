from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd


def add_shannon_entropy(
    df: pd.DataFrame,
    source_col: str = "close",
    window: int = 64,
    bins: int = 10,
    normalize: bool = True,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Apply the registered ``shannon_entropy`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: shannon_entropy
            params:
              source_col: close
              window: 64
              bins: 10
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
    bins:
        Configuration parameter accepted by this feature. Default: ``10``.
    normalize:
        Configuration parameter accepted by this feature. Default: ``true``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    """
    _validate_columns(df, [source_col])
    _validate_window(window, name="window")
    _validate_window(bins, name="bins")
    if bins <= 1:
        raise ValueError("bins must be greater than 1.")
    col = _resolve_output_col(output_col, f"shannon_entropy_{window}")

    out = df.copy()
    source = out[source_col].astype(float)
    out[col] = source.rolling(window=window, min_periods=window).apply(
        lambda values: _entropy(values, bins=bins, normalize=normalize),
        raw=True,
    )
    return out


def _entropy(values: np.ndarray, *, bins: int, normalize: bool) -> float:
    series = np.asarray(values, dtype=float)
    if not np.isfinite(series).all():
        return np.nan
    counts, _ = np.histogram(series, bins=bins)
    counts = counts[counts > 0]
    if counts.size == 0:
        return np.nan
    probabilities = counts / counts.sum()
    entropy = float(-np.sum(probabilities * np.log(probabilities)))
    if normalize:
        entropy /= float(np.log(bins))
    return entropy


def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for Shannon entropy: {missing}")


def _validate_window(window: int, *, name: str) -> None:
    if isinstance(window, bool) or not isinstance(window, Integral) or window <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def _resolve_output_col(output_col: str | None, default: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError("output_col must be a non-empty string.")
    return output_col


__all__ = [
    "add_shannon_entropy",
]
