from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from .helpers.common import positive_int, require_columns


def compute_rolling_autocorrelation(
    series: pd.Series, *, window: int, lag: int = 1,
    min_periods: int | None = None,
) -> pd.Series:
    """Compute causal rolling correlation between a series and its lag."""
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    resolved_window = positive_int(window, field="window")
    resolved_lag = positive_int(lag, field="lag")
    resolved_min = resolved_window if min_periods is None else positive_int(min_periods, field="min_periods")
    if resolved_min > resolved_window:
        raise ValueError("min_periods must be <= window.")
    source = pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
    out = source.rolling(resolved_window, min_periods=resolved_min).corr(source.shift(resolved_lag))
    out.name = series.name
    return out.astype("float32")


def add_rolling_autocorrelation(
    df: pd.DataFrame, *, source_col: str, windows: Sequence[int] = (48, 192),
    lag: int = 1, min_periods: int | None = None,
    output_template: str = "ac_{window}", inplace: bool = False,
) -> pd.DataFrame:
    """Add causal rolling autocorrelations of a configured input series.

    YAML declaration::

        features:
          - step: rolling_autocorrelation
            params:
              source_col: close_ret
              windows: [48, 192]
              lag: 1

    Required input columns
    ----------------------
    source_col:
        Return or other numeric series available at t.

    Parameters
    ----------
    windows, lag, min_periods:
        Trailing correlation settings. Only observations at or before t are
        used. Constant windows naturally produce NaN. Outputs are float32.
    """
    require_columns(df, [source_col], owner="rolling_autocorrelation")
    if isinstance(windows, (str, bytes)) or not isinstance(windows, Sequence) or not windows:
        raise ValueError("windows must be a non-empty sequence of positive integers.")
    resolved = tuple(positive_int(w, field="windows entry") for w in windows)
    if len(set(resolved)) != len(resolved):
        raise ValueError("windows must not contain duplicates.")
    if not isinstance(output_template, str) or "{window}" not in output_template:
        raise ValueError("output_template must contain '{window}'.")
    out = df if inplace else df.copy()
    for window in resolved:
        out[output_template.format(window=window)] = compute_rolling_autocorrelation(
            out[source_col], window=window, lag=lag, min_periods=min_periods)
    return out


__all__ = ["add_rolling_autocorrelation", "compute_rolling_autocorrelation"]
