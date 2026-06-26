from __future__ import annotations

import pandas as pd


def compute_ema(prices: pd.Series, span: int, adjust: bool = False) -> pd.Series:
    """
    Compute the ``compute_ema`` feature value.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: compute_ema
            params:
              span: <required>
              adjust: false
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    span:
        Configuration parameter accepted by this feature.
    adjust:
        Configuration parameter accepted by this feature. Default: ``false``.
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series")
    ema = prices.ewm(span=span, adjust=adjust).mean()
    ema.name = f"{prices.name}_ema_{span}"
    return ema


__all__ = ["compute_ema"]
