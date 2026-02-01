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
