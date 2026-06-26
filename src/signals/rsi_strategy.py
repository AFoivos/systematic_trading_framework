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
    Apply the registered ``rsi_strategy`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: rsi_strategy
          params:
            rsi_col: <required>
            buy_level: 30.0
            sell_level: 70.0
            signal_col: null
            mode: long_short_hold
          output_cols:
            - configured by signal_col
    
    Required input columns
    ----------------------
    rsi_col:
        Input dataframe column configured by ``rsi_col``.
    
    Parameters
    ----------
    rsi_col:
        Input dataframe column configured by ``rsi_col``.
    buy_level:
        Configuration parameter accepted by this signal. Default: ``30.0``.
    sell_level:
        Configuration parameter accepted by this signal. Default: ``70.0``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``null``.
    mode:
        Mode selector controlling how this signal is applied. Default: ``long_short_hold``.
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
