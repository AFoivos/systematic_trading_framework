from __future__ import annotations

import numpy as np
import pandas as pd


def add_trend_regime_features(
    df: pd.DataFrame,
    price_col: str = "close",
    base_sma_for_sign: int = 50,
    short_sma: int = 20,
    long_sma: int = 50,
    inplace: bool = False,
) -> pd.DataFrame:
    out = df if inplace else df.copy()
    over_col = f"{price_col}_over_sma_{base_sma_for_sign}"
    if over_col not in out.columns:
        raise KeyError(
            f"Required column '{over_col}' not found. "
            "Run add_trend_features() first with appropriate sma_windows."
        )

    regime_col = f"{price_col}_trend_regime_sma_{base_sma_for_sign}"
    regime = np.sign(out[over_col].astype(float))
    regime = regime.where(~out[over_col].isna(), other=np.nan)
    out[regime_col] = regime.astype("float32")

    short_col = f"{price_col}_sma_{short_sma}"
    long_col = f"{price_col}_sma_{long_sma}"
    missing = [c for c in (short_col, long_col) if c not in out.columns]
    if missing:
        raise KeyError(f"Missing SMA columns {missing}. Run add_trend_features() with matching sma_windows.")

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
