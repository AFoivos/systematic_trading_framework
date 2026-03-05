from __future__ import annotations

import numpy as np
import pandas as pd


_ALLOWED_MODES = {"long_only", "short_only", "long_short", "long_short_hold"}


def compute_forecast_threshold_signal(
    df: pd.DataFrame,
    forecast_col: str = "pred_ret",
    *,
    upper: float = 0.0,
    lower: float | None = None,
    signal_col: str = "forecast_threshold_signal",
    mode: str = "long_short_hold",
) -> pd.DataFrame:
    """
    Convert return forecasts into thresholded directional exposure.
    """
    if forecast_col not in df.columns:
        raise KeyError(f"forecast_col '{forecast_col}' not found in DataFrame")
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of {_ALLOWED_MODES}")

    out = df.copy()
    series = out[forecast_col].astype(float)
    out[signal_col] = 0.0

    if lower is None:
        lower = -abs(float(upper))

    long_mask = series > float(upper)
    short_mask = series < float(lower)
    if mode == "long_short_hold":
        hold = pd.Series(np.nan, index=out.index, dtype=float)
        hold.loc[long_mask] = 1.0
        hold.loc[short_mask] = -1.0
        out[signal_col] = hold.ffill().fillna(0.0).astype(float)
        return out

    if mode in {"long_only", "long_short"}:
        out.loc[long_mask, signal_col] = 1.0
    if mode in {"short_only", "long_short"}:
        out.loc[short_mask, signal_col] = -1.0
    return out


def compute_forecast_vol_adjusted_signal(
    df: pd.DataFrame,
    forecast_col: str = "pred_ret",
    *,
    vol_col: str = "pred_vol",
    signal_col: str = "forecast_vol_adjusted_signal",
    clip: float = 1.0,
    vol_floor: float = 1e-6,
) -> pd.DataFrame:
    """
    Convert return and volatility forecasts into a continuous conviction-sized signal.
    """
    if forecast_col not in df.columns:
        raise KeyError(f"forecast_col '{forecast_col}' not found in DataFrame")
    if vol_col not in df.columns:
        raise KeyError(f"vol_col '{vol_col}' not found in DataFrame")
    if clip <= 0:
        raise ValueError("clip must be > 0.")
    if vol_floor <= 0:
        raise ValueError("vol_floor must be > 0.")

    out = df.copy()
    forecast = out[forecast_col].astype(float)
    vol = out[vol_col].astype(float).clip(lower=float(vol_floor))
    scaled = np.tanh(forecast / vol).astype(float) * float(clip)
    out[signal_col] = scaled.astype(float)
    return out


__all__ = [
    "compute_forecast_threshold_signal",
    "compute_forecast_vol_adjusted_signal",
]
