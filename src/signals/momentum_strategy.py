from __future__ import annotations

import pandas as pd

from src.signals._common import resolve_signal_output_name
from src.signals.momentum_signal import compute_momentum_signal


def momentum_strategy(
    df: pd.DataFrame,
    momentum_col: str,
    long_threshold: float = 0.0,
    short_threshold: float | None = None,
    signal_col: str | None = None,
    mode: str = "long_short_hold",
) -> pd.Series:
    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_momentum",
    )
    out = compute_momentum_signal(
        df,
        momentum_col=momentum_col,
        long_threshold=long_threshold,
        short_threshold=short_threshold,
        signal_col=output_col,
        mode=mode,
    )
    return out[output_col]


__all__ = ["momentum_strategy"]
