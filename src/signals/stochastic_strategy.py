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
    """
    Apply the registered ``stochastic`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: stochastic
          params:
            k_col: <required>
            buy_level: 20.0
            sell_level: 80.0
            signal_col: null
            mode: long_short_hold
            output_cols:
              - configured by signal_col
    
    Required input columns
    ----------------------
    k_col:
        Input dataframe column configured by ``k_col``.
    
    Parameters
    ----------
    k_col:
        Input dataframe column configured by ``k_col``.
    buy_level:
        Configuration parameter accepted by this signal. Default: ``20.0``.
    sell_level:
        Configuration parameter accepted by this signal. Default: ``80.0``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``null``.
    mode:
        Mode selector controlling how this signal is applied. Default: ``long_short_hold``.
    """
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
