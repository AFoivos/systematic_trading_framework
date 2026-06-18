from __future__ import annotations

import pandas as pd


def add_ppo_features(
    df: pd.DataFrame,
    price_col: str = "close",
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    ppo_col: str | None = None,
    ppo_signal_col: str | None = None,
    ppo_hist_col: str | None = None,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``ppo`` feature transformation.

    YAML declaration::

        features:
          - step: ppo
            params: {}
    """
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")
    out = df if inplace else df.copy()
    close = out[price_col].astype(float)
    return out.join(
        compute_ppo(
            close,
            fast=fast,
            slow=slow,
            signal=signal,
            ppo_col=ppo_col,
            ppo_signal_col=ppo_signal_col,
            ppo_hist_col=ppo_hist_col,
        )
    )


def compute_ppo(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    *,
    ppo_col: str | None = None,
    ppo_signal_col: str | None = None,
    ppo_hist_col: str | None = None,
) -> pd.DataFrame:
    provided_output_cols = (ppo_col, ppo_signal_col, ppo_hist_col)
    if any(col is not None and (not isinstance(col, str) or not col.strip()) for col in provided_output_cols):
        raise ValueError("PPO output columns must be non-empty strings.")
    output_cols = (
        ppo_col or f"ppo_{fast}_{slow}",
        ppo_signal_col or f"ppo_signal_{signal}",
        ppo_hist_col or f"ppo_hist_{fast}_{slow}_{signal}",
    )
    if len(set(output_cols)) != len(output_cols):
        raise ValueError("PPO output columns must be unique.")

    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    ppo = (ema_fast - ema_slow) / ema_slow
    ppo_signal = ppo.ewm(span=signal, adjust=False).mean()
    ppo_hist = ppo - ppo_signal
    return pd.DataFrame(
        {
            output_cols[0]: ppo,
            output_cols[1]: ppo_signal,
            output_cols[2]: ppo_hist,
        }
    )

__all__ = ["compute_ppo", "add_ppo_features"]
