from __future__ import annotations

import pandas as pd

from src.signals._common import resolve_signal_output_name


def trend_state_long_only_signal(
    df: pd.DataFrame,
    state_col: str,
    signal_col: str | None = None,
) -> pd.Series:
    """
    Long-only signal based on a trend state column.
    """
    if state_col not in df.columns:
        raise KeyError(f"state_col '{state_col}' not found in DataFrame")
    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_trend_state_long_only",
    )
    signal = (df[state_col].astype(float) > 0).astype(float)
    signal.name = output_col
    return signal


__all__ = ["trend_state_long_only_signal"]
