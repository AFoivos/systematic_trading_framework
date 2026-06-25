from __future__ import annotations

import numpy as np
import pandas as pd

from ._ehlers import as_float_array, require_columns, resolve_output_col, validate_bool, validate_float


def add_laguerre_rsi(
    df: pd.DataFrame,
    price_col: str = "close",
    gamma: float = 0.5,
    output_col: str | None = None,
    as_percent: bool = False,
) -> pd.DataFrame:
    """
    Add Ehlers' causal Laguerre RSI oscillator.
    
    YAML declaration::
    
        features:
          - step: laguerre_rsi
            params: {}
    
    Required input columns
    ----------------------
    price_col:
        Input column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column name consumed by the component. Default: ``close``.
    gamma:
        Configuration value used by the registered component. Default: ``0.5``.
    output_col:
        Output column name emitted by the component. Default: ``None``.
    as_percent:
        Configuration value used by the registered component. Default: ``False``.
    """
    require_columns(df, [price_col], feature="Laguerre RSI")
    resolved_gamma = validate_float(gamma, name="gamma", minimum=0.0, maximum=1.0)
    percent = validate_bool(as_percent, name="as_percent")
    col = resolve_output_col(output_col, "laguerre_rsi")

    out = df.copy()
    values = as_float_array(out[price_col])
    l0 = np.full(values.size, np.nan, dtype=float)
    l1 = np.full(values.size, np.nan, dtype=float)
    l2 = np.full(values.size, np.nan, dtype=float)
    l3 = np.full(values.size, np.nan, dtype=float)
    rsi = np.full(values.size, np.nan, dtype=float)

    prev_l0 = prev_l1 = prev_l2 = prev_l3 = np.nan
    for idx, price in enumerate(values):
        if not np.isfinite(price):
            continue
        if not np.isfinite(prev_l0):
            prev_l0 = prev_l1 = prev_l2 = prev_l3 = price

        l0[idx] = (1.0 - resolved_gamma) * price + resolved_gamma * prev_l0
        l1[idx] = -resolved_gamma * l0[idx] + prev_l0 + resolved_gamma * prev_l1
        l2[idx] = -resolved_gamma * l1[idx] + prev_l1 + resolved_gamma * prev_l2
        l3[idx] = -resolved_gamma * l2[idx] + prev_l2 + resolved_gamma * prev_l3

        cu = 0.0
        cd = 0.0
        for first, second in ((l0[idx], l1[idx]), (l1[idx], l2[idx]), (l2[idx], l3[idx])):
            if first >= second:
                cu += first - second
            else:
                cd += second - first
        total = cu + cd
        rsi[idx] = cu / total if total > 0.0 else 0.0

        prev_l0, prev_l1, prev_l2, prev_l3 = l0[idx], l1[idx], l2[idx], l3[idx]

    out[col] = rsi * 100.0 if percent else rsi
    return out


__all__ = ["add_laguerre_rsi"]
