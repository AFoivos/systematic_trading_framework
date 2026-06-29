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


def add_cyber_cycle(
    df: pd.DataFrame,
    price_col: str = "close",
    alpha: float = 0.07,
    output_col: str | None = None,
    trigger_col: str | None = None,
    add_trigger: bool = True,
) -> pd.DataFrame:
    """
    Apply the registered ``cyber_cycle`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: cyber_cycle
            params:
              price_col: close
              alpha: 0.07
              output_col: null
              trigger_col: null
              add_trigger: true
            output_cols:
              - configured by output_col
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    trigger_col:
        Input dataframe column configured by ``trigger_col``. Default: ``null``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    alpha:
        Configuration parameter accepted by this feature. Default: ``0.07``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    trigger_col:
        Input dataframe column configured by ``trigger_col``. Default: ``null``.
    add_trigger:
        Boolean switch controlling optional feature behavior. Default: ``true``.
    """
    require_columns(df, [price_col], feature="Cyber Cycle")
    a = validate_float(alpha, name="alpha", minimum=0.0, maximum=1.0)
    validate_bool(add_trigger, name="add_trigger")
    col = resolve_output_col(output_col, "cyber_cycle")
    trigger = resolve_named_col(trigger_col, default=f"{col}_trigger", name="trigger_col")
    if add_trigger:
        ensure_unique_columns([col, trigger], feature="Cyber Cycle")

    out = df.copy()
    values = as_float_array(out[price_col])
    smooth = np.full(values.size, np.nan, dtype=float)
    cycle = np.full(values.size, np.nan, dtype=float)

    for idx in range(values.size):
        if idx < 3:
            if np.isfinite(values[idx]):
                smooth[idx] = values[idx]
            continue
        sample = values[idx - 3 : idx + 1]
        if np.isfinite(sample).all():
            smooth[idx] = (values[idx] + 2.0 * values[idx - 1] + 2.0 * values[idx - 2] + values[idx - 3]) / 6.0

    for idx in range(values.size):
        if not np.isfinite(values[idx]):
            continue
        if idx < 2:
            cycle[idx] = 0.0
        elif idx < 7:
            sample = values[idx - 2 : idx + 1]
            if np.isfinite(sample).all():
                cycle[idx] = (values[idx] - 2.0 * values[idx - 1] + values[idx - 2]) / 4.0
        else:
            sample = smooth[idx - 2 : idx + 1]
            if not np.isfinite(sample).all() or not np.isfinite(cycle[idx - 1]) or not np.isfinite(cycle[idx - 2]):
                continue
            cycle[idx] = (
                (1.0 - 0.5 * a) ** 2 * (smooth[idx] - 2.0 * smooth[idx - 1] + smooth[idx - 2])
                + 2.0 * (1.0 - a) * cycle[idx - 1]
                - (1.0 - a) ** 2 * cycle[idx - 2]
            )

    out[col] = cycle
    if add_trigger:
        out[trigger] = pd.Series(cycle, index=out.index).shift(1)
    return out


__all__ = ["add_cyber_cycle"]
