from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
import zlib

import numpy as np
import pandas as pd


def _require_columns(df: pd.DataFrame, columns: Sequence[str], *, owner: str) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for {owner}: {missing}")


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df[column], errors="coerce").astype(float)


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or int(value) <= 0:
        raise ValueError(f"{field} must be a positive integer.")
    return int(value)


def _resolve_windows(values: Sequence[int] | None, *, default: tuple[int, ...], field: str) -> list[int]:
    raw_values = list(values) if values is not None else list(default)
    resolved: list[int] = []
    for raw in raw_values:
        value = _positive_int(raw, field=field)
        if value not in resolved:
            resolved.append(value)
    if not resolved:
        raise ValueError(f"{field} must not be empty.")
    return resolved


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.replace(0.0, np.nan)


def _last_pct_rank(values: np.ndarray) -> float:
    current = float(values[-1])
    if not np.isfinite(current):
        return np.nan
    valid = values[np.isfinite(values)]
    if valid.size == 0:
        return np.nan
    return float((valid <= current).sum() / valid.size)


def _rolling_pct_rank(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).apply(_last_pct_rank, raw=True)


def _normalize_asset_name(asset: str) -> str:
    return str(asset).strip().upper()


def _stable_asset_id(
    asset: str | None,
    *,
    asset_vocab: Sequence[str] | None,
    asset_aliases: Mapping[str, str] | None,
) -> float:
    if asset is None:
        return np.nan

    aliases = {
        _normalize_asset_name(key): _normalize_asset_name(value)
        for key, value in dict(asset_aliases or {}).items()
    }
    normalized = aliases.get(_normalize_asset_name(asset), _normalize_asset_name(asset))
    if asset_vocab is not None:
        vocab = [_normalize_asset_name(item) for item in asset_vocab]
        if normalized in vocab:
            return float(vocab.index(normalized))

    # Avoid Python's randomized hash and keep the value numeric for model use.
    return float(zlib.crc32(normalized.encode("utf-8")) % 1_000_000)


