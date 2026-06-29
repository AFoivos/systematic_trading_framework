from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd


def add_garman_klass_volatility(
    df: pd.DataFrame,
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    window: int = 20,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Apply the registered ``garman_klass_volatility`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: garman_klass_volatility
            params:
              open_col: open
              high_col: high
              low_col: low
              close_col: close
              window: 20
              output_col: null
            output_cols:
              - configured by output_col
    
    Required input columns
    ----------------------
    open_col:
        Input dataframe column configured by ``open_col``. Default: ``open``.
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    
    Parameters
    ----------
    open_col:
        Input dataframe column configured by ``open_col``. Default: ``open``.
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``20``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    """
    _validate_columns(df, [open_col, high_col, low_col, close_col])
    _validate_window(window)
    col = _resolve_output_col(output_col, f"garman_klass_vol_{window}")

    out = df.copy()
    open_ = out[open_col].astype(float)
    high = out[high_col].astype(float)
    low = out[low_col].astype(float)
    close = out[close_col].astype(float)
    valid = (open_ > 0.0) & (high > 0.0) & (low > 0.0) & (close > 0.0)

    log_hl = pd.Series(np.nan, index=out.index, dtype="float64")
    log_co = pd.Series(np.nan, index=out.index, dtype="float64")
    log_hl.loc[valid] = np.log(high.loc[valid] / low.loc[valid])
    log_co.loc[valid] = np.log(close.loc[valid] / open_.loc[valid])
    per_bar_var = 0.5 * log_hl.pow(2) - (2.0 * np.log(2.0) - 1.0) * log_co.pow(2)
    variance = per_bar_var.rolling(window=window, min_periods=window).mean()
    out[col] = np.sqrt(variance.clip(lower=0.0))
    return out


def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for Garman-Klass volatility: {missing}")


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
    "add_garman_klass_volatility",
]
