from __future__ import annotations

import pandas as pd

from src.signals import (
    compute_momentum_signal,
    compute_rsi_signal,
    compute_stochastic_signal,
    compute_trend_state_signal,
    compute_volatility_regime_signal,
)
from src.risk.position_sizing import scale_signal_by_vol


def buy_and_hold_signal(df: pd.DataFrame, signal_name: str = "signal_bh") -> pd.Series:
    """
    Long-only buy-and-hold signal.
    """
    if "close" not in df.columns:
        raise ValueError("Expected column 'close' in df.")
    signal = pd.Series(1.0, index=df.index, name=signal_name)
    return signal


def trend_state_long_only_signal(
    df: pd.DataFrame,
    state_col: str,
    signal_name: str = "signal_trend_state_long_only",
) -> pd.Series:
    """
    Long-only signal based on a trend state column (expects 1 for bull).
    """
    if state_col not in df.columns:
        raise KeyError(f"state_col '{state_col}' not found in DataFrame")
    signal = (df[state_col].astype(float) > 0).astype(float)
    signal.name = signal_name
    return signal


def trend_state_signal(
    df: pd.DataFrame,
    state_col: str,
    signal_name: str = "signal_trend_state",
    mode: str = "long_short_hold",
) -> pd.Series:
    """
    Trend-state strategy wrapper (supports long/short/hold modes).
    """
    out = compute_trend_state_signal(
        df,
        state_col=state_col,
        signal_col=signal_name,
        mode=mode,
    )
    return out[signal_name]


def rsi_strategy(
    df: pd.DataFrame,
    rsi_col: str,
    buy_level: float = 30.0,
    sell_level: float = 70.0,
    signal_name: str = "signal_rsi",
    mode: str = "long_short_hold",
) -> pd.Series:
    """
    RSI strategy wrapper (supports long/short/hold modes).
    """
    out = compute_rsi_signal(
        df,
        rsi_col=rsi_col,
        buy_level=buy_level,
        sell_level=sell_level,
        signal_col=signal_name,
        mode=mode,
    )
    return out[signal_name]


def momentum_strategy(
    df: pd.DataFrame,
    momentum_col: str,
    long_threshold: float = 0.0,
    short_threshold: float | None = None,
    signal_name: str = "signal_momentum",
    mode: str = "long_short_hold",
) -> pd.Series:
    """
    Momentum strategy wrapper (supports long/short/hold modes).
    """
    out = compute_momentum_signal(
        df,
        momentum_col=momentum_col,
        long_threshold=long_threshold,
        short_threshold=short_threshold,
        signal_col=signal_name,
        mode=mode,
    )
    return out[signal_name]


def stochastic_strategy(
    df: pd.DataFrame,
    k_col: str,
    buy_level: float = 20.0,
    sell_level: float = 80.0,
    signal_name: str = "signal_stochastic",
    mode: str = "long_short_hold",
) -> pd.Series:
    """
    Stochastic %K strategy wrapper (supports long/short/hold modes).
    """
    out = compute_stochastic_signal(
        df,
        k_col=k_col,
        buy_level=buy_level,
        sell_level=sell_level,
        signal_col=signal_name,
        mode=mode,
    )
    return out[signal_name]


def volatility_regime_strategy(
    df: pd.DataFrame,
    vol_col: str,
    quantile: float = 0.5,
    signal_name: str = "signal_volatility_regime",
    mode: str = "long_short_hold",
) -> pd.Series:
    """
    Volatility regime strategy wrapper (supports long/short/hold modes).
    """
    out = compute_volatility_regime_signal(
        df,
        vol_col=vol_col,
        quantile=quantile,
        signal_col=signal_name,
        mode=mode,
    )
    return out[signal_name]


def probabilistic_signal(
    df: pd.DataFrame,
    prob_col: str,
    signal_name: str = "signal_prob",
    upper: float = 0.55,
    lower: float = 0.45,
) -> pd.Series:
    """
    Map probability forecasts to {-1,0,1} signal with dead-zone.
    """
    if prob_col not in df.columns:
        raise KeyError(f"prob_col '{prob_col}' not found in DataFrame")
    prob = df[prob_col].astype(float)
    sig = pd.Series(0.0, index=df.index, name=signal_name)
    sig[prob > upper] = 1.0
    sig[prob < lower] = -1.0
    return sig


def conviction_sizing_signal(
    df: pd.DataFrame,
    prob_col: str,
    signal_name: str = "signal_prob_size",
    clip: float = 1.0,
) -> pd.Series:
    """
    Linear map prob∈[0,1] to exposure∈[-clip, clip]:
    exposure = clip * (prob - 0.5) * 2
    """
    if prob_col not in df.columns:
        raise KeyError(f"prob_col '{prob_col}' not found in DataFrame")
    prob = df[prob_col].astype(float)
    exp = clip * (prob - 0.5) * 2.0
    exp = exp.clip(-clip, clip)
    exp.name = signal_name
    return exp


def regime_filtered_signal(
    df: pd.DataFrame,
    base_signal_col: str,
    regime_col: str,
    signal_name: str = "signal_regime_filtered",
    active_value: float = 1.0,
) -> pd.Series:
    """
    Keep base signal only when regime_col == active_value (else 0).
    """
    if base_signal_col not in df.columns:
        raise KeyError(f"base_signal_col '{base_signal_col}' not found in DataFrame")
    if regime_col not in df.columns:
        raise KeyError(f"regime_col '{regime_col}' not found in DataFrame")
    sig = df[base_signal_col].astype(float).copy()
    mask = df[regime_col] == active_value
    sig[~mask] = 0.0
    sig.name = signal_name
    return sig


def vol_targeted_signal(
    df: pd.DataFrame,
    signal_col: str,
    vol_col: str,
    target_vol: float,
    max_leverage: float = 3.0,
    signal_name: str = "signal_vol_tgt",
) -> pd.Series:
    """
    Scale signal by volatility targeting using scale_signal_by_vol.
    """
    if signal_col not in df.columns:
        raise KeyError(f"signal_col '{signal_col}' not found in DataFrame")
    if vol_col not in df.columns:
        raise KeyError(f"vol_col '{vol_col}' not found in DataFrame")
    scaled = scale_signal_by_vol(
        signal=df[signal_col].astype(float),
        vol=df[vol_col].astype(float),
        target_vol=target_vol,
        max_leverage=max_leverage,
    )
    scaled.name = signal_name
    return scaled
