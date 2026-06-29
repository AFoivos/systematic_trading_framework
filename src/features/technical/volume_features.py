from __future__ import annotations

import numpy as np
import pandas as pd


def add_volume_features(
    df: pd.DataFrame,
    volume_col: str = "volume",
    atr_col: str | None = None,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    atr_window: int = 14,
    vol_z_window: int = 20,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``volume`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: volume
            params:
              volume_col: volume
              atr_col: null
              high_col: high
              low_col: low
              close_col: close
              atr_window: 14
              vol_z_window: 20
              inplace: false
            output_cols:
              - configured by atr_col
    
    Required input columns
    ----------------------
    volume_col:
        Input dataframe column configured by ``volume_col``. Default: ``volume``.
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    
    Parameters
    ----------
    volume_col:
        Input dataframe column configured by ``volume_col``. Default: ``volume``.
    atr_col:
        Output dataframe column configured by ``atr_col``. Default: ``null``.
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    atr_window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``14``.
    vol_z_window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``20``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    """
    if volume_col not in df.columns:
        raise KeyError(f"volume_col '{volume_col}' not found in DataFrame")

    out = df if inplace else df.copy()
    volume = out[volume_col].astype(float)
    out[f"volume_z_{vol_z_window}"] = compute_volume_zscore(volume, window=vol_z_window)

    resolved_atr_col = atr_col or f"atr_{atr_window}"
    if resolved_atr_col not in out.columns:
        missing = [c for c in (high_col, low_col, close_col) if c not in out.columns]
        if missing:
            raise KeyError(
                f"Missing columns for volume_over_atr features: {missing}; "
                f"or provide an existing atr_col='{resolved_atr_col}'."
            )
        from .atr import compute_atr

        out[resolved_atr_col] = compute_atr(
            out[high_col].astype(float),
            out[low_col].astype(float),
            out[close_col].astype(float),
            window=atr_window,
        )

    out[f"volume_over_atr_{atr_window}"] = compute_volume_over_atr(
        volume,
        out[resolved_atr_col].astype(float),
        window=atr_window,
    )
    return out


def compute_volume_zscore(volume: pd.Series, window: int = 20) -> pd.Series:
    """
    Compute the ``compute_volume_zscore`` feature value.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: compute_volume_zscore
            params:
              volume: <required>
              window: 20
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    volume:
        Configuration parameter accepted by this feature.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``20``.
    """
    mean = volume.rolling(window=window, min_periods=window).mean()
    std = volume.rolling(window=window, min_periods=window).std(ddof=0)
    z = (volume - mean) / std.replace(0, np.nan)
    z.name = f"volume_z_{window}"
    return z


def compute_volume_over_atr(volume: pd.Series, atr: pd.Series, *, window: int) -> pd.Series:
    """
    Compute the ``compute_volume_over_atr`` feature value.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: compute_volume_over_atr
            params:
              volume: <required>
              atr: <required>
              window: <required>
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    volume:
        Configuration parameter accepted by this feature.
    atr:
        Configuration parameter accepted by this feature.
    window:
        Trailing lookback or forecast horizon controlling this feature.
    """
    out = volume.astype(float) / atr.astype(float)
    out.name = f"volume_over_atr_{window}"
    return out

__all__ = ["compute_volume_over_atr", "compute_volume_zscore", "add_volume_features"]
