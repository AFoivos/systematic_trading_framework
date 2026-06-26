from __future__ import annotations

import pandas as pd

from src.signals._common import resolve_signal_output_name


def regime_filtered_signal(
    df: pd.DataFrame,
    base_signal_col: str,
    regime_col: str,
    signal_col: str | None = None,
    active_value: float = 1.0,
) -> pd.Series:
    """
    Apply the registered ``regime_filtered`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: regime_filtered
          params:
            base_signal_col: <required>
            regime_col: <required>
            signal_col: null
            active_value: 1.0
          output_cols:
            - configured by signal_col
    
    Required input columns
    ----------------------
    regime_col:
        Input dataframe column configured by ``regime_col``.
    
    Parameters
    ----------
    base_signal_col:
        Input dataframe column configured by ``base_signal_col``.
    regime_col:
        Input dataframe column configured by ``regime_col``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``null``.
    active_value:
        Configuration parameter accepted by this signal. Default: ``1.0``.
    """
    if base_signal_col not in df.columns:
        raise KeyError(f"base_signal_col '{base_signal_col}' not found in DataFrame")
    if regime_col not in df.columns:
        raise KeyError(f"regime_col '{regime_col}' not found in DataFrame")

    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_regime_filtered",
    )
    sig = df[base_signal_col].astype(float).copy()
    sig.loc[df[regime_col] != active_value] = 0.0
    sig.name = output_col
    return sig


__all__ = ["regime_filtered_signal"]
