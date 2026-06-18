from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd


def add_volatility_regime(
    df: pd.DataFrame,
    vol_col: str | None = None,
    price_col: str = "close",
    returns_col: str | None = None,
    vol_window: int = 20,
    regime_window: int = 100,
    method: str = "ratio",
    lower_quantile: float = 0.33,
    upper_quantile: float = 0.67,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Add a causal volatility regime feature.

    ``method='ratio'`` emits ``vol / trailing_mean(vol)``. ``method='percentile'``
    emits ``0, 1, 2`` based on trailing rolling quantiles of the volatility
    series. If ``vol_col`` is not provided, trailing return volatility is
    computed from ``returns_col`` or ``price_col``.

    YAML declaration::

        features:
          - step: volatility_regime
            params: {}
    """
    _validate_window(vol_window, name="vol_window")
    _validate_window(regime_window, name="regime_window")
    _validate_quantiles(lower_quantile, upper_quantile)
    if method not in {"ratio", "percentile"}:
        raise ValueError("method must be one of: ratio, percentile.")
    col = _resolve_output_col(output_col, "volatility_regime")

    out = df.copy()
    if vol_col is not None:
        _validate_columns(df, [vol_col], feature="volatility regime")
        vol = out[vol_col].astype(float)
    else:
        if returns_col is not None:
            _validate_columns(df, [returns_col], feature="volatility regime")
            returns = out[returns_col].astype(float)
        else:
            _validate_columns(df, [price_col], feature="volatility regime")
            returns = out[price_col].astype(float).pct_change()
        vol = returns.rolling(window=vol_window, min_periods=vol_window).std(ddof=0)

    if method == "ratio":
        baseline = vol.rolling(window=regime_window, min_periods=regime_window).mean()
        out[col] = vol / baseline.replace(0.0, np.nan)
    else:
        lower = vol.rolling(window=regime_window, min_periods=regime_window).quantile(lower_quantile)
        upper = vol.rolling(window=regime_window, min_periods=regime_window).quantile(upper_quantile)
        regime = pd.Series(np.nan, index=out.index, dtype="float64")
        ready = lower.notna() & upper.notna() & vol.notna()
        regime.loc[ready & (vol <= lower)] = 0.0
        regime.loc[ready & (vol > lower) & (vol < upper)] = 1.0
        regime.loc[ready & (vol >= upper)] = 2.0
        out[col] = regime
    return out


def _validate_columns(df: pd.DataFrame, columns: list[str], *, feature: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for {feature}: {missing}")


def _validate_window(window: int, *, name: str) -> None:
    if isinstance(window, bool) or not isinstance(window, Integral) or window <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def _validate_quantiles(lower: float, upper: float) -> None:
    if not (0.0 < float(lower) < float(upper) < 1.0):
        raise ValueError("lower_quantile and upper_quantile must satisfy 0 < lower < upper < 1.")


def _resolve_output_col(output_col: str | None, default: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError("output_col must be a non-empty string.")
    return output_col


__all__ = [
    "add_volatility_regime",
]
