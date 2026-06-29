from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd


def add_parkinson_volatility(
    df: pd.DataFrame,
    high_col: str = "high",
    low_col: str = "low",
    window: int = 20,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Apply the registered ``parkinson_volatility`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: parkinson_volatility
            params:
              high_col: high
              low_col: low
              window: 20
              output_col: null
            output_cols:
              - configured by output_col
    
    Required input columns
    ----------------------
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    
    Parameters
    ----------
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``20``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    """
    _validate_columns(df, [high_col, low_col])
    _validate_window(window)
    col = _resolve_output_col(output_col, f"parkinson_vol_{window}")

    out = df.copy()
    high = out[high_col].astype(float)
    low = out[low_col].astype(float)
    valid = (high > 0.0) & (low > 0.0)
    log_range = pd.Series(np.nan, index=out.index, dtype="float64")
    log_range.loc[valid] = np.log(high.loc[valid] / low.loc[valid])
    variance = log_range.pow(2).rolling(window=window, min_periods=window).mean() / (4.0 * np.log(2.0))
    out[col] = np.sqrt(variance.clip(lower=0.0))
    return out


def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for Parkinson volatility: {missing}")


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
    "add_parkinson_volatility",
]
