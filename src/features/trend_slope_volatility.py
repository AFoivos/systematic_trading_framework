from __future__ import annotations

from numbers import Integral, Real

import numpy as np
import pandas as pd


def add_trend_slope_volatility(
    df: pd.DataFrame,
    price_col: str = "close",
    volatility_col: str | None = None,
    window: int = 96,
    annualize: bool = False,
    periods_per_year: int | None = None,
    slope_col: str | None = None,
    volatility_used_col: str | None = None,
    slope_vol_ratio_col: str | None = None,
    positive_col: str | None = None,
    rising_col: str | None = None,
    strong_trend_col: str | None = None,
    strong_threshold: float = 1.0,
) -> pd.DataFrame:
    """
    Apply the registered ``trend_slope_volatility`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: trend_slope_volatility
            params:
              price_col: close
              volatility_col: null
              window: 96
              annualize: false
              periods_per_year: null
              slope_col: null
              volatility_used_col: null
              slope_vol_ratio_col: null
              positive_col: null
              rising_col: null
              strong_trend_col: null
              strong_threshold: 1.0
            output_cols:
              - configured by slope_col
              - configured by volatility_used_col
              - configured by slope_vol_ratio_col
              - configured by positive_col
              - configured by rising_col
              - configured by strong_trend_col
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    volatility_col:
        Input dataframe column configured by ``volatility_col``. Default: ``null``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    volatility_col:
        Input dataframe column configured by ``volatility_col``. Default: ``null``.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``96``.
    annualize:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    periods_per_year:
        Configuration parameter accepted by this feature. Default: ``null``.
    slope_col:
        Output dataframe column configured by ``slope_col``. Default: ``null``.
    volatility_used_col:
        Output dataframe column configured by ``volatility_used_col``. Default: ``null``.
    slope_vol_ratio_col:
        Output dataframe column configured by ``slope_vol_ratio_col``. Default: ``null``.
    positive_col:
        Output dataframe column configured by ``positive_col``. Default: ``null``.
    rising_col:
        Output dataframe column configured by ``rising_col``. Default: ``null``.
    strong_trend_col:
        Output dataframe column configured by ``strong_trend_col``. Default: ``null``.
    strong_threshold:
        Numeric threshold used by this feature. Default: ``1.0``.
    """
    _validate_columns(df, [price_col], feature="trend slope volatility")
    if volatility_col is not None:
        _validate_columns(df, [volatility_col], feature="trend slope volatility")
    _validate_window(window)
    threshold = _validate_positive_float(strong_threshold, field="strong_threshold")
    annualization_periods = _validate_annualization(
        annualize=annualize,
        periods_per_year=periods_per_year,
    )

    slope_name = _resolve_output_col(slope_col, f"trend_slope_{window}", field="slope_col")
    volatility_name = _resolve_output_col(
        volatility_used_col,
        f"trend_slope_volatility_used_{window}",
        field="volatility_used_col",
    )
    ratio_name = _resolve_output_col(
        slope_vol_ratio_col,
        f"trend_slope_vol_ratio_{window}",
        field="slope_vol_ratio_col",
    )
    for field, value in (
        ("positive_col", positive_col),
        ("rising_col", rising_col),
        ("strong_trend_col", strong_trend_col),
    ):
        if value is not None:
            _resolve_output_col(value, "unused", field=field)

    out = df.copy()
    price = _clean_numeric(out[price_col])
    slope = _rolling_linear_slope(price, window=window)
    volatility = _resolve_volatility(out, price=price, volatility_col=volatility_col, window=window)

    if annualize:
        slope = slope * float(annualization_periods)
        volatility = volatility * np.sqrt(float(annualization_periods))

    ratio = slope / volatility.where(volatility.abs() > 0.0, np.nan)

    out[slope_name] = slope
    out[volatility_name] = volatility
    out[ratio_name] = ratio
    if positive_col is not None:
        out[positive_col] = (ratio.notna() & (ratio > 0.0)).astype("int8")
    if rising_col is not None:
        out[rising_col] = ((ratio > ratio.shift(1)) & ratio.notna() & ratio.shift(1).notna()).astype("int8")
    if strong_trend_col is not None:
        out[strong_trend_col] = (ratio.notna() & (ratio.abs() >= threshold)).astype("int8")
    return out


def _rolling_linear_slope(series: pd.Series, *, window: int) -> pd.Series:
    x = np.arange(window, dtype=float)
    x_centered = x - float(x.mean())
    x_ss = float(np.dot(x_centered, x_centered))

    def slope_fn(values: np.ndarray) -> float:
        if not bool(np.isfinite(values).all()):
            return float("nan")
        y = values.astype(float)
        y_centered = y - float(y.mean())
        return float(np.dot(x_centered, y_centered) / x_ss)

    return series.rolling(window=window, min_periods=window).apply(slope_fn, raw=True)


def _resolve_volatility(
    df: pd.DataFrame,
    *,
    price: pd.Series,
    volatility_col: str | None,
    window: int,
) -> pd.Series:
    if volatility_col is not None:
        return _clean_numeric(df[volatility_col])
    returns = price.pct_change().replace([np.inf, -np.inf], np.nan)
    return returns.rolling(window=window, min_periods=window).std(ddof=1)


def _clean_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)


def _validate_columns(df: pd.DataFrame, columns: list[str], *, feature: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for {feature}: {missing}")


def _validate_window(window: int) -> None:
    if isinstance(window, bool) or not isinstance(window, Integral) or int(window) < 5:
        raise ValueError("window must be an integer greater than or equal to 5.")


def _validate_positive_float(value: float, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be > 0.")
    out = float(value)
    if not np.isfinite(out) or out <= 0.0:
        raise ValueError(f"{field} must be > 0.")
    return out


def _validate_annualization(*, annualize: bool, periods_per_year: int | None) -> int | None:
    if not annualize:
        return None
    if periods_per_year is None:
        raise ValueError("periods_per_year is required when annualize=True.")
    if (
        isinstance(periods_per_year, bool)
        or not isinstance(periods_per_year, Integral)
        or int(periods_per_year) <= 0
    ):
        raise ValueError("periods_per_year must be a positive integer when annualize=True.")
    return int(periods_per_year)


def _resolve_output_col(output_col: str | None, default: str, *, field: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return output_col


__all__ = ["add_trend_slope_volatility"]
