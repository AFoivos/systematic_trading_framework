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
    """
    Apply the registered ``momentum_strategy`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: momentum_strategy
          params:
            momentum_col: <required>
            long_threshold: 0.0
            short_threshold: null
            signal_col: null
            mode: long_short_hold
          output_cols:
            - configured by signal_col
    
    Required input columns
    ----------------------
    momentum_col:
        Input dataframe column configured by ``momentum_col``.
    
    Parameters
    ----------
    momentum_col:
        Input dataframe column configured by ``momentum_col``.
    long_threshold:
        Numeric threshold used by this signal. Default: ``0.0``.
    short_threshold:
        Numeric threshold used by this signal. Default: ``null``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``null``.
    mode:
        Mode selector controlling how this signal is applied. Default: ``long_short_hold``.
    """
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
