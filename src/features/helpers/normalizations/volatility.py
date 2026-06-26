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
