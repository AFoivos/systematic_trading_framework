from __future__ import annotations

import pandas as pd


def add_bollinger_features(
    df: pd.DataFrame,
    price_col: str = "close",
    window: int = 20,
    n_std: float = 2.0,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``bollinger`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: bollinger
            params:
              price_col: close
              window: 20
              n_std: 2.0
              inplace: false
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``20``.
    n_std:
        Configuration parameter accepted by this feature. Default: ``2.0``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    """
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")
    out = df if inplace else df.copy()
    close = out[price_col].astype(float)
    return out.join(add_bollinger_bands(close, window=window, n_std=n_std))


def add_bollinger_bands(close: pd.Series, window: int = 20, n_std: float = 2.0) -> pd.DataFrame:
    """
    Apply the registered ``bollinger_bands`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: bollinger_bands
            params:
              close: <required>
              window: 20
              n_std: 2.0
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    close:
        Configuration parameter accepted by this feature.
    window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``20``.
    n_std:
        Configuration parameter accepted by this feature. Default: ``2.0``.
    """
    ma = close.rolling(window=window, min_periods=window).mean()
    sd = close.rolling(window=window, min_periods=window).std(ddof=0)
    upper = ma + n_std * sd
    lower = ma - n_std * sd
    band_width = (upper - lower) / ma
    percent_b = (close - lower) / (upper - lower)
    return pd.DataFrame(
        {
            f"bb_ma_{window}": ma,
            f"bb_upper_{window}_{n_std}": upper,
            f"bb_lower_{window}_{n_std}": lower,
            f"bb_width_{window}_{n_std}": band_width,
            f"bb_percent_b_{window}_{n_std}": percent_b,
        }
    )

__all__ = ["add_bollinger_bands", "add_bollinger_features"]
