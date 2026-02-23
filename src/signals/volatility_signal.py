from __future__ import annotations

import pandas as pd


_ALLOWED_MODES = {"long_only", "short_only", "long_short", "long_short_hold"}


def compute_volatility_regime_signal(
    df: pd.DataFrame,
    vol_col: str,
    quantile: float = 0.5,
    signal_col: str = "volatility_regime_signal",
    mode: str = "long_short_hold",
    causal: bool = True,
) -> pd.DataFrame:
    """
    Long when volatility is at or below the specified quantile,
    short when above (if mode allows shorts).
    If causal=True, quantile threshold is computed with expanding history and shifted by one bar.
    """
    if vol_col not in df.columns:
        raise KeyError(f"vol_col '{vol_col}' not found in DataFrame")
    if not (0.0 < quantile < 1.0):
        raise ValueError("quantile must be between 0 and 1")
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of {_ALLOWED_MODES}")

    out = df.copy()
    vol = out[vol_col].astype(float)
    if causal:
        threshold = vol.expanding(min_periods=1).quantile(quantile).shift(1)
    else:
        threshold = pd.Series(float(vol.quantile(quantile)), index=vol.index)

    out[signal_col] = 0.0
    ready = threshold.notna()
    long_mask = ready & (vol <= threshold)
    short_mask = ready & (vol > threshold)

    if mode in {"long_only", "long_short", "long_short_hold"}:
        out.loc[long_mask, signal_col] = 1.0
    if mode in {"short_only", "long_short", "long_short_hold"}:
        out.loc[short_mask, signal_col] = -1.0

    return out
