from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.technical.atr import compute_atr
from src.features.technical.ema import compute_ema


def _resolve_returns_series(
    df: pd.DataFrame,
    *,
    price_col: str,
    returns_col: str,
    use_log_returns: bool,
) -> pd.Series:
    if returns_col in df.columns:
        return df[returns_col].astype(float)

    prices = df[price_col].astype(float)
    prev_prices = prices.shift(1)
    ratio = prices / prev_prices.replace(0.0, np.nan)
    if use_log_returns:
        out = np.log(ratio)
        out[ratio <= 0.0] = np.nan
        return pd.Series(out, index=df.index, name=returns_col, dtype=float)
    return pd.Series(ratio - 1.0, index=df.index, name=returns_col, dtype=float)


def _resolve_ema_series(
    df: pd.DataFrame,
    *,
    price_col: str,
    ema_col: str | None,
    ema_window: int,
) -> tuple[pd.Series, str]:
    if ema_col is not None:
        if ema_col not in df.columns:
            raise KeyError(
                f"shock_context ema_col '{ema_col}' not found in DataFrame. "
                "Provide an existing EMA column or omit ema_col to use ema_window fallback."
            )
        return df[ema_col].astype(float), str(ema_col)
    prices = df[price_col].astype(float)
    return compute_ema(prices, span=int(ema_window)).astype(float), f"{price_col}_ema_{int(ema_window)}"


def _resolve_atr_series(
    df: pd.DataFrame,
    *,
    price_col: str,
    high_col: str,
    low_col: str,
    atr_col: str | None,
    atr_window: int,
) -> tuple[pd.Series, str]:
    if atr_col is not None:
        if atr_col not in df.columns:
            raise KeyError(
                f"shock_context atr_col '{atr_col}' not found in DataFrame. "
                "Provide an existing ATR column or omit atr_col to use atr_window fallback."
            )
        return df[atr_col].astype(float), str(atr_col)

    missing = [col for col in (high_col, low_col, price_col) if col not in df.columns]
    if missing:
        raise KeyError(
            "shock_context requires price/high/low columns when atr_col is not provided; "
            f"missing {missing}."
        )
    return (
        compute_atr(
            df[high_col].astype(float),
            df[low_col].astype(float),
            df[price_col].astype(float),
            window=int(atr_window),
            method="wilder",
        ).astype(float),
        f"atr_{int(atr_window)}",
    )


def _compute_horizon_return(
    base_returns: pd.Series,
    *,
    horizon: int,
    use_log_returns: bool,
) -> pd.Series:
    if int(horizon) == 1:
        return base_returns.astype(float)
    if use_log_returns:
        return base_returns.rolling(int(horizon), min_periods=int(horizon)).sum()
    compounded = (1.0 + base_returns.astype(float)).rolling(
        int(horizon),
        min_periods=int(horizon),
    ).apply(np.prod, raw=True)
    return compounded - 1.0


def _rolling_zscore(series: pd.Series, *, window: int) -> pd.Series:
    roll_mean = series.rolling(int(window), min_periods=int(window)).mean()
    roll_std = series.rolling(int(window), min_periods=int(window)).std(ddof=0)
    return (series - roll_mean) / roll_std.replace(0.0, np.nan)


def _bars_since_event(event_mask: pd.Series) -> pd.Series:
    out = np.full(len(event_mask), np.nan, dtype=float)
    last_event_idx: int | None = None
    for idx, is_event in enumerate(event_mask.astype(bool).to_numpy(dtype=bool)):
        if is_event:
            last_event_idx = idx
            out[idx] = 0.0
        elif last_event_idx is not None:
            out[idx] = float(idx - last_event_idx)
    return pd.Series(out, index=event_mask.index, name="bars_since_shock", dtype="float32")


