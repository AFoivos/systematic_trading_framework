from __future__ import annotations

from typing import Iterable, Sequence

import pandas as pd


def add_lagged_features(
    df: pd.DataFrame,
    cols: Iterable[str],
    lags: Sequence[int] = (1, 2, 5),
    prefix: str = "lag",
) -> pd.DataFrame:
    """
    Apply the registered ``lags`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: lags
            params:
              cols: <required>
              lags: [1, 2, 5]
              prefix: lag
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    cols:
        Configuration parameter accepted by this feature.
    lags:
        Configuration parameter accepted by this feature. Default: ``[1, 2, 5]``.
    prefix:
        Configuration parameter accepted by this feature. Default: ``lag``.
    """

    out = df.copy()
    for col in cols:
        if col not in out.columns:
            raise KeyError(f"Column '{col}' not found for lagging")
        for lag in lags:
            out[f"{prefix}_{col}_{lag}"] = out[col].shift(lag)
    return out
