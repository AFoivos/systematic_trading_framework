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
    Apply the registered ``momentum`` signal transformation.
    
    YAML declaration::
    
        signals:
          kind: momentum
          params:
            momentum_col: momentum_20
    
    Required input columns
    ----------------------
    None fixed by signature:
        Required dataframe columns are resolved from configuration or from
        upstream feature/target/signal stages at runtime.
    
    Parameters
    ----------
    momentum_col:
        Input dataframe column name consumed by the component.
    long_threshold:
        Numeric threshold controlling the component decision rule. Default: ``0.0``.
    short_threshold:
        Numeric threshold controlling the component decision rule. Default: ``None``.
    signal_col:
        Output column name emitted by the component. Default: ``None``.
    mode:
        Mode selector that controls the registered component behavior. Default: ``long_short_hold``.
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
