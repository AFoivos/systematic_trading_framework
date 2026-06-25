from __future__ import annotations

import numpy as np
import pandas as pd

from ._ehlers import (
    as_float_array,
    ensure_unique_columns,
    require_columns,
    resolve_named_col,
    resolve_output_col,
    validate_bool,
    validate_float,
)


def add_instantaneous_trendline(
    df: pd.DataFrame,
    price_col: str = "close",
    alpha: float = 0.07,
    output_col: str | None = None,
    trigger_col: str | None = None,
    add_trigger: bool = True,
) -> pd.DataFrame:
    """
    Add Ehlers' causal instantaneous trendline and optional trigger.
    
    YAML declaration::
    
        features:
          - step: instantaneous_trendline
            params: {}
    
    Required input columns
    ----------------------
    price_col:
        Input column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column name consumed by the component. Default: ``close``.
    alpha:
        Configuration value used by the registered component. Default: ``0.07``.
    output_col:
        Output column name emitted by the component. Default: ``None``.
    trigger_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    add_trigger:
        Configuration value used by the registered component. Default: ``True``.
    """
    require_columns(df, [price_col], feature="instantaneous trendline")
    a = validate_float(alpha, name="alpha", minimum=0.0, maximum=1.0)
    validate_bool(add_trigger, name="add_trigger")
    col = resolve_output_col(output_col, "instantaneous_trendline")
    trigger = resolve_named_col(trigger_col, default=f"{col}_trigger", name="trigger_col")
    if add_trigger:
        ensure_unique_columns([col, trigger], feature="instantaneous trendline")

    out = df.copy()
    values = as_float_array(out[price_col])
    trendline = np.full(values.size, np.nan, dtype=float)
    trigger_values = np.full(values.size, np.nan, dtype=float)

    for idx in range(values.size):
        if not np.isfinite(values[idx]):
            continue
        if idx < 2:
            trendline[idx] = values[idx]
        elif idx < 7:
            sample = values[idx - 2 : idx + 1]
            if np.isfinite(sample).all():
                trendline[idx] = (values[idx] + 2.0 * values[idx - 1] + values[idx - 2]) / 4.0
        else:
            sample = values[idx - 2 : idx + 1]
            if not np.isfinite(sample).all() or not np.isfinite(trendline[idx - 1]) or not np.isfinite(trendline[idx - 2]):
                continue
            trendline[idx] = (
                (a - (a * a) / 4.0) * values[idx]
                + 0.5 * a * a * values[idx - 1]
                - (a - 0.75 * a * a) * values[idx - 2]
                + 2.0 * (1.0 - a) * trendline[idx - 1]
                - (1.0 - a) ** 2 * trendline[idx - 2]
            )
        if idx >= 2 and np.isfinite(trendline[idx]) and np.isfinite(trendline[idx - 2]):
            trigger_values[idx] = 2.0 * trendline[idx] - trendline[idx - 2]

    out[col] = trendline
    if add_trigger:
        out[trigger] = trigger_values
    return out


__all__ = ["add_instantaneous_trendline"]
