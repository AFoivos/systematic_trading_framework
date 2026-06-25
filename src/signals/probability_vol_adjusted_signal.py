from __future__ import annotations

import pandas as pd

from src.signals._common import resolve_signal_output_name
from src.signals.forecast_signal import compute_probability_vol_adjusted_signal


def probability_vol_adjusted_signal(
    df: pd.DataFrame,
    prob_col: str = "pred_prob",
    vol_col: str = "pred_vol",
    signal_col: str | None = None,
    prob_center: float = 0.5,
    upper: float | None = None,
    lower: float | None = None,
    vol_target: float | None = 0.001,
    clip: float = 1.0,
    vol_floor: float = 1e-6,
    min_signal_abs: float = 0.0,
    activation_filters: list[dict[str, object]] | None = None,
    top_quantile: float | None = None,
    top_quantile_window: int | None = None,
    max_trade_rate: float | None = None,
) -> pd.Series:
    """
    Apply the registered ``probability_vol_adjusted`` signal transformation.
    
    YAML declaration::
    
        signals:
          kind: probability_vol_adjusted
          params: {}
    
    Required input columns
    ----------------------
    prob_col:
        Input column configured by ``prob_col``. Default: ``pred_prob``.
    vol_col:
        Input column configured by ``vol_col``. Default: ``pred_vol``.
    
    Parameters
    ----------
    prob_col:
        Input dataframe column name consumed by the component. Default: ``pred_prob``.
    vol_col:
        Input dataframe column name consumed by the component. Default: ``pred_vol``.
    signal_col:
        Output column name emitted by the component. Default: ``None``.
    prob_center:
        Configuration value used by the registered component. Default: ``0.5``.
    upper:
        Configuration value used by the registered component. Default: ``None``.
    lower:
        Configuration value used by the registered component. Default: ``None``.
    vol_target:
        Configuration value used by the registered component. Default: ``0.001``.
    clip:
        Configuration value used by the registered component. Default: ``1.0``.
    vol_floor:
        Configuration value used by the registered component. Default: ``1e-06``.
    min_signal_abs:
        Configuration value used by the registered component. Default: ``0.0``.
    activation_filters:
        Configuration value used by the registered component. Default: ``None``.
    top_quantile:
        Configuration value used by the registered component. Default: ``None``.
    top_quantile_window:
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``None``.
    max_trade_rate:
        Configuration value used by the registered component. Default: ``None``.
    """
    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_prob_vol_adj",
    )
    out = compute_probability_vol_adjusted_signal(
        df,
        prob_col=prob_col,
        vol_col=vol_col,
        signal_col=output_col,
        prob_center=prob_center,
        upper=upper,
        lower=lower,
        vol_target=vol_target,
        clip=clip,
        vol_floor=vol_floor,
        min_signal_abs=min_signal_abs,
        activation_filters=activation_filters,
        top_quantile=top_quantile,
        top_quantile_window=top_quantile_window,
        max_trade_rate=max_trade_rate,
    )
    return out[output_col]


__all__ = ["probability_vol_adjusted_signal"]
