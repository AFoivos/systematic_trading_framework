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
    """
    Apply the registered ``trend_state`` signal transformation.
    
    YAML declaration::
    
        signals:
          kind: trend_state
          params:
            state_col: trend_regime
    
    Required input columns
    ----------------------
    state_col:
        Optional input column configured by ``state_col``; used when a value is provided.
    
    Parameters
    ----------
    state_col:
        Input dataframe column name consumed by the component.
    signal_col:
        Output column name emitted by the component. Default: ``None``.
    mode:
        Mode selector that controls the registered component behavior. Default: ``long_short_hold``.
    """
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
