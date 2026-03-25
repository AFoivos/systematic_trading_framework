from __future__ import annotations

import pandas as pd

from src.signals._common import resolve_signal_output_name
from src.signals.stochastic_signal import compute_stochastic_signal


def stochastic_strategy(
    df: pd.DataFrame,
    k_col: str,
    buy_level: float = 20.0,
    sell_level: float = 80.0,
    signal_col: str | None = None,
    mode: str = "long_short_hold",
) -> pd.Series:
    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_stochastic",
    )
    out = compute_stochastic_signal(
        df,
        k_col=k_col,
        buy_level=buy_level,
        sell_level=sell_level,
        signal_col=output_col,
        mode=mode,
    )
    return out[output_col]


__all__ = ["stochastic_strategy"]
