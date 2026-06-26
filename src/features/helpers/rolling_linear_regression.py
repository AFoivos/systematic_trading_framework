from __future__ import annotations

import numpy as np
import pandas as pd

from .common import output_column, positive_int, resolve_configured_column


def _rolling_linear_regression_values(values: np.ndarray) -> tuple[float, float, float]:
    if not bool(np.isfinite(values).all()):
        return float("nan"), float("nan"), float("nan")
    x = np.arange(values.size, dtype=float)
    x_mean = float(x.mean())
    y = values.astype(float)
    y_mean = float(y.mean())
    x_centered = x - x_mean
    y_centered = y - y_mean
    denom = float(np.dot(x_centered, x_centered))
    if denom == 0.0:
        return float("nan"), float("nan"), float("nan")
    slope = float(np.dot(x_centered, y_centered) / denom)
    intercept = y_mean - slope * x_mean
    fitted = intercept + slope * x
    ss_tot = float(np.dot(y_centered, y_centered))
    eps = np.finfo(float).eps
    if ss_tot <= eps:
        r2 = 1.0 if float(np.dot(y - fitted, y - fitted)) <= eps else float("nan")
    else:
        residuals = y - fitted
        r2 = float(np.clip(1.0 - float(np.dot(residuals, residuals)) / ss_tot, 0.0, 1.0))
    return slope, intercept, r2


def compute_rolling_linear_regression(
    series: pd.Series,
    *,
    window: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Compute trailing linear-regression slope, intercept, and R2.

    YAML declaration::

        transforms:
          rolling_linear_regression:
            params:
              window: 96

    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on the supplied Series directly.

    Parameters
    ----------
    window:
        Trailing rolling window length.
    """
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    resolved_window = positive_int(window, field="window")
    if resolved_window < 2:
        raise ValueError("window must be >= 2.")
    source = pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)

    slope = source.rolling(resolved_window, min_periods=resolved_window).apply(
        lambda values: _rolling_linear_regression_values(values)[0],
        raw=True,
    )
    intercept = source.rolling(resolved_window, min_periods=resolved_window).apply(
        lambda values: _rolling_linear_regression_values(values)[1],
        raw=True,
    )
    r2 = source.rolling(resolved_window, min_periods=resolved_window).apply(
        lambda values: _rolling_linear_regression_values(values)[2],
        raw=True,
    )
    slope.name = f"{series.name}_rolling_slope_{resolved_window}"
    intercept.name = f"{series.name}_rolling_intercept_{resolved_window}"
    r2.name = f"{series.name}_rolling_r2_{resolved_window}"
    return slope.astype("float32"), intercept.astype("float32"), r2.astype("float32")


def add_rolling_linear_regression_transform(
    df: pd.DataFrame,
    *,
    source_col: str | None = None,
    source_selector: dict[str, object] | None = None,
    window: int = 96,
    slope_col: str | None = None,
    intercept_col: str | None = None,
    r2_col: str | None = None,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``rolling_linear_regression`` feature helper transformation.

    YAML declaration::

        transforms:
          rolling_linear_regression:
            params:
              source_col: close
              window: 96
              r2_col: rolling_r2_trend_quality_96
              slope_col: rolling_r2_slope_96
              intercept_col: rolling_r2_intercept_96

    Required input columns
    ----------------------
    source_col:
        Input dataframe column configured by ``source_col``.

    Parameters
    ----------
    source_col:
        Input dataframe column used for the trailing linear regression.
    source_selector:
        Column selector used when ``source_col`` is not provided.
    window:
        Trailing rolling window length.
    slope_col:
        Output column for the fitted slope.
    intercept_col:
        Output column for the fitted intercept.
    r2_col:
        Output column for the rolling R2 value.
    inplace:
        If true, mutate the supplied dataframe; otherwise copy it first.
    """
    out = df if inplace else df.copy()
    cfg = {"source_col": source_col, "source_selector": source_selector}
    source = resolve_configured_column(
        out,
        cfg,
        col_key="source_col",
        selector_key="source_selector",
        field_prefix="rolling_linear_regression",
    )
    resolved_window = positive_int(window, field="window")
    slope, intercept, r2 = compute_rolling_linear_regression(out[source], window=resolved_window)
    out[output_column(slope_col, default=f"{source}_rolling_slope_{resolved_window}", field="slope_col")] = slope
    out[
        output_column(
            intercept_col,
            default=f"{source}_rolling_intercept_{resolved_window}",
            field="intercept_col",
        )
    ] = intercept
    out[output_column(r2_col, default=f"{source}_rolling_r2_{resolved_window}", field="r2_col")] = r2
    return out


__all__ = [
    "add_rolling_linear_regression_transform",
    "compute_rolling_linear_regression",
]
