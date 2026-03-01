from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd


def compute_true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """True range as max of (high-low, |high-prev_close|, |low-prev_close|)."""
    prev_close = close.shift(1)
    ranges = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    )
    tr = ranges.max(axis=1)
    tr.name = "true_range"
    return tr


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 14,
    method: str = "wilder",
) -> pd.Series:
    """Average True Range (ATR). method: 'wilder' (EWMA) or 'simple' (SMA)."""
    tr = compute_true_range(high, low, close)
    if method == "wilder":
        atr = tr.ewm(alpha=1 / window, adjust=False).mean()
    elif method == "simple":
        atr = tr.rolling(window=window, min_periods=window).mean()
    else:
        raise ValueError("method must be 'wilder' or 'simple'")
    atr.name = f"atr_{window}"
    return atr


def add_bollinger_bands(
    close: pd.Series,
    window: int = 20,
    n_std: float = 2.0,
) -> pd.DataFrame:
    """Bollinger bands and derived features: upper, lower, band_width, percent_b."""
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


def compute_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """MACD line, signal line, histogram."""
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


def compute_ppo(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Percentage Price Oscillator: normalized MACD."""
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


def compute_roc(
    close: pd.Series,
    window: int = 10,
) -> pd.Series:
    """Rate of Change: (P_t / P_{t-w}) - 1."""
    roc = close / close.shift(window) - 1.0
    roc.name = f"roc_{window}"
    return roc


def compute_volume_zscore(
    volume: pd.Series,
    window: int = 20,
) -> pd.Series:
    """Rolling z-score of volume."""
    mean = volume.rolling(window=window, min_periods=window).mean()
    std = volume.rolling(window=window, min_periods=window).std(ddof=0)
    z = (volume - mean) / std.replace(0, np.nan)
    z.name = f"volume_z_{window}"
    return z


def compute_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 14,
) -> pd.DataFrame:
    """ADX with DI+, DI- using Wilder smoothing."""
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    tr = compute_true_range(high, low, close)
    atr = tr.ewm(alpha=1 / window, adjust=False).mean()

    plus_di = 100 * (plus_dm.ewm(alpha=1 / window, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / window, adjust=False).mean() / atr)

    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    adx = dx.ewm(alpha=1 / window, adjust=False).mean()

    return pd.DataFrame(
        {
            f"plus_di_{window}": plus_di,
            f"minus_di_{window}": minus_di,
            f"adx_{window}": adx,
        }
    )


def compute_mfi(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    window: int = 14,
) -> pd.Series:
    """Money Flow Index (uses typical price * volume)."""
    typical_price = (high + low + close) / 3.0
    raw_flow = typical_price * volume
    pos_flow = raw_flow.where(typical_price.diff() > 0, 0.0)
    neg_flow = raw_flow.where(typical_price.diff() < 0, 0.0)

    pos_sum = pos_flow.rolling(window=window, min_periods=window).sum()
    neg_sum = neg_flow.rolling(window=window, min_periods=window).sum()

    mfr = pos_sum / neg_sum.replace(0, np.nan)
    mfi = 100 - (100 / (1 + mfr))
    mfi = mfi.where(~((neg_sum == 0.0) & (pos_sum > 0.0)), other=100.0)
    mfi = mfi.where(~((pos_sum == 0.0) & (neg_sum > 0.0)), other=0.0)
    mfi.name = f"mfi_{window}"
    return mfi


def add_indicator_features(
    df: pd.DataFrame,
    price_col: str = "close",
    high_col: str = "high",
    low_col: str = "low",
    volume_col: str = "volume",
    bb_window: int = 20,
    bb_nstd: float = 2.0,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    ppo_fast: int = 12,
    ppo_slow: int = 26,
    ppo_signal: int = 9,
    roc_windows: Sequence[int] = (10, 20),
    atr_window: int = 14,
    adx_window: int = 14,
    vol_z_window: int = 20,
    include_mfi: bool = True,
) -> pd.DataFrame:
    """
    Add a bundle of classic indicators to an OHLCV dataframe.
    """
    missing = [c for c in (price_col, high_col, low_col, volume_col) if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for indicators: {missing}")

    out = df.copy()
    close = out[price_col].astype(float)
    high = out[high_col].astype(float)
    low = out[low_col].astype(float)
    vol = out[volume_col].astype(float)

    bb = add_bollinger_bands(close, window=bb_window, n_std=bb_nstd)
    out = out.join(bb)

    out = out.join(compute_macd(close, fast=macd_fast, slow=macd_slow, signal=macd_signal))
    out = out.join(compute_ppo(close, fast=ppo_fast, slow=ppo_slow, signal=ppo_signal))

    for w in roc_windows:
        out[f"roc_{w}"] = compute_roc(close, window=w)

    out[f"atr_{atr_window}"] = compute_atr(high, low, close, window=atr_window)
    out[f"atr_over_price_{atr_window}"] = out[f"atr_{atr_window}"] / close

    adx_df = compute_adx(high, low, close, window=adx_window)
    out = out.join(adx_df)

    out[f"volume_z_{vol_z_window}"] = compute_volume_zscore(vol, window=vol_z_window)
    out[f"volume_over_atr_{atr_window}"] = vol / out[f"atr_{atr_window}"]

    if include_mfi:
        out[f"mfi_{atr_window}"] = compute_mfi(high, low, close, vol, window=atr_window)

    return out
