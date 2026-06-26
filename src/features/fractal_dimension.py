from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd


def add_fractal_dimension(
    df: pd.DataFrame,
    price_col: str = "close",
    window: int = 128,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Apply the registered ``fractal_dimension`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: fractal_dimension
            params:
              price_col: close
              window: 128
              output_col: null
          output_cols:
            - configured by output_col
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``128``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    """
    _validate_columns(df, [price_col])
    _validate_window(window)
    col = _resolve_output_col(output_col, f"fractal_dimension_{window}")

    out = df.copy()
    prices = out[price_col].astype(float)
    out[col] = prices.rolling(window=window, min_periods=window).apply(_katz_fractal_dimension, raw=True)
    return out


def _katz_fractal_dimension(values: np.ndarray) -> float:
    series = np.asarray(values, dtype=float)
    if not np.isfinite(series).all():
        return np.nan
    if series.size < 2:
        return np.nan

    distances = np.sqrt(1.0 + np.diff(series) ** 2)
    path_length = float(np.sum(distances))
    if path_length == 0.0:
        return 1.0

    offsets = np.arange(series.size, dtype=float)
    radius = float(np.max(np.sqrt((offsets - offsets[0]) ** 2 + (series - series[0]) ** 2)))
    if radius == 0.0:
        return 1.0

    n = float(series.size)
    denominator = np.log10(n) + np.log10(radius / path_length)
    if denominator <= 0.0 or not np.isfinite(denominator):
        return np.nan
    return float(np.log10(n) / denominator)


def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for fractal dimension: {missing}")


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
    "add_fractal_dimension",
]
