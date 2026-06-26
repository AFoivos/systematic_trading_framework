from __future__ import annotations

import pandas as pd

from src.signals._common import resolve_signal_output_name
from src.signals.volatility_signal import compute_volatility_regime_signal


def volatility_regime_strategy(
    df: pd.DataFrame,
    vol_col: str,
    quantile: float = 0.5,
    signal_col: str | None = None,
    mode: str = "long_short_hold",
) -> pd.Series:
    """
    Apply the registered ``volatility_regime_strategy`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: volatility_regime_strategy
          params:
            vol_col: <required>
            quantile: 0.5
            signal_col: null
            mode: long_short_hold
          output_cols:
            - configured by signal_col
    
    Required input columns
    ----------------------
    vol_col:
        Input dataframe column configured by ``vol_col``.
    
    Parameters
    ----------
    vol_col:
        Input dataframe column configured by ``vol_col``.
    quantile:
        Configuration parameter accepted by this signal. Default: ``0.5``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``null``.
    mode:
        Mode selector controlling how this signal is applied. Default: ``long_short_hold``.
    """
    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_volatility_regime",
    )
    out = compute_volatility_regime_signal(
        df,
        vol_col=vol_col,
        quantile=quantile,
        signal_col=output_col,
        mode=mode,
    )
    return out[output_col]


__all__ = ["volatility_regime_strategy"]
