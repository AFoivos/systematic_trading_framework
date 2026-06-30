from __future__ import annotations

import numpy as np
import pandas as pd

from ._ehlers import as_float_array, compute_mesa_components, require_columns, resolve_output_col


_PHASE_UNIT_ALIASES = {
    "degrees": "degrees",
    "degree": "degrees",
    "deg": "degrees",
    "radians": "radians",
    "radian": "radians",
    "rad": "radians",
}


def _resolve_phase_unit(unit: str) -> str:
    if not isinstance(unit, str) or not unit.strip():
        raise ValueError("unit must be one of: degrees, radians.")
    normalized = unit.strip().lower()
    if normalized not in _PHASE_UNIT_ALIASES:
        raise ValueError("unit must be one of: degrees, radians.")
    return _PHASE_UNIT_ALIASES[normalized]


def add_dominant_cycle_phase(
    df: pd.DataFrame,
    price_col: str = "close",
    output_col: str | None = None,
    unit: str = "degrees",
) -> pd.DataFrame:
    """
    Apply the registered ``dominant_cycle_phase`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: dominant_cycle_phase
            params:
              price_col: close
              output_col: null
              unit: degrees
            output_cols:
              - configured by output_col
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    unit:
        Output unit for the phase angle. Use ``degrees`` for values in
        ``[0, 360)`` or ``radians`` for values in ``[0, 2*pi)``.
    """
    require_columns(df, [price_col], feature="dominant cycle phase")
    col = resolve_output_col(output_col, "dominant_cycle_phase")
    phase_unit = _resolve_phase_unit(unit)

    out = df.copy()
    components = compute_mesa_components(as_float_array(out[price_col]))
    phase = components["phase"]
    if phase_unit == "radians":
        phase = np.deg2rad(phase)
    out[col] = phase
    return out


__all__ = ["add_dominant_cycle_phase"]