def add_shock_context_features(
    df: pd.DataFrame,
    *,
    price_col: str = "close",
    high_col: str = "high",
    low_col: str = "low",
    returns_col: str = "close_logret",
    ema_col: str | None = None,
    ema_window: int = 24,
    atr_col: str | None = None,
    atr_window: int = 24,
    short_horizon: int = 1,
    medium_horizon: int = 4,
    vol_window: int = 24,
    ret_z_threshold: float = 2.0,
    atr_mult_threshold: float = 1.5,
    distance_from_mean_threshold: float = 1.0,
    post_shock_active_bars: int = 1,
    use_log_returns: bool = True,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Build point-in-time safe shock/reversion context columns from already-available market data.

    The emitted columns are intended for two complementary use-cases:
    - rule-based contrarian baselines via `shock_side_contrarian`
    - meta-label classifiers via `triple_barrier.side_col` + `candidate_col`

    Candidate shocks are event columns, not persistent regimes: they are active only on the bar
    where the shock rule is satisfied.
    """
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame.")
    if int(short_horizon) <= 0:
        raise ValueError("short_horizon must be a positive integer.")
    if int(medium_horizon) <= 0:
        raise ValueError("medium_horizon must be a positive integer.")
    if int(medium_horizon) < int(short_horizon):
        raise ValueError("medium_horizon must be >= short_horizon.")
    if int(vol_window) <= 1:
        raise ValueError("vol_window must be > 1.")
    if int(ema_window) <= 1:
        raise ValueError("ema_window must be > 1.")
    if int(atr_window) <= 1:
        raise ValueError("atr_window must be > 1.")
    if int(post_shock_active_bars) <= 0:
        raise ValueError("post_shock_active_bars must be a positive integer.")
    if float(ret_z_threshold) <= 0.0:
        raise ValueError("ret_z_threshold must be > 0.")
    if float(atr_mult_threshold) <= 0.0:
        raise ValueError("atr_mult_threshold must be > 0.")
    if float(distance_from_mean_threshold) <= 0.0:
        raise ValueError("distance_from_mean_threshold must be > 0.")
    if not isinstance(use_log_returns, bool):
        raise TypeError("use_log_returns must be boolean.")

    out = df if inplace else df.copy()
    prices = out[price_col].astype(float)
    returns = _resolve_returns_series(
        out,
        price_col=price_col,
        returns_col=str(returns_col),
        use_log_returns=bool(use_log_returns),
    ).astype(float)
    ema_series, _ = _resolve_ema_series(
        out,
        price_col=price_col,
        ema_col=ema_col,
        ema_window=int(ema_window),
    )
    atr_series, _ = _resolve_atr_series(
        out,
        price_col=price_col,
        high_col=high_col,
        low_col=low_col,
        atr_col=atr_col,
        atr_window=int(atr_window),
    )
    atr_safe = atr_series.astype(float).where(atr_series.astype(float) > 0.0, other=np.nan)

    short_suffix = f"{int(short_horizon)}h"
    medium_suffix = f"{int(medium_horizon)}h"

    shock_ret_short = _compute_horizon_return(
        returns,
        horizon=int(short_horizon),
        use_log_returns=bool(use_log_returns),
    ).astype(float)
    shock_ret_medium = _compute_horizon_return(
        returns,
        horizon=int(medium_horizon),
        use_log_returns=bool(use_log_returns),
    ).astype(float)
    shock_ret_z_short = _rolling_zscore(shock_ret_short, window=int(vol_window)).astype(float)
    shock_ret_z_medium = _rolling_zscore(shock_ret_medium, window=int(vol_window)).astype(float)

    shock_atr_multiple_short = ((prices - prices.shift(int(short_horizon))) / atr_safe).astype(float)
    shock_atr_multiple_medium = ((prices - prices.shift(int(medium_horizon))) / atr_safe).astype(float)
    shock_distance_ema = ((prices - ema_series.astype(float)) / atr_safe).astype(float)

    use_short = shock_ret_z_short.abs().fillna(-np.inf) >= shock_ret_z_medium.abs().fillna(-np.inf)
    dominant_ret_z = shock_ret_z_short.where(use_short, other=shock_ret_z_medium)
    dominant_atr_multiple = shock_atr_multiple_short.where(use_short, other=shock_atr_multiple_medium)

    strength_components = pd.DataFrame(
        {
            "ret": dominant_ret_z.abs() / float(ret_z_threshold),
            "atr": dominant_atr_multiple.abs() / float(atr_mult_threshold),
            "dist": shock_distance_ema.abs() / float(distance_from_mean_threshold),
        },
        index=out.index,
    )
    shock_strength = strength_components.mean(axis=1)
    shock_strength = shock_strength.where(strength_components.notna().all(axis=1))

    up_candidate = (
        (dominant_ret_z >= float(ret_z_threshold))
        & (dominant_atr_multiple >= float(atr_mult_threshold))
        & (shock_distance_ema >= float(distance_from_mean_threshold))
    )
    down_candidate = (
        (dominant_ret_z <= -float(ret_z_threshold))
        & (dominant_atr_multiple <= -float(atr_mult_threshold))
        & (shock_distance_ema <= -float(distance_from_mean_threshold))
    )

    conflicting = up_candidate & down_candidate
    if bool(conflicting.any()):
        up_candidate = up_candidate & ~conflicting
        down_candidate = down_candidate & ~conflicting

    shock_candidate = (up_candidate | down_candidate).astype(bool)
    shock_side_contrarian = pd.Series(0.0, index=out.index, dtype=float)
    shock_side_contrarian.loc[up_candidate] = -1.0
    shock_side_contrarian.loc[down_candidate] = 1.0
    bars_since_shock = _bars_since_event(pd.Series(shock_candidate, index=out.index))
    active_mask = (
        bars_since_shock.ge(0.0)
        & bars_since_shock.lt(float(int(post_shock_active_bars)))
    )
    shock_side_contrarian_active = (
        shock_side_contrarian.replace(0.0, np.nan)
        .ffill()
        .where(active_mask, 0.0)
        .fillna(0.0)
    )

    out[f"shock_ret_{short_suffix}"] = shock_ret_short.astype("float32")
    out[f"shock_ret_{medium_suffix}"] = shock_ret_medium.astype("float32")
    out[f"shock_ret_z_{short_suffix}"] = shock_ret_z_short.astype("float32")
    out[f"shock_ret_z_{medium_suffix}"] = shock_ret_z_medium.astype("float32")
    out[f"shock_atr_multiple_{short_suffix}"] = shock_atr_multiple_short.astype("float32")
    out[f"shock_atr_multiple_{medium_suffix}"] = shock_atr_multiple_medium.astype("float32")
    out["shock_distance_ema"] = shock_distance_ema.astype("float32")
    out["shock_up_candidate"] = up_candidate.astype("float32")
    out["shock_down_candidate"] = down_candidate.astype("float32")
    out["shock_candidate"] = shock_candidate.astype("float32")
    out["shock_side_contrarian"] = shock_side_contrarian.astype("float32")
    out["shock_side_contrarian_active"] = shock_side_contrarian_active.astype("float32")
    out["shock_active_window"] = active_mask.astype("float32")
    out["shock_strength"] = shock_strength.astype("float32")
    out["bars_since_shock"] = bars_since_shock
    return out


__all__ = ["add_shock_context_features"]
