from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.helpers.common import require_columns


def add_atr_distance_features(
    df: pd.DataFrame,
    *,
    atr_col: str = "atr_14",
    pairs: list[dict[str, str]],
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``atr_distance`` normalization helper transformation.
    
    This normalization helper uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        normalizations:
          atr_distance:
            params:
              atr_col: atr_14
              pairs: <required>
              inplace: false
              base_col: <configured>
              name: <configured>
              ref_col: <configured>
          outputs:
            - atr_14
    
    Required input columns
    ----------------------
    pairs:
        List of mappings that define generated pairwise distance columns.
    base_col:
        Input dataframe column configured by ``base_col``. Default: ``<configured>``.
    ref_col:
        Input dataframe column configured by ``ref_col``. Default: ``<configured>``.
    
    Parameters
    ----------
    atr_col:
        Output dataframe column configured by ``atr_col``. Default: ``atr_14``.
    pairs:
        List of mappings that define generated pairwise distance columns.
    inplace:
        Boolean switch controlling optional normalization helper behavior. Default: ``false``.
    base_col:
        Input dataframe column configured by ``base_col``. Default: ``<configured>``.
    name:
        Configuration parameter accepted by this normalization helper. Default: ``<configured>``.
    ref_col:
        Input dataframe column configured by ``ref_col``. Default: ``<configured>``.
    """
    require_columns(df, [atr_col], owner="ATR distance normalization")
    out = df if inplace else df.copy()
    atr = out[atr_col].replace(0, np.nan).astype(float)

    for idx, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            raise TypeError(f"pairs[{idx}] must be a mapping.")
        name = pair.get("name")
        base_col = pair.get("base_col")
        ref_col = pair.get("ref_col")
        if not all(isinstance(value, str) and value.strip() for value in (name, base_col, ref_col)):
            raise ValueError(f"pairs[{idx}] must define name, base_col, and ref_col as non-empty strings.")
        require_columns(out, [str(base_col), str(ref_col)], owner="ATR distance normalization")
        out[str(name)] = (out[str(base_col)].astype(float) - out[str(ref_col)].astype(float)) / atr

    return out


__all__ = ["add_atr_distance_features"]
