from __future__ import annotations

import pandas as pd

from src.risk.position_sizing import scale_signal_by_vol
from src.signals._common import resolve_signal_output_name


def vol_targeted_signal(
    df: pd.DataFrame,
    signal_col: str,
    vol_col: str,
    target_vol: float,
    max_leverage: float = 3.0,
    *,
    output_col: str | None = None,
) -> pd.Series:
    """
    Scale an existing signal column by volatility targeting.
    """
    if signal_col not in df.columns:
        raise KeyError(f"signal_col '{signal_col}' not found in DataFrame")
    if vol_col not in df.columns:
        raise KeyError(f"vol_col '{vol_col}' not found in DataFrame")

    name = resolve_signal_output_name(
        signal_col=output_col,
        default="signal_vol_tgt",
    )
    scaled = scale_signal_by_vol(
        signal=df[signal_col].astype(float),
        vol=df[vol_col].astype(float),
        target_vol=target_vol,
        max_leverage=max_leverage,
    )
    scaled.name = name
    return scaled


__all__ = ["vol_targeted_signal"]
