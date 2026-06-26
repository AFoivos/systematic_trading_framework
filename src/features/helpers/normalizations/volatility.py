from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.helpers.common import require_columns


def add_volatility_normalization_features(
    df: pd.DataFrame,
    *,
    close_col: str = "close",
    atr_col: str = "atr_14",
    add_atr_pct: bool = True,
    add_atr_percentile: bool = True,
    percentile_window: int = 252,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``volatility_normalization`` normalization helper transformation.
    
    This normalization helper uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        normalizations:
          volatility_normalization:
            params:
              close_col: close
              atr_col: atr_14
              add_atr_pct: true
              add_atr_percentile: true
              percentile_window: 252
              inplace: false
          outputs:
            - atr_14
    
    Required input columns
    ----------------------
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    
    Parameters
    ----------
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    atr_col:
        Output dataframe column configured by ``atr_col``. Default: ``atr_14``.
    add_atr_pct:
        Boolean switch controlling optional normalization helper behavior. Default: ``true``.
    add_atr_percentile:
        Boolean switch controlling optional normalization helper behavior. Default: ``true``.
    percentile_window:
        Trailing lookback or forecast horizon controlling this normalization helper. Default: ``252``.
    inplace:
        Boolean switch controlling optional normalization helper behavior. Default: ``false``.
    """
    require_columns(df, [close_col, atr_col], owner="volatility normalization")
    if isinstance(percentile_window, bool) or int(percentile_window) <= 1:
        raise ValueError("percentile_window must be > 1.")

    out = df if inplace else df.copy()
    close = out[close_col].replace(0, np.nan).astype(float)
    atr = out[atr_col].astype(float)
    resolved_window = int(percentile_window)

    if add_atr_pct:
        out[f"{atr_col}_pct"] = atr / close

    if add_atr_percentile:
        out[f"{atr_col}_percentile_{resolved_window}"] = (
            atr.rolling(resolved_window, min_periods=resolved_window)
            .apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
        )

    return out


__all__ = ["add_volatility_normalization_features"]
