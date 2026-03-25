from __future__ import annotations

import pandas as pd

from src.signals._common import resolve_signal_output_name
from src.signals.forecast_signal import compute_forecast_threshold_signal


def forecast_threshold_signal(
    df: pd.DataFrame,
    forecast_col: str = "pred_ret",
    signal_col: str | None = None,
    upper: float = 0.0,
    lower: float | None = None,
    mode: str = "long_short_hold",
) -> pd.Series:
    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_forecast",
    )
    out = compute_forecast_threshold_signal(
        df,
        forecast_col=forecast_col,
        upper=upper,
        lower=lower,
        signal_col=output_col,
        mode=mode,
    )
    return out[output_col]


__all__ = ["forecast_threshold_signal"]
