from __future__ import annotations

import pandas as pd

from src.signals._common import resolve_signal_output_name


def buy_and_hold_signal(
    df: pd.DataFrame,
    signal_col: str | None = None,
) -> pd.Series:
    """
    Long-only buy-and-hold signal.
    """
    if "close" not in df.columns:
        raise ValueError("Expected column 'close' in df.")
    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_bh",
    )
    return pd.Series(1.0, index=df.index, name=output_col)


__all__ = ["buy_and_hold_signal"]
