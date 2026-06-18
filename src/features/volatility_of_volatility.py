from __future__ import annotations

from numbers import Integral, Real

import numpy as np
import pandas as pd


def add_volatility_of_volatility(
    df: pd.DataFrame,
    volatility_col: str,
    window: int = 96,
    mean_window: int | None = None,
    output_col: str | None = None,
    mean_col: str | None = None,
    ratio_col: str | None = None,
    rising_col: str | None = None,
    high_vov_col: str | None = None,
    high_vov_mult: float = 1.0,
) -> pd.DataFrame:
    """
    Add causal volatility-of-volatility diagnostics.

    Volatility of volatility measures how unstable the volatility series itself
    is. High vol-of-vol points to an unstable or risky volatility regime.

    YAML declaration::

        features:
          - step: volatility_of_volatility
            params:
              volatility_col: vol_rolling_20
    """
    _validate_columns(df, [volatility_col])
    _validate_window(window, field="window")
    if mean_window is not None:
        _validate_window(mean_window, field="mean_window")
    multiplier = _validate_positive_float(high_vov_mult, field="high_vov_mult")
    _validate_mean_dependencies(mean_window=mean_window, mean_col=mean_col, ratio_col=ratio_col)

    vov_name = _resolve_output_col(
        output_col,
        f"volatility_of_volatility_{volatility_col}_{window}",
        field="output_col",
    )
    rising_name = _resolve_output_col(
        rising_col,
        f"volatility_of_volatility_{volatility_col}_{window}_rising",
        field="rising_col",
    )
    high_name = _resolve_output_col(
        high_vov_col,
        f"volatility_of_volatility_{volatility_col}_{window}_high",
        field="high_vov_col",
    )

    out = df.copy()
    volatility = _clean_numeric(out[volatility_col])
    vov = volatility.rolling(window=window, min_periods=window).std(ddof=0)
    high_baseline_window = mean_window if mean_window is not None else window
    vov_high_baseline = vov.rolling(window=high_baseline_window, min_periods=high_baseline_window).mean()

    out[vov_name] = vov
    if mean_window is not None:
        mean_name = _resolve_output_col(
            mean_col,
            f"volatility_of_volatility_{volatility_col}_{window}_mean_{mean_window}",
            field="mean_col",
        )
        ratio_name = _resolve_output_col(
            ratio_col,
            f"volatility_of_volatility_{volatility_col}_{window}_ratio_{mean_window}",
            field="ratio_col",
        )
        vov_mean = vov.rolling(window=mean_window, min_periods=mean_window).mean()
        out[mean_name] = vov_mean
        out[ratio_name] = vov / vov_mean.where(vov_mean.abs() > 0.0, np.nan)

    out[high_name] = (
        vov.notna() & vov_high_baseline.notna() & (vov > multiplier * vov_high_baseline)
    ).astype("int8")
    out[rising_name] = ((vov > vov.shift(1)) & vov.notna() & vov.shift(1).notna()).astype("int8")
    return out


def _clean_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)


def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for volatility of volatility: {missing}")


def _validate_window(window: int, *, field: str) -> None:
    if isinstance(window, bool) or not isinstance(window, Integral) or int(window) < 2:
        raise ValueError(f"{field} must be an integer greater than or equal to 2.")


def _validate_positive_float(value: float, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be > 0.")
    out = float(value)
    if not np.isfinite(out) or out <= 0.0:
        raise ValueError(f"{field} must be > 0.")
    return out


def _validate_mean_dependencies(
    *,
    mean_window: int | None,
    mean_col: str | None,
    ratio_col: str | None,
) -> None:
    if mean_window is not None:
        return
    requested = [
        field
        for field, value in (
            ("mean_col", mean_col),
            ("ratio_col", ratio_col),
        )
        if value is not None
    ]
    if requested:
        fields = ", ".join(requested)
        raise ValueError(f"mean_window is required when {fields} is provided.")


def _resolve_output_col(output_col: str | None, default: str, *, field: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return output_col


__all__ = ["add_volatility_of_volatility"]
