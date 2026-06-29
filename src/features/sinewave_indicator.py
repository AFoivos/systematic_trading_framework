from __future__ import annotations

import numpy as np
import pandas as pd

from ._ehlers import (
    as_float_array,
    compute_mesa_components,
    ensure_unique_columns,
    require_columns,
    resolve_named_col,
    resolve_output_col,
    validate_float,
)


def add_sinewave_indicator(
    df: pd.DataFrame,
    price_col: str = "close",
    lead_degrees: float = 45.0,
    output_col: str | None = None,
    lead_output_col: str | None = None,
) -> pd.DataFrame:
    """
    Apply the registered ``sinewave_indicator`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: sinewave_indicator
            params:
              price_col: close
              lead_degrees: 45.0
              output_col: null
              lead_output_col: null
            output_cols:
              - configured by output_col
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    lead_output_col:
        Input dataframe column configured by ``lead_output_col``. Default: ``null``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    lead_degrees:
        Configuration parameter accepted by this feature. Default: ``45.0``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    lead_output_col:
        Input dataframe column configured by ``lead_output_col``. Default: ``null``.
    """
    require_columns(df, [price_col], feature="sinewave indicator")
    lead = validate_float(lead_degrees, name="lead_degrees")
    sine_col = resolve_output_col(output_col, "sinewave")
    lead_col = resolve_named_col(lead_output_col, default="lead_sinewave", name="lead_output_col")
    ensure_unique_columns([sine_col, lead_col], feature="sinewave indicator")

    out = df.copy()
    phase = compute_mesa_components(as_float_array(out[price_col]))["phase"]
    out[sine_col] = np.sin(np.deg2rad(phase))
    out[lead_col] = np.sin(np.deg2rad(phase + lead))
    return out


__all__ = ["add_sinewave_indicator"]
