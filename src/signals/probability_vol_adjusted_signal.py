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
