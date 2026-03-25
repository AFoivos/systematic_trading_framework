from __future__ import annotations

import pandas as pd

from src.signals._common import resolve_signal_output_name
from src.signals.rsi_signal import compute_rsi_signal


def rsi_strategy(
    df: pd.DataFrame,
    rsi_col: str,
    buy_level: float = 30.0,
    sell_level: float = 70.0,
    signal_col: str | None = None,
    mode: str = "long_short_hold",
) -> pd.Series:
    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_rsi",
    )
    out = compute_rsi_signal(
        df,
        rsi_col=rsi_col,
        buy_level=buy_level,
        sell_level=sell_level,
        signal_col=output_col,
        mode=mode,
    )
    return out[output_col]


__all__ = ["rsi_strategy"]
