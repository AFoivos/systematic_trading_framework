from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd

from src.features.technical.adx import compute_adx


def add_adx_rms(
    df: pd.DataFrame,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    adx_col: str | None = None,
    adx_window: int = 14,
    window: int = 14,
    output_col: str | None = None,
) -> pd.DataFrame:
    """Add a trailing RMS transform of ADX.

    If ``adx_col`` or ``adx_<adx_window>`` already exists it is reused. Otherwise
    ADX is computed causally from OHLC data without adding intermediate columns.
    """
    _validate_window(adx_window, name="adx_window")
    _validate_window(window, name="window")
    source_col = adx_col or f"adx_{adx_window}"
    if source_col in df.columns:
        _validate_columns(df, [source_col], feature="ADX RMS")
        adx = df[source_col].astype(float)
    else:
        _validate_columns(df, [high_col, low_col, close_col], feature="ADX RMS")
        adx = compute_adx(
            df[high_col].astype(float),
            df[low_col].astype(float),
            df[close_col].astype(float),
            window=adx_window,
        )[f"adx_{adx_window}"]

    col = _resolve_output_col(output_col, f"adx_rms_{window}")
    out = df.copy()
    out[col] = np.sqrt(adx.pow(2).rolling(window=window, min_periods=window).mean())
    return out


def _validate_columns(df: pd.DataFrame, columns: list[str], *, feature: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for {feature}: {missing}")


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
    "add_adx_rms",
]
