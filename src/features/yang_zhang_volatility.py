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
    regime_window: int | None = None,
    high_vol_mult: float = 1.0,
    output_col: str | None = None,
    rolling_mean_col: str | None = None,
    ratio_col: str | None = None,
    rising_col: str | None = None,
    high_vol_regime_col: str | None = None,
) -> pd.DataFrame:
    """
    Apply the registered ``yang_zhang_volatility`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: yang_zhang_volatility
            params:
              open_col: open
              high_col: high
              low_col: low
              close_col: close
              window: 20
              regime_window: null
              high_vol_mult: 1.0
              output_col: null
              rolling_mean_col: null
              ratio_col: null
              rising_col: null
              high_vol_regime_col: null
          output_cols:
            - configured by output_col
            - configured by ratio_col
            - configured by rising_col
    
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
    rolling_mean_col:
        Input dataframe column configured by ``rolling_mean_col``. Default: ``null``.
    high_vol_regime_col:
        Input dataframe column configured by ``high_vol_regime_col``. Default: ``null``.
    
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
    regime_window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``null``.
    high_vol_mult:
        Configuration parameter accepted by this feature. Default: ``1.0``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    rolling_mean_col:
        Input dataframe column configured by ``rolling_mean_col``. Default: ``null``.
    ratio_col:
        Output dataframe column configured by ``ratio_col``. Default: ``null``.
    rising_col:
        Output dataframe column configured by ``rising_col``. Default: ``null``.
    high_vol_regime_col:
        Input dataframe column configured by ``high_vol_regime_col``. Default: ``null``.
    """
    _validate_columns(df, [open_col, high_col, low_col, close_col])
    _validate_window(window)
    if regime_window is not None:
        _validate_window(regime_window)
    _validate_positive_float(high_vol_mult, name="high_vol_mult")
    col = _resolve_output_col(output_col, f"yang_zhang_vol_{window}")
    optional_cols = [rolling_mean_col, ratio_col, rising_col, high_vol_regime_col]
    for optional_col in optional_cols:
        if optional_col is not None:
            _resolve_output_col(optional_col, "unused")
    output_cols = [col, *[optional_col for optional_col in optional_cols if optional_col is not None]]
    if len(output_cols) != len(set(output_cols)):
        raise ValueError("Yang-Zhang output columns must be unique.")

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

    needs_regime_window = any(optional_col is not None for optional_col in optional_cols)
    if needs_regime_window and regime_window is None:
        raise ValueError("regime_window is required when Yang-Zhang regime output columns are requested.")
    if regime_window is None:
        return out

    baseline = out[col].rolling(window=regime_window, min_periods=regime_window).mean()
    ratio = out[col] / baseline.replace(0.0, np.nan)
    if rolling_mean_col is not None:
        out[rolling_mean_col] = baseline
    if ratio_col is not None:
        out[ratio_col] = ratio
    if rising_col is not None:
        out[rising_col] = out[col].gt(out[col].shift(1)).fillna(False).astype("int8")
    if high_vol_regime_col is not None:
        out[high_vol_regime_col] = ratio.ge(float(high_vol_mult)).fillna(False).astype("int8")
    return out


def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for Yang-Zhang volatility: {missing}")


def _validate_window(window: int) -> None:
    if isinstance(window, bool) or not isinstance(window, Integral) or window <= 1:
        raise ValueError("window must be an integer greater than 1.")


def _validate_positive_float(value: float, *, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite positive number.")
    if float(value) <= 0.0:
        raise ValueError(f"{name} must be a finite positive number.")


def _resolve_output_col(output_col: str | None, default: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError("output_col must be a non-empty string.")
    return output_col


__all__ = [
    "add_yang_zhang_volatility",
]
