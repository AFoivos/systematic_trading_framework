from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd


def add_hurst_exponent(
    df: pd.DataFrame,
    price_col: str = "close",
    window: int = 128,
    min_lag: int = 2,
    max_lag: int | None = None,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Apply the registered ``hurst_exponent`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: hurst_exponent
            params:
              price_col: close
              window: 128
              min_lag: 2
              max_lag: null
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
    min_lag:
        Configuration parameter accepted by this feature. Default: ``2``.
    max_lag:
        Configuration parameter accepted by this feature. Default: ``null``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    """
    _validate_columns(df, [price_col])
    _validate_window(window, name="window")
    _validate_window(min_lag, name="min_lag")
    if max_lag is not None:
        _validate_window(max_lag, name="max_lag")
        if max_lag >= window:
            raise ValueError("max_lag must be smaller than window.")
    if min_lag >= window:
        raise ValueError("min_lag must be smaller than window.")

    col = _resolve_output_col(output_col, f"hurst_{window}")
    resolved_max_lag = int(max_lag) if max_lag is not None else max(min(window // 2, 20), min_lag + 1)
    if resolved_max_lag <= min_lag:
        raise ValueError("window must allow at least two lag values.")

    out = df.copy()
    prices = out[price_col].astype(float)
    lags = np.arange(int(min_lag), resolved_max_lag + 1, dtype=int)
    out[col] = prices.rolling(window=window, min_periods=window).apply(
        lambda values: _estimate_hurst(values, lags),
        raw=True,
    )
    return out


def _estimate_hurst(values: np.ndarray, lags: np.ndarray) -> float:
    series = np.asarray(values, dtype=float)
    if not np.isfinite(series).all():
        return np.nan

    log_lags: list[float] = []
    log_tau: list[float] = []
    for lag in lags:
        diffs = series[lag:] - series[:-lag]
        tau = float(np.std(diffs, ddof=1)) if diffs.size > 1 else np.nan
        if np.isfinite(tau) and tau > 0.0:
            log_lags.append(float(np.log(lag)))
            log_tau.append(float(np.log(tau)))

    if len(log_lags) < 3:
        return np.nan
    slope = float(np.polyfit(np.asarray(log_lags), np.asarray(log_tau), 1)[0])
    if not np.isfinite(slope):
        return np.nan
    return float(np.clip(slope, 0.0, 1.0))


def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for Hurst exponent: {missing}")


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
    "add_hurst_exponent",
]
