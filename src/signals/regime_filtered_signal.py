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
    Keep base signal only when regime_col == active_value.
    
    YAML declaration::
    
        signals:
          kind: regime_filtered
          params:
            base_signal_col: signal
            regime_col: trend_regime
    
    Required input columns
    ----------------------
    None fixed by signature:
        Required dataframe columns are resolved from configuration or from
        upstream feature/target/signal stages at runtime.
    
    Parameters
    ----------
    base_signal_col:
        Output column name emitted by the component.
    regime_col:
        Input dataframe column name consumed by the component.
    signal_col:
        Output column name emitted by the component. Default: ``None``.
    active_value:
        Configuration value used by the registered component. Default: ``1.0``.
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
