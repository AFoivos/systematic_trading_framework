from __future__ import annotations

import pandas as pd

from src.signals._common import resolve_signal_output_name


def conviction_sizing_signal(
    df: pd.DataFrame,
    prob_col: str,
    signal_col: str | None = None,
    clip: float = 1.0,
) -> pd.Series:
    """
    Linear map prob in [0, 1] to exposure in [-clip, clip].
    
    YAML declaration::
    
        signals:
          kind: probability_conviction
          params:
            prob_col: pred_prob
    
    Required input columns
    ----------------------
    prob_col:
        Optional input column configured by ``prob_col``; used when a value is provided.
    
    Parameters
    ----------
    prob_col:
        Input dataframe column name consumed by the component.
    signal_col:
        Output column name emitted by the component. Default: ``None``.
    clip:
        Configuration value used by the registered component. Default: ``1.0``.
    """
    if prob_col not in df.columns:
        raise KeyError(f"prob_col '{prob_col}' not found in DataFrame")
    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_prob_size",
    )
    prob = df[prob_col].astype(float)
    exp = clip * (prob - 0.5) * 2.0
    exp = exp.clip(-clip, clip)
    exp.name = output_col
    return exp


__all__ = ["conviction_sizing_signal"]
