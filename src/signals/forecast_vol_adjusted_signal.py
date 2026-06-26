from __future__ import annotations

import pandas as pd

from src.signals._common import resolve_signal_output_name
from src.signals.forecast_signal import compute_forecast_vol_adjusted_signal


def forecast_vol_adjusted_signal(
    df: pd.DataFrame,
    forecast_col: str = "pred_ret",
    vol_col: str = "pred_vol",
    signal_col: str | None = None,
    clip: float = 1.0,
    vol_floor: float = 1e-6,
) -> pd.Series:
    """
    Apply the registered ``forecast_vol_adjusted`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: forecast_vol_adjusted
          params:
            forecast_col: pred_ret
            vol_col: pred_vol
            signal_col: null
            clip: 1.0
            vol_floor: 1e-06
          output_cols:
            - configured by signal_col
    
    Required input columns
    ----------------------
    forecast_col:
        Input dataframe column configured by ``forecast_col``. Default: ``pred_ret``.
    vol_col:
        Input dataframe column configured by ``vol_col``. Default: ``pred_vol``.
    
    Parameters
    ----------
    forecast_col:
        Input dataframe column configured by ``forecast_col``. Default: ``pred_ret``.
    vol_col:
        Input dataframe column configured by ``vol_col``. Default: ``pred_vol``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``null``.
    clip:
        Configuration parameter accepted by this signal. Default: ``1.0``.
    vol_floor:
        Configuration parameter accepted by this signal. Default: ``1e-06``.
    """
    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_forecast_vol_adj",
    )
    out = compute_forecast_vol_adjusted_signal(
        df,
        forecast_col=forecast_col,
        vol_col=vol_col,
        signal_col=output_col,
        clip=clip,
        vol_floor=vol_floor,
    )
    return out[output_col]


__all__ = ["forecast_vol_adjusted_signal"]
