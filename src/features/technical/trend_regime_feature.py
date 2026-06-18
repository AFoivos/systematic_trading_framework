from __future__ import annotations

import numpy as np
import pandas as pd

from .sma import compute_sma


def add_trend_regime_features(
    df: pd.DataFrame,
    price_col: str = "close",
    base_sma_for_sign: int = 50,
    short_sma: int = 20,
    long_sma: int = 50,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Add the SMA-based trend regime features used by the dashboard builder.

    YAML declaration::

        features:
          - step: trend_regime
            params: {}
    """
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")

    out = df if inplace else df.copy()
    prices = out[price_col].astype(float)
    required_windows = {int(base_sma_for_sign), int(short_sma), int(long_sma)}
    for window in sorted(required_windows):
        sma_col = f"{price_col}_sma_{window}"
        if sma_col not in out.columns:
            out[sma_col] = compute_sma(prices, window=window)
        over_sma_col = f"{price_col}_over_sma_{window}"
        if over_sma_col not in out.columns:
            out[over_sma_col] = prices / out[sma_col].astype(float) - 1.0

    over_col = f"{price_col}_over_sma_{base_sma_for_sign}"
    regime_col = f"{price_col}_trend_regime_sma_{base_sma_for_sign}"
    regime = np.sign(out[over_col].astype(float))
    regime = regime.where(~out[over_col].isna(), other=np.nan)
    out[regime_col] = regime.astype("float32")

    short_col = f"{price_col}_sma_{short_sma}"
    long_col = f"{price_col}_sma_{long_sma}"
    state_col = f"{price_col}_trend_state_sma_{short_sma}_{long_sma}"
    state = pd.Series(index=out.index, dtype="float32")
    short = out[short_col].astype(float)
    long_ = out[long_col].astype(float)
    state[short > long_] = 1.0
    state[short < long_] = -1.0
    state[(short.isna()) | (long_.isna())] = 0.0
    out[state_col] = state
    return out


__all__ = ["add_trend_regime_features"]
