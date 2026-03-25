from __future__ import annotations

import pandas as pd

from src.signals._common import resolve_signal_output_name
from src.signals.trend_signal import compute_trend_state_signal


def trend_state_signal(
    df: pd.DataFrame,
    state_col: str,
    signal_col: str | None = None,
    mode: str = "long_short_hold",
) -> pd.Series:
    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_trend_state",
    )
    out = compute_trend_state_signal(
        df,
        state_col=state_col,
        signal_col=output_col,
        mode=mode,
    )
    return out[output_col]


__all__ = ["trend_state_signal"]
