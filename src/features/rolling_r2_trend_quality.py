from __future__ import annotations

from numbers import Integral, Real

import numpy as np
import pandas as pd


def add_rolling_r2_trend_quality(
    df: pd.DataFrame,
    price_col: str = "close",
    window: int = 96,
    output_col: str | None = None,
    slope_col: str | None = None,
    intercept_col: str | None = None,
    rising_col: str | None = None,
    trend_quality_col: str | None = None,
    trend_quality_threshold: float = 0.60,
) -> pd.DataFrame:
    """
    Add causal rolling linear-trend quality diagnostics.

    Each trailing window fits ``price = a + b * t`` without sklearn. R^2 close
    to 1 means the path is well explained by a clean linear trend; R^2 close to
    0 means the path is noisy or choppy relative to a straight-line trend.

    YAML declaration::

        features:
          - step: rolling_r2_trend_quality
            params:
              price_col: close
              window: 96
              output_col: rolling_r2_trend_quality_96
              slope_col: rolling_r2_slope_96
              intercept_col: rolling_r2_intercept_96
              rising_col: rolling_r2_trend_quality_96_rising
              trend_quality_col: rolling_r2_trend_quality_96_ok
              trend_quality_threshold: 0.60
            output_cols:
              - rolling_r2_trend_quality_96
              - rolling_r2_slope_96
              - rolling_r2_intercept_96
              - rolling_r2_trend_quality_96_rising
              - rolling_r2_trend_quality_96_ok

    Parameters
    ----------
    price_col:
        Input price column used for the rolling linear regression.
    window:
        Trailing rolling window length used to fit the linear trend.
    output_col:
        Output column for the rolling R^2 trend-quality value.
    slope_col:
        Output column for the fitted rolling linear-regression slope.
    intercept_col:
        Output column for the fitted rolling linear-regression intercept.
    rising_col:
        Output binary column that is 1 when rolling R^2 is rising versus
        the previous bar, otherwise 0.
    trend_quality_col:
        Output binary column that is 1 when rolling R^2 is greater than or
        equal to trend_quality_threshold, otherwise 0.
    trend_quality_threshold:
        Minimum R^2 value required to mark the trend-quality column as 1.
    """

    _validate_columns(df, [price_col])
    _validate_window(window)
    threshold = _validate_probability(trend_quality_threshold, field="trend_quality_threshold")
    r2_name = _resolve_output_col(output_col, f"rolling_r2_trend_quality_{window}", field="output_col")
    slope_name = _resolve_output_col(slope_col, f"rolling_r2_slope_{window}", field="slope_col")
    intercept_name = _resolve_output_col(
        intercept_col,
        f"rolling_r2_intercept_{window}",
        field="intercept_col",
    )
    rising_name = _resolve_output_col(
        rising_col,
        f"rolling_r2_trend_quality_{window}_rising",
        field="rising_col",
    )
    quality_name = _resolve_output_col(
        trend_quality_col,
        f"rolling_r2_trend_quality_{window}_ok",
        field="trend_quality_col",
    )

    out = df.copy()
    price = _clean_numeric(out[price_col])
    slope, intercept, r2 = _rolling_linear_regression(price, window=window)

    out[r2_name] = r2
    out[slope_name] = slope
    out[intercept_name] = intercept
    out[rising_name] = ((r2 > r2.shift(1)) & r2.notna() & r2.shift(1).notna()).astype("int8")
    out[quality_name] = (r2.notna() & (r2 >= threshold)).astype("int8")
    return out


def _rolling_linear_regression(series: pd.Series, *, window: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    x = np.arange(window, dtype=float)
    x_mean = float(x.mean())
    x_centered = x - x_mean
    x_ss = float(np.dot(x_centered, x_centered))

    def slope_fn(values: np.ndarray) -> float:
        if not bool(np.isfinite(values).all()):
            return float("nan")
        y = values.astype(float)
        y_centered = y - float(y.mean())
        return float(np.dot(x_centered, y_centered) / x_ss)

    def intercept_fn(values: np.ndarray) -> float:
        if not bool(np.isfinite(values).all()):
            return float("nan")
        y = values.astype(float)
        slope = slope_fn(y)
        if not np.isfinite(slope):
            return float("nan")
        return float(y.mean() - slope * x_mean)

    def r2_fn(values: np.ndarray) -> float:
        if not bool(np.isfinite(values).all()):
            return float("nan")
        y = values.astype(float)
        y_mean = float(y.mean())
        y_centered = y - y_mean
        ss_tot = float(np.dot(y_centered, y_centered))
        slope = float(np.dot(x_centered, y_centered) / x_ss)
        intercept = y_mean - slope * x_mean
        residual = y - (intercept + slope * x)
        ss_res = float(np.dot(residual, residual))
        eps = np.finfo(float).eps
        if ss_tot <= eps:
            return 1.0 if ss_res <= eps else float("nan")
        return float(np.clip(1.0 - ss_res / ss_tot, 0.0, 1.0))

    rolling = series.rolling(window=window, min_periods=window)
    slope = rolling.apply(slope_fn, raw=True)
    intercept = rolling.apply(intercept_fn, raw=True)
    r2 = rolling.apply(r2_fn, raw=True)
    return slope, intercept, r2


def _clean_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)


def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for rolling R2 trend quality: {missing}")


def _validate_window(window: int) -> None:
    if isinstance(window, bool) or not isinstance(window, Integral) or int(window) < 5:
        raise ValueError("window must be an integer greater than or equal to 5.")


def _validate_probability(value: float, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a float between 0 and 1.")
    out = float(value)
    if not np.isfinite(out) or not 0.0 <= out <= 1.0:
        raise ValueError(f"{field} must be a float between 0 and 1.")
    return out


def _resolve_output_col(output_col: str | None, default: str, *, field: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return output_col


__all__ = ["add_rolling_r2_trend_quality"]
