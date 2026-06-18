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
    Add Ehlers' causal sinewave and lead sine cycle indicators.

    YAML declaration::

        features:
          - step: sinewave_indicator
            params: {}
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
