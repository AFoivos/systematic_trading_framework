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
