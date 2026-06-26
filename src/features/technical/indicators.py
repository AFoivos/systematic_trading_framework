from __future__ import annotations

from typing import Sequence

import pandas as pd

from .adx import compute_adx
from .atr import compute_atr
from .bollinger import add_bollinger_bands
from .macd import compute_macd
from .mfi import compute_mfi
from .ppo import compute_ppo
from .roc import compute_roc
from .true_range import compute_true_range
from .volume_features import compute_volume_over_atr, compute_volume_zscore


def add_indicator_features(
    df: pd.DataFrame,
    price_col: str = "close",
    high_col: str = "high",
    low_col: str = "low",
    volume_col: str = "volume",
    bb_window: int = 20,
    bb_nstd: float = 2.0,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    ppo_fast: int = 12,
    ppo_slow: int = 26,
    ppo_signal: int = 9,
    roc_windows: Sequence[int] = (10, 20),
    atr_window: int = 14,
    adx_window: int = 14,
    vol_z_window: int = 20,
    include_mfi: bool = True,
) -> pd.DataFrame:
    """
    Apply the registered ``indicator`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: indicator
            params:
              price_col: close
              high_col: high
              low_col: low
              volume_col: volume
              bb_window: 20
              bb_nstd: 2.0
              macd_fast: 12
              macd_slow: 26
              macd_signal: 9
              ppo_fast: 12
              ppo_slow: 26
              ppo_signal: 9
              roc_windows: [10, 20]
              atr_window: 14
              adx_window: 14
              vol_z_window: 20
              include_mfi: true
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    volume_col:
        Input dataframe column configured by ``volume_col``. Default: ``volume``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    volume_col:
        Input dataframe column configured by ``volume_col``. Default: ``volume``.
    bb_window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``20``.
    bb_nstd:
        Configuration parameter accepted by this feature. Default: ``2.0``.
    macd_fast:
        Configuration parameter accepted by this feature. Default: ``12``.
    macd_slow:
        Configuration parameter accepted by this feature. Default: ``26``.
    macd_signal:
        Configuration parameter accepted by this feature. Default: ``9``.
    ppo_fast:
        Configuration parameter accepted by this feature. Default: ``12``.
    ppo_slow:
        Configuration parameter accepted by this feature. Default: ``26``.
    ppo_signal:
        Configuration parameter accepted by this feature. Default: ``9``.
    roc_windows:
        Trailing lookback or forecast horizon controlling this feature. Default: ``[10, 20]``.
    atr_window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``14``.
    adx_window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``14``.
    vol_z_window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``20``.
    include_mfi:
        Configuration parameter accepted by this feature. Default: ``true``.
    """
    missing = [c for c in (price_col, high_col, low_col, volume_col) if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for indicators: {missing}")

    out = df.copy()
    close = out[price_col].astype(float)
    high = out[high_col].astype(float)
    low = out[low_col].astype(float)
    vol = out[volume_col].astype(float)

    out = out.join(add_bollinger_bands(close, window=bb_window, n_std=bb_nstd))
    out = out.join(compute_macd(close, fast=macd_fast, slow=macd_slow, signal=macd_signal))
    out = out.join(compute_ppo(close, fast=ppo_fast, slow=ppo_slow, signal=ppo_signal))
    for window in roc_windows:
        out[f"roc_{window}"] = compute_roc(close, window=window)
    out[f"atr_{atr_window}"] = compute_atr(high, low, close, window=atr_window)
    out[f"atr_over_price_{atr_window}"] = out[f"atr_{atr_window}"] / close
    out = out.join(compute_adx(high, low, close, window=adx_window))
    out[f"volume_z_{vol_z_window}"] = compute_volume_zscore(vol, window=vol_z_window)
    out[f"volume_over_atr_{atr_window}"] = compute_volume_over_atr(vol, out[f"atr_{atr_window}"], window=atr_window)
    if include_mfi:
        out[f"mfi_{atr_window}"] = compute_mfi(high, low, close, vol, window=atr_window)
    return out


__all__ = [
    "compute_true_range",
    "compute_atr",
    "add_bollinger_bands",
    "compute_macd",
    "compute_ppo",
    "compute_roc",
    "compute_volume_zscore",
    "compute_volume_over_atr",
    "compute_adx",
    "compute_mfi",
    "add_indicator_features",
]
