from __future__ import annotations

import pandas as pd


def add_macd_features(
    df: pd.DataFrame,
    price_col: str = "close",
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``macd`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: macd
            params:
              price_col: close
              fast: 12
              slow: 26
              signal: 9
              inplace: false
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    fast:
        Trailing lookback or forecast horizon controlling this feature. Default: ``12``.
    slow:
        Trailing lookback or forecast horizon controlling this feature. Default: ``26``.
    signal:
        Configuration parameter accepted by this feature. Default: ``9``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    """
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")
    out = df if inplace else df.copy()
    close = out[price_col].astype(float)
    return out.join(compute_macd(close, fast=fast, slow=slow, signal=signal))


def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """
    Compute the ``compute_macd`` feature value.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: compute_macd
            params:
              close: <required>
              fast: 12
              slow: 26
              signal: 9
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    close:
        Configuration parameter accepted by this feature.
    fast:
        Trailing lookback or forecast horizon controlling this feature. Default: ``12``.
    slow:
        Trailing lookback or forecast horizon controlling this feature. Default: ``26``.
    signal:
        Configuration parameter accepted by this feature. Default: ``9``.
    """
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    macd_hist = macd - macd_signal
    return pd.DataFrame(
        {
            f"macd_{fast}_{slow}": macd,
            f"macd_signal_{signal}": macd_signal,
            f"macd_hist_{fast}_{slow}_{signal}": macd_hist,
        }
    )

__all__ = ["compute_macd", "add_macd_features"]