def add_indicator_pullback_features(
    df: pd.DataFrame,
    *,
    asset: str | None = None,
    asset_vocab: Sequence[str] | None = None,
    asset_aliases: Mapping[str, str] | None = None,
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    ema_fast_period: int = 20,
    ema_mid_period: int = 50,
    ema_slow_period: int = 100,
    ema_fast_col: str | None = None,
    ema_mid_col: str | None = None,
    ema_slow_col: str | None = None,
    atr_period: int = 14,
    atr_col: str | None = None,
    atr_pct_col: str = "atr_pct",
    atr_pct_rank_window: int = 100,
    macd_hist_col: str = "macd_hist",
    rsi_period: int = 14,
    rsi_col: str | None = None,
    stoch_k_col: str = "stoch_rsi_k",
    stoch_d_col: str = "stoch_rsi_d",
    bollinger_bandwidth_col: str = "bollinger_bandwidth",
    bollinger_percent_b_col: str = "bollinger_percent_b",
    realized_vol_windows: Sequence[int] | None = (10, 20),
    return_windows: Sequence[int] | None = (1, 2, 3, 6),
    rolling_return_windows: Sequence[int] | None = (4, 8),
    bb_bandwidth_rank_window: int | None = 100,
    include_asset_id: bool = True,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Add causal derived features used by the indicator/model adaptive pullback strategy.

    All rolling statistics use the current row and historical rows only. The function does not
    shift features forward and does not inspect future bars.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    ema_fast_period = _positive_int(ema_fast_period, field="ema_fast_period")
    ema_mid_period = _positive_int(ema_mid_period, field="ema_mid_period")
    ema_slow_period = _positive_int(ema_slow_period, field="ema_slow_period")
    atr_period = _positive_int(atr_period, field="atr_period")
    atr_pct_rank_window = _positive_int(atr_pct_rank_window, field="atr_pct_rank_window")
    rsi_period = _positive_int(rsi_period, field="rsi_period")
    if bb_bandwidth_rank_window is not None:
        bb_bandwidth_rank_window = _positive_int(
            bb_bandwidth_rank_window,
            field="bb_bandwidth_rank_window",
        )

    ema_fast_col = str(ema_fast_col or f"ema_{ema_fast_period}")
    ema_mid_col = str(ema_mid_col or f"ema_{ema_mid_period}")
    ema_slow_col = str(ema_slow_col or f"ema_{ema_slow_period}")
    atr_col = str(atr_col or f"atr_{atr_period}")
    rsi_col = str(rsi_col or f"rsi_{rsi_period}")

    required = [
        open_col,
        high_col,
        low_col,
        close_col,
        ema_fast_col,
        ema_mid_col,
        ema_slow_col,
        atr_col,
        macd_hist_col,
        rsi_col,
        stoch_k_col,
        stoch_d_col,
        bollinger_bandwidth_col,
        bollinger_percent_b_col,
    ]
    _require_columns(df, required, owner="indicator_pullback_features")

    out = df if inplace else df.copy()
    open_ = _numeric(out, open_col)
    high = _numeric(out, high_col)
    low = _numeric(out, low_col)
    close = _numeric(out, close_col)
    ema_fast = _numeric(out, ema_fast_col)
    ema_mid = _numeric(out, ema_mid_col)
    ema_slow = _numeric(out, ema_slow_col)
    atr = _numeric(out, atr_col)
    macd_hist = _numeric(out, macd_hist_col)
    rsi = _numeric(out, rsi_col)
    stoch_k = _numeric(out, stoch_k_col)
    stoch_d = _numeric(out, stoch_d_col)
    bb_bandwidth = _numeric(out, bollinger_bandwidth_col)

    out[f"ema_slope_{ema_fast_period}"] = (ema_fast - ema_fast.shift(1)).astype("float32")
    out[f"ema_slope_{ema_mid_period}"] = (ema_mid - ema_mid.shift(1)).astype("float32")

    alignment = pd.Series(0, index=out.index, dtype="int8")
    alignment.loc[ema_fast.gt(ema_mid) & ema_mid.gt(ema_slow)] = 1
    alignment.loc[ema_fast.lt(ema_mid) & ema_mid.lt(ema_slow)] = -1
    out["ema_alignment_score"] = alignment.astype("int8")

    out["macd_hist_slope"] = (macd_hist - macd_hist.shift(1)).astype("float32")
    out[f"rsi_{rsi_period}_slope"] = (rsi - rsi.shift(1)).astype("float32")
    out["stoch_rsi_cross_up"] = (
        stoch_k.shift(1).le(stoch_d.shift(1)) & stoch_k.gt(stoch_d)
    ).fillna(False).astype("int8")
    out["stoch_rsi_cross_down"] = (
        stoch_k.shift(1).ge(stoch_d.shift(1)) & stoch_k.lt(stoch_d)
    ).fillna(False).astype("int8")

    out[atr_pct_col] = _safe_divide(atr, close).astype("float32")
    out[f"{atr_pct_col}_rank_{atr_pct_rank_window}"] = _rolling_pct_rank(
        out[atr_pct_col].astype(float),
        atr_pct_rank_window,
    ).astype("float32")

    if bb_bandwidth_rank_window is not None:
        out[f"bollinger_bandwidth_rank_{bb_bandwidth_rank_window}"] = _rolling_pct_rank(
            bb_bandwidth,
            bb_bandwidth_rank_window,
        ).astype("float32")

    candle_range = (high - low).replace(0.0, np.nan)
    body = close - open_
    out["body_ratio"] = _safe_divide(body.abs(), candle_range).astype("float32")
    out["upper_wick_ratio"] = _safe_divide(high - pd.concat([open_, close], axis=1).max(axis=1), candle_range).astype("float32")
    out["lower_wick_ratio"] = _safe_divide(pd.concat([open_, close], axis=1).min(axis=1) - low, candle_range).astype("float32")
    out["close_location"] = _safe_divide(close - low, candle_range).astype("float32")
    out["range_to_atr"] = _safe_divide(candle_range, atr).astype("float32")
    out[f"distance_from_ema{ema_fast_period}_atr"] = _safe_divide((close - ema_fast).abs(), atr).astype("float32")
    out[f"distance_from_ema{ema_mid_period}_atr"] = _safe_divide((close - ema_mid).abs(), atr).astype("float32")

    for window in _resolve_windows(return_windows, default=(1, 2, 3, 6), field="return_windows"):
        values = (close / close.shift(window) - 1.0).astype("float32")
        out[f"return_{window}"] = values
        out[f"ret_{window}"] = values
    for window in _resolve_windows(
        rolling_return_windows,
        default=(4, 8),
        field="rolling_return_windows",
    ):
        out[f"rolling_return_{window}"] = (close / close.shift(window) - 1.0).astype("float32")

    return_1 = out["return_1"].astype(float) if "return_1" in out.columns else close.pct_change()
    for window in _resolve_windows(
        realized_vol_windows,
        default=(10, 20),
        field="realized_vol_windows",
    ):
        out[f"realized_vol_{window}"] = (
            return_1.rolling(window=window, min_periods=window).std(ddof=0).astype("float32")
        )

    if include_asset_id:
        out["asset_id"] = np.float32(
            _stable_asset_id(asset, asset_vocab=asset_vocab, asset_aliases=asset_aliases)
        )

    return out


__all__ = ["add_indicator_pullback_features"]
