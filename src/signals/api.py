from __future__ import annotations

import pandas as pd

from src.risk.position_sizing import scale_signal_by_vol
from src.signals.forecast_signal import (
    compute_forecast_threshold_signal,
    compute_forecast_vol_adjusted_signal,
    compute_probability_vol_adjusted_signal,
)
from src.signals.momentum_signal import compute_momentum_signal
from src.signals.rsi_signal import compute_rsi_signal
from src.signals.stochastic_signal import compute_stochastic_signal
from src.signals.trend_signal import compute_trend_state_signal
from src.signals.volatility_signal import compute_volatility_regime_signal


def _resolve_signal_output_name(
    *,
    signal_col: str | None,
    default: str,
) -> str:
    return str(signal_col or default)


def buy_and_hold_signal(
    df: pd.DataFrame,
    signal_col: str | None = None,
) -> pd.Series:
    """
    Long-only buy-and-hold signal.
    """
    if "close" not in df.columns:
        raise ValueError("Expected column 'close' in df.")
    output_col = _resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_bh",
    )
    return pd.Series(1.0, index=df.index, name=output_col)


def trend_state_long_only_signal(
    df: pd.DataFrame,
    state_col: str,
    signal_col: str | None = None,
) -> pd.Series:
    """
    Long-only signal based on a trend state column (expects positive values for bull state).
    """
    if state_col not in df.columns:
        raise KeyError(f"state_col '{state_col}' not found in DataFrame")
    output_col = _resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_trend_state_long_only",
    )
    signal = (df[state_col].astype(float) > 0).astype(float)
    signal.name = output_col
    return signal


def trend_state_signal(
    df: pd.DataFrame,
    state_col: str,
    signal_col: str | None = None,
    mode: str = "long_short_hold",
) -> pd.Series:
    output_col = _resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_trend_state",
    )
    out = compute_trend_state_signal(
        df,
        state_col=state_col,
        signal_col=output_col,
        mode=mode,
    )
    return out[output_col]


def rsi_strategy(
    df: pd.DataFrame,
    rsi_col: str,
    buy_level: float = 30.0,
    sell_level: float = 70.0,
    signal_col: str | None = None,
    mode: str = "long_short_hold",
) -> pd.Series:
    output_col = _resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_rsi",
    )
    out = compute_rsi_signal(
        df,
        rsi_col=rsi_col,
        buy_level=buy_level,
        sell_level=sell_level,
        signal_col=output_col,
        mode=mode,
    )
    return out[output_col]


def momentum_strategy(
    df: pd.DataFrame,
    momentum_col: str,
    long_threshold: float = 0.0,
    short_threshold: float | None = None,
    signal_col: str | None = None,
    mode: str = "long_short_hold",
) -> pd.Series:
    output_col = _resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_momentum",
    )
    out = compute_momentum_signal(
        df,
        momentum_col=momentum_col,
        long_threshold=long_threshold,
        short_threshold=short_threshold,
        signal_col=output_col,
        mode=mode,
    )
    return out[output_col]


def stochastic_strategy(
    df: pd.DataFrame,
    k_col: str,
    buy_level: float = 20.0,
    sell_level: float = 80.0,
    signal_col: str | None = None,
    mode: str = "long_short_hold",
) -> pd.Series:
    output_col = _resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_stochastic",
    )
    out = compute_stochastic_signal(
        df,
        k_col=k_col,
        buy_level=buy_level,
        sell_level=sell_level,
        signal_col=output_col,
        mode=mode,
    )
    return out[output_col]


def volatility_regime_strategy(
    df: pd.DataFrame,
    vol_col: str,
    quantile: float = 0.5,
    signal_col: str | None = None,
    mode: str = "long_short_hold",
) -> pd.Series:
    output_col = _resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_volatility_regime",
    )
    out = compute_volatility_regime_signal(
        df,
        vol_col=vol_col,
        quantile=quantile,
        signal_col=output_col,
        mode=mode,
    )
    return out[output_col]


