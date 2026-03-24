from __future__ import annotations

import pandas as pd


def compute_ppo(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    ppo = (ema_fast - ema_slow) / ema_slow
    ppo_signal = ppo.ewm(span=signal, adjust=False).mean()
    ppo_hist = ppo - ppo_signal
    return pd.DataFrame(
        {
            f"ppo_{fast}_{slow}": ppo,
            f"ppo_signal_{signal}": ppo_signal,
            f"ppo_hist_{fast}_{slow}_{signal}": ppo_hist,
        }
    )


__all__ = ["compute_ppo"]
