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
    Apply the registered ``zscore_momentum`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: zscore_momentum
            params:
              price_col: close
              window: 20
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
        Trailing lookback or forecast horizon controlling this feature. Default: ``20``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
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
