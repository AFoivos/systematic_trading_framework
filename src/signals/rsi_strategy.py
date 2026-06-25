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
    """
    Apply the registered ``rsi`` signal transformation.
    
    YAML declaration::
    
        signals:
          kind: rsi
          params:
            rsi_col: rsi_14
    
    Required input columns
    ----------------------
    None fixed by signature:
        Required dataframe columns are resolved from configuration or from
        upstream feature/target/signal stages at runtime.
    
    Parameters
    ----------
    rsi_col:
        Input dataframe column name consumed by the component.
    buy_level:
        Configuration value used by the registered component. Default: ``30.0``.
    sell_level:
        Configuration value used by the registered component. Default: ``70.0``.
    signal_col:
        Output column name emitted by the component. Default: ``None``.
    mode:
        Mode selector that controls the registered component behavior. Default: ``long_short_hold``.
    """
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
