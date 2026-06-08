from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd


def add_yang_zhang_volatility(
    df: pd.DataFrame,
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    window: int = 20,
    output_col: str | None = None,
) -> pd.DataFrame:
    """Add causal rolling Yang-Zhang volatility from OHLC prices.

    Overnight, open-close, and Rogers-Satchell components are estimated over
    trailing windows. The overnight return uses ``close.shift(1)`` only.
    """
    _validate_columns(df, [open_col, high_col, low_col, close_col])
    _validate_window(window)
    col = _resolve_output_col(output_col, f"yang_zhang_vol_{window}")

    out = df.copy()
    open_ = out[open_col].astype(float)
    high = out[high_col].astype(float)
    low = out[low_col].astype(float)
    close = out[close_col].astype(float)
    prev_close = close.shift(1)

    valid_overnight = (open_ > 0.0) & (prev_close > 0.0)
    overnight = pd.Series(np.nan, index=out.index, dtype="float64")
    overnight.loc[valid_overnight] = np.log(open_.loc[valid_overnight] / prev_close.loc[valid_overnight])

    valid_oc = (open_ > 0.0) & (close > 0.0)
    open_close = pd.Series(np.nan, index=out.index, dtype="float64")
    open_close.loc[valid_oc] = np.log(close.loc[valid_oc] / open_.loc[valid_oc])

    valid_rs = (open_ > 0.0) & (high > 0.0) & (low > 0.0) & (close > 0.0)
    rogers_satchell = pd.Series(np.nan, index=out.index, dtype="float64")
    rogers_satchell.loc[valid_rs] = (
        np.log(high.loc[valid_rs] / close.loc[valid_rs]) * np.log(high.loc[valid_rs] / open_.loc[valid_rs])
        + np.log(low.loc[valid_rs] / close.loc[valid_rs]) * np.log(low.loc[valid_rs] / open_.loc[valid_rs])
    )

    k = 0.34 / (1.34 + (window + 1.0) / (window - 1.0))
    overnight_var = overnight.rolling(window=window, min_periods=window).var(ddof=1)
    open_close_var = open_close.rolling(window=window, min_periods=window).var(ddof=1)
    rs_var = rogers_satchell.rolling(window=window, min_periods=window).mean()
    variance = overnight_var + k * open_close_var + (1.0 - k) * rs_var
    out[col] = np.sqrt(variance.clip(lower=0.0))
    return out


def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for Yang-Zhang volatility: {missing}")


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
    "add_yang_zhang_volatility",
]