def probabilistic_signal(
    df: pd.DataFrame,
    prob_col: str,
    signal_col: str | None = None,
    upper: float = 0.55,
    lower: float = 0.45,
) -> pd.Series:
    """
    Map probability forecasts to {-1,0,1} signal with dead-zone.
    """
    if prob_col not in df.columns:
        raise KeyError(f"prob_col '{prob_col}' not found in DataFrame")
    output_col = _resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_prob",
    )
    prob = df[prob_col].astype(float)
    sig = pd.Series(0.0, index=df.index, name=output_col)
    sig[prob > upper] = 1.0
    sig[prob < lower] = -1.0
    return sig


def conviction_sizing_signal(
    df: pd.DataFrame,
    prob_col: str,
    signal_col: str | None = None,
    clip: float = 1.0,
) -> pd.Series:
    """
    Linear map prob∈[0,1] to exposure∈[-clip, clip].
    """
    if prob_col not in df.columns:
        raise KeyError(f"prob_col '{prob_col}' not found in DataFrame")
    output_col = _resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_prob_size",
    )
    prob = df[prob_col].astype(float)
    exp = clip * (prob - 0.5) * 2.0
    exp = exp.clip(-clip, clip)
    exp.name = output_col
    return exp


def forecast_threshold_signal(
    df: pd.DataFrame,
    forecast_col: str = "pred_ret",
    signal_col: str | None = None,
    upper: float = 0.0,
    lower: float | None = None,
    mode: str = "long_short_hold",
) -> pd.Series:
    output_col = _resolve_signal_output_name(
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


def forecast_vol_adjusted_signal(
    df: pd.DataFrame,
    forecast_col: str = "pred_ret",
    vol_col: str = "pred_vol",
    signal_col: str | None = None,
    clip: float = 1.0,
    vol_floor: float = 1e-6,
) -> pd.Series:
    output_col = _resolve_signal_output_name(
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


def probability_vol_adjusted_signal(
    df: pd.DataFrame,
    prob_col: str = "pred_prob",
    vol_col: str = "pred_vol",
    signal_col: str | None = None,
    prob_center: float = 0.5,
    upper: float | None = None,
    lower: float | None = None,
    vol_target: float = 0.001,
    clip: float = 1.0,
    vol_floor: float = 1e-6,
    min_signal_abs: float = 0.0,
    activation_filters: list[dict[str, object]] | None = None,
) -> pd.Series:
    output_col = _resolve_signal_output_name(
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
    )
    return out[output_col]


def regime_filtered_signal(
    df: pd.DataFrame,
    base_signal_col: str,
    regime_col: str,
    signal_col: str | None = None,
    active_value: float = 1.0,
) -> pd.Series:
    """
    Keep base signal only when regime_col == active_value (else 0).
    """
    if base_signal_col not in df.columns:
        raise KeyError(f"base_signal_col '{base_signal_col}' not found in DataFrame")
    if regime_col not in df.columns:
        raise KeyError(f"regime_col '{regime_col}' not found in DataFrame")
    output_col = _resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_regime_filtered",
    )
    sig = df[base_signal_col].astype(float).copy()
    sig.loc[df[regime_col] != active_value] = 0.0
    sig.name = output_col
    return sig


def vol_targeted_signal(
    df: pd.DataFrame,
    signal_col: str,
    vol_col: str,
    target_vol: float,
    max_leverage: float = 3.0,
    *,
    output_col: str | None = None,
) -> pd.Series:
    """
    Scale an existing signal column by volatility targeting.
    """
    if signal_col not in df.columns:
        raise KeyError(f"signal_col '{signal_col}' not found in DataFrame")
    if vol_col not in df.columns:
        raise KeyError(f"vol_col '{vol_col}' not found in DataFrame")
    name = _resolve_signal_output_name(
        signal_col=output_col,
        default="signal_vol_tgt",
    )
    scaled = scale_signal_by_vol(
        signal=df[signal_col].astype(float),
        vol=df[vol_col].astype(float),
        target_vol=target_vol,
        max_leverage=max_leverage,
    )
    scaled.name = name
    return scaled


__all__ = [
    "buy_and_hold_signal",
    "trend_state_long_only_signal",
    "trend_state_signal",
    "rsi_strategy",
    "momentum_strategy",
    "stochastic_strategy",
    "volatility_regime_strategy",
    "probabilistic_signal",
    "conviction_sizing_signal",
    "forecast_threshold_signal",
    "forecast_vol_adjusted_signal",
    "probability_vol_adjusted_signal",
    "regime_filtered_signal",
    "vol_targeted_signal",
]
