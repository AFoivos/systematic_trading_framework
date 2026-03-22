from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


def add_macro_context_features(
    df: pd.DataFrame,
    *,
    columns: Sequence[str],
    availability_lag: int = 1,
    lags: Sequence[int] = (1, 24),
    pct_change_periods: Sequence[int] = (1, 24),
    zscore_window: int | None = 168,
    ema_spans: Sequence[int] = (),
    allow_missing: bool = False,
) -> pd.DataFrame:
    """
    Add reusable macro/exogenous context transforms with an explicit availability lag.

    The input columns are assumed to represent externally sourced covariates whose publication or
    ingestion timing may lag market timestamps. To avoid inadvertent lookahead, every source
    series is shifted by `availability_lag` before any derived features are computed.
    """
    if not isinstance(columns, Sequence) or isinstance(columns, (str, bytes)):
        raise TypeError("columns must be a sequence of column names.")
    if availability_lag < 0:
        raise ValueError("availability_lag must be >= 0.")

    requested_cols = [str(col) for col in columns]
    missing_cols = [col for col in requested_cols if col not in df.columns]
    if missing_cols and not allow_missing:
        raise KeyError(f"Macro columns not found in DataFrame: {missing_cols}")

    out = df.copy()
    for col in requested_cols:
        if col not in out.columns:
            continue

        base = out[col].astype(float).shift(int(availability_lag))
        out[f"{col}_avail_lag_{availability_lag}"] = base.astype("float32")

        for lag in tuple(int(v) for v in lags):
            if lag <= 0:
                raise ValueError("lags entries must be positive integers.")
            out[f"{col}_lag_{lag}"] = base.shift(lag).astype("float32")

        for period in tuple(int(v) for v in pct_change_periods):
            if period <= 0:
                raise ValueError("pct_change_periods entries must be positive integers.")
            out[f"{col}_pct_{period}"] = base.pct_change(period).astype("float32")

        if zscore_window is not None:
            if int(zscore_window) <= 1:
                raise ValueError("zscore_window must be > 1 when provided.")
            roll_mean = base.rolling(int(zscore_window), min_periods=int(zscore_window)).mean()
            roll_std = base.rolling(int(zscore_window), min_periods=int(zscore_window)).std(ddof=0)
            out[f"{col}_z_{int(zscore_window)}"] = (
                (base - roll_mean) / roll_std.replace(0.0, np.nan)
            ).astype("float32")

        for span in tuple(int(v) for v in ema_spans):
            if span <= 1:
                raise ValueError("ema_spans entries must be integers > 1.")
            ema = base.ewm(span=span, adjust=False).mean()
            out[f"{col}_ema_gap_{span}"] = (base / ema.replace(0.0, np.nan) - 1.0).astype("float32")

    return out


__all__ = ["add_macro_context_features"]
