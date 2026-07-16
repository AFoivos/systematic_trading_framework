from __future__ import annotations

import numpy as np
import pandas as pd


def add_impulse_12_96(
    df: pd.DataFrame,
    *,
    close_col: str = "close",
    returns_col: str = "close_ret",
    return_bars: int = 12,
    volatility_window: int = 96,
    output_col: str = "impulse_12_96",
) -> pd.DataFrame:
    """
    Add a trailing, native-observation volatility-normalized price impulse.

    The calculation deliberately uses dataframe rows rather than elapsed-clock bars.  This
    is important for assets with different sessions: a missing bar never becomes a synthetic
    observation merely to make their histories line up.

    YAML declaration::

        features:
          - step: impulse_12_96
            params:
              close_col: close
              returns_col: close_ret
              return_bars: 12
              volatility_window: 96
              output_col: impulse_12_96

    Required input columns
    ----------------------
    close_col:
        Price column used for the trailing return.
    returns_col:
        Return column used for the causal volatility estimate.

    Parameters
    ----------
    df:
        Time-ordered dataframe containing the configured price and return columns.
    close_col:
        Price column used to calculate the trailing simple return.
    returns_col:
        One-period return column used to estimate trailing realized volatility.
    return_bars:
        Positive native-row horizon for the trailing price return.
    volatility_window:
        Trailing native-row window for the causal volatility estimate.
    output_col:
        Name of the volatility-normalized impulse output column.
    """
    if close_col not in df.columns:
        raise KeyError(f"impulse requires close column '{close_col}'.")
    if returns_col not in df.columns:
        raise KeyError(f"impulse requires returns column '{returns_col}'.")
    if isinstance(return_bars, bool) or int(return_bars) <= 0:
        raise ValueError("return_bars must be a positive integer.")
    if isinstance(volatility_window, bool) or int(volatility_window) <= 1:
        raise ValueError("volatility_window must be an integer greater than one.")
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError("output_col must be a non-empty string.")

    out = df.copy()
    close = pd.to_numeric(out[close_col], errors="coerce").astype(float)
    close_ret = pd.to_numeric(out[returns_col], errors="coerce").astype(float)
    trailing_return = close / close.shift(int(return_bars)) - 1.0
    realized_vol = close_ret.rolling(int(volatility_window), min_periods=int(volatility_window)).std(ddof=1)
    denominator = realized_vol * np.sqrt(float(return_bars))
    impulse = trailing_return / denominator.where(denominator > 0.0)
    out[output_col] = impulse.replace([np.inf, -np.inf], np.nan).astype(float)
    return out


__all__ = ["add_impulse_12_96"]
