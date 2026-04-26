from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def compute_vol_target_leverage(
    vol: pd.Series,
    target_vol: float,
    max_leverage: float = 3.0,
    min_leverage: float = 0.0,
    eps: float = 1e-8,
) -> pd.Series:
    """
    Compute leverage to target a given volatility level.
    leverage = target_vol / vol, clipped to [min_leverage, max_leverage].
    """
    if not isinstance(vol, pd.Series):
        raise TypeError("vol must be a pandas Series")

    lev = target_vol / (vol.astype(float) + eps)
    lev = lev.clip(lower=min_leverage, upper=max_leverage)
    lev.name = f"{vol.name}_lev_target_{target_vol}"
    return lev


def scale_signal_by_vol(
    signal: pd.Series,
    vol: pd.Series,
    target_vol: float,
    max_leverage: float = 3.0,
    min_leverage: float = 0.0,
    eps: float = 1e-8,
) -> pd.Series:
    """
    Scale a trading signal by volatility targeting leverage.
    """
    if not isinstance(signal, pd.Series):
        raise TypeError("signal must be a pandas Series")
    if not isinstance(vol, pd.Series):
        raise TypeError("vol must be a pandas Series")

    lev = compute_vol_target_leverage(
        vol=vol,
        target_vol=target_vol,
        max_leverage=max_leverage,
        min_leverage=min_leverage,
        eps=eps,
    )
    scaled = signal.astype(float) * lev
    scaled.name = f"{signal.name}_vol_scaled"
    return scaled


def scale_signal_for_ftmo(
    signal: pd.Series,
    vol: pd.Series,
    *,
    target_vol: float | None = None,
    risk_per_trade: float = 0.0025,
    stop_mult: float = 1.0,
    max_leverage: float = 3.0,
    min_leverage: float = 0.0,
    min_abs_signal: float = 0.0,
    confidence: pd.Series | None = None,
    confidence_floor: float | None = None,
    confidence_mode: str = "directional_class1",
    confidence_power: float = 1.0,
    eps: float = 1e-8,
) -> pd.Series:
    """
    Convert signed model conviction into FTMO-style risk-per-trade exposure.

    The returned series is signed exposure, not a normalized portfolio score. Volatility is
    interpreted as the stop-distance input in return space, so risk_per_trade / stop_distance
    approximates the leverage that risks risk_per_trade of equity at the configured stop.
    """
    if not isinstance(signal, pd.Series):
        raise TypeError("signal must be a pandas Series")
    if not isinstance(vol, pd.Series):
        raise TypeError("vol must be a pandas Series")
    if risk_per_trade <= 0:
        raise ValueError("risk_per_trade must be > 0.")
    if stop_mult <= 0:
        raise ValueError("stop_mult must be > 0.")
    if max_leverage < 0:
        raise ValueError("max_leverage must be >= 0.")
    if min_leverage < 0:
        raise ValueError("min_leverage must be >= 0.")
    if min_leverage > max_leverage:
        raise ValueError("min_leverage must be <= max_leverage.")
    if min_abs_signal < 0:
        raise ValueError("min_abs_signal must be >= 0.")
    if target_vol is not None and target_vol <= 0:
        raise ValueError("target_vol must be > 0 when provided.")
    if confidence_power <= 0:
        raise ValueError("confidence_power must be > 0.")
    if confidence_floor is not None and not 0.0 <= float(confidence_floor) < 1.0:
        raise ValueError("confidence_floor must be in [0, 1).")
    if confidence_mode not in {"directional_class1", "meta_success"}:
        raise ValueError("confidence_mode must be one of: directional_class1, meta_success.")

    index = signal.index
    sig = signal.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    vol_aligned = (
        vol.reindex(index)
        .astype(float)
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
        .abs()
    )
    stop_distance = (float(stop_mult) * vol_aligned).clip(lower=float(eps))
    risk_based = float(risk_per_trade) / stop_distance
    if target_vol is not None:
        vol_based = float(target_vol) / vol_aligned.clip(lower=float(eps))
        leverage = pd.concat([risk_based, vol_based], axis=1).min(axis=1)
    else:
        leverage = risk_based
    leverage = leverage.replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(
        lower=float(min_leverage),
        upper=float(max_leverage),
    )

    active = sig.abs() >= float(min_abs_signal)
    confidence_adj = pd.Series(1.0, index=index, dtype=float)
    if confidence is not None:
        conf = (
            confidence.reindex(index)
            .astype(float)
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
            .clip(lower=0.0, upper=1.0)
        )
        if confidence_mode == "directional_class1":
            conf = conf.where(sig >= 0.0, 1.0 - conf)
        if confidence_floor is not None:
            floor = float(confidence_floor)
            confidence_adj = ((conf - floor).clip(lower=0.0) / max(1.0 - floor, float(eps))).clip(
                lower=0.0,
                upper=1.0,
            )
        else:
            confidence_adj = conf
        confidence_adj = confidence_adj.pow(float(confidence_power))

    exposure = np.sign(sig) * sig.abs().clip(upper=1.0) * leverage * confidence_adj
    exposure = exposure.where(active, 0.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    exposure.name = f"{signal.name}_ftmo_scaled"
    return exposure.astype(float)


__all__ = [
    "compute_vol_target_leverage",
    "scale_signal_by_vol",
    "scale_signal_for_ftmo",
]
