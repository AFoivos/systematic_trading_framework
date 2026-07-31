from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.registry import get_feature_fn

from src.utils.eurusd_ftmo_ml_v2_contract import (
    BASE_NOTIONAL_MULTIPLE,
    EWMA_VOL_SPAN_BARS,
    PERIODS_PER_YEAR,
    VOLATILITY_FACTOR_CAP,
    VOLATILITY_FACTOR_FLOOR,
)


def add_volatility_factor(market: pd.DataFrame) -> pd.DataFrame:
    if "logret1" not in market.columns:
        raise KeyError("market must contain logret1.")
    out = get_feature_fn("volatility")(
        market,
        returns_col="logret1",
        rolling_windows=(),
        ewma_spans=(EWMA_VOL_SPAN_BARS,),
        annualization_factor=float(PERIODS_PER_YEAR),
    )
    out["ewma20_annual_vol"] = out[f"vol_ewma_{EWMA_VOL_SPAN_BARS}"]
    out["lagged_ewma20_annual_vol"] = out["ewma20_annual_vol"].shift(1)
    out["expanding_median_annual_vol"] = out["ewma20_annual_vol"].shift(1).expanding().median()
    out["volatility_factor"] = (
        out["expanding_median_annual_vol"] / out["lagged_ewma20_annual_vol"]
    ).clip(VOLATILITY_FACTOR_FLOOR, VOLATILITY_FACTOR_CAP)
    return out


def drawdown_scale(drawdown: float | pd.Series | np.ndarray) -> float | pd.Series | np.ndarray:
    raw = (0.065 + drawdown) / (0.065 - 0.025)
    if isinstance(raw, pd.Series):
        return raw.clip(0.0, 1.0)
    if isinstance(raw, np.ndarray):
        return np.clip(raw, 0.0, 1.0)
    return float(np.clip(raw, 0.0, 1.0))


def raw_position_multiple(directional_signal: pd.Series, volatility_factor: pd.Series) -> pd.Series:
    return directional_signal.astype(float) * BASE_NOTIONAL_MULTIPLE * volatility_factor.astype(float)


__all__ = ["add_volatility_factor", "drawdown_scale", "raw_position_multiple"]
