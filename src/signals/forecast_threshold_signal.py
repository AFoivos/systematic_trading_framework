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
    """
    Apply the registered ``forecast_threshold`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: forecast_threshold
          params:
            forecast_col: pred_ret
            signal_col: null
            upper: 0.0
            lower: null
            mode: long_short_hold
            output_cols:
              - configured by signal_col
    
    Required input columns
    ----------------------
    forecast_col:
        Input dataframe column configured by ``forecast_col``. Default: ``pred_ret``.
    
    Parameters
    ----------
    forecast_col:
        Input dataframe column configured by ``forecast_col``. Default: ``pred_ret``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``null``.
    upper:
        Configuration parameter accepted by this signal. Default: ``0.0``.
    lower:
        Configuration parameter accepted by this signal. Default: ``null``.
    mode:
        Mode selector controlling how this signal is applied. Default: ``long_short_hold``.
    """
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
