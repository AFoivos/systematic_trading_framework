from __future__ import annotations

import pandas as pd

from src.signals._common import resolve_signal_output_name
from src.signals.volatility_signal import compute_volatility_regime_signal


def volatility_regime_strategy(
    df: pd.DataFrame,
    vol_col: str,
    quantile: float = 0.5,
    signal_col: str | None = None,
    mode: str = "long_short_hold",
) -> pd.Series:
    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_volatility_regime",
    )
    out = compute_volatility_regime_signal(
        df,
        vol_col=vol_col,
        quantile=quantile,
        signal_col=output_col,
        mode=mode,
    )
    return out[output_col]


__all__ = ["volatility_regime_strategy"]
