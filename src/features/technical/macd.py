from __future__ import annotations

import pandas as pd


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


__all__ = ["compute_macd"]
