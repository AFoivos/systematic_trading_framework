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
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")
    out = df if inplace else df.copy()
    close = out[price_col].astype(float)
    return out.join(compute_macd(close, fast=fast, slow=slow, signal=signal))


def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
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
