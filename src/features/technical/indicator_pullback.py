from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
import zlib

import numpy as np
import pandas as pd

from .atr import compute_atr
from .bollinger import add_bollinger_bands
from .ema import compute_ema
from .macd import compute_macd
from .rsi import compute_rsi
from .stochastic_rsi import compute_stochastic_rsi


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


def _ensure_indicator_dependencies(
    df: pd.DataFrame,
    *,
    open_col: str,
    high_col: str,
    low_col: str,
    close_col: str,
    ema_fast_period: int,
    ema_mid_period: int,
    ema_slow_period: int,
    ema_fast_col: str,
    ema_mid_col: str,
    ema_slow_col: str,
    atr_period: int,
    atr_col: str,
    macd_hist_col: str,
    rsi_period: int,
    rsi_col: str,
    stoch_k_col: str,
    stoch_d_col: str,
    bollinger_bandwidth_col: str,
    bollinger_percent_b_col: str,
) -> pd.DataFrame:
    _require_columns(
        df,
        [open_col, high_col, low_col, close_col],
        owner="indicator_pullback_features",
    )
    out = df
    close = _numeric(out, close_col)
    high = _numeric(out, high_col)
    low = _numeric(out, low_col)

    if ema_fast_col not in out.columns:
        out[ema_fast_col] = compute_ema(close, span=ema_fast_period)
    if ema_mid_col not in out.columns:
        out[ema_mid_col] = compute_ema(close, span=ema_mid_period)
    if ema_slow_col not in out.columns:
        out[ema_slow_col] = compute_ema(close, span=ema_slow_period)
    if atr_col not in out.columns:
        out[atr_col] = compute_atr(high, low, close, window=atr_period, method="wilder")
    if macd_hist_col not in out.columns:
        macd = compute_macd(close, fast=12, slow=26, signal=9)
        out[macd_hist_col] = macd["macd_hist_12_26_9"]
    if rsi_col not in out.columns:
        out[rsi_col] = compute_rsi(close, window=rsi_period, method="wilder")
    if stoch_k_col not in out.columns or stoch_d_col not in out.columns:
        stoch = compute_stochastic_rsi(close)
        if stoch_k_col not in out.columns:
            out[stoch_k_col] = stoch["stoch_rsi_k"]
        if stoch_d_col not in out.columns:
            out[stoch_d_col] = stoch["stoch_rsi_d"]
    if bollinger_bandwidth_col not in out.columns or bollinger_percent_b_col not in out.columns:
        bollinger = add_bollinger_bands(close, window=20, n_std=2.0)
        if bollinger_bandwidth_col not in out.columns:
            out[bollinger_bandwidth_col] = bollinger["bb_width_20_2.0"]
        if bollinger_percent_b_col not in out.columns:
            out[bollinger_percent_b_col] = bollinger["bb_percent_b_20_2.0"]
    return out


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
    Apply the registered ``indicator_pullback`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: indicator_pullback
            params:
              asset: null
              asset_vocab: null
              asset_aliases: null
              open_col: open
              high_col: high
              low_col: low
              close_col: close
              ema_fast_period: 20
              ema_mid_period: 50
              ema_slow_period: 100
              ema_fast_col: null
              ema_mid_col: null
              ema_slow_col: null
              atr_period: 14
              atr_col: null
              atr_pct_col: atr_pct
              atr_pct_rank_window: 100
              macd_hist_col: macd_hist
              rsi_period: 14
              rsi_col: null
              stoch_k_col: stoch_rsi_k
              stoch_d_col: stoch_rsi_d
              bollinger_bandwidth_col: bollinger_bandwidth
              bollinger_percent_b_col: bollinger_percent_b
              realized_vol_windows: [10, 20]
              return_windows: [1, 2, 3, 6]
              rolling_return_windows: [4, 8]
              bb_bandwidth_rank_window: 100
              include_asset_id: true
              inplace: false
            output_cols:
              - configured by atr_col
    
    Required input columns
    ----------------------
    open_col:
        Input dataframe column configured by ``open_col``. Default: ``open``.
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    ema_fast_col:
        Input dataframe column configured by ``ema_fast_col``. Default: ``null``.
    ema_mid_col:
        Input dataframe column configured by ``ema_mid_col``. Default: ``null``.
    ema_slow_col:
        Input dataframe column configured by ``ema_slow_col``. Default: ``null``.
    atr_pct_col:
        Input dataframe column configured by ``atr_pct_col``. Default: ``atr_pct``.
    macd_hist_col:
        Input dataframe column configured by ``macd_hist_col``. Default: ``macd_hist``.
    rsi_col:
        Input dataframe column configured by ``rsi_col``. Default: ``null``.
    stoch_k_col:
        Input dataframe column configured by ``stoch_k_col``. Default: ``stoch_rsi_k``.
    stoch_d_col:
        Input dataframe column configured by ``stoch_d_col``. Default: ``stoch_rsi_d``.
    bollinger_bandwidth_col:
        Input dataframe column configured by ``bollinger_bandwidth_col``. Default: ``bollinger_bandwidth``.
    bollinger_percent_b_col:
        Input dataframe column configured by ``bollinger_percent_b_col``. Default: ``bollinger_percent_b``.
    
    Parameters
    ----------
    asset:
        Configuration parameter accepted by this feature. Default: ``null``.
    asset_vocab:
        Configuration parameter accepted by this feature. Default: ``null``.
    asset_aliases:
        Configuration parameter accepted by this feature. Default: ``null``.
    open_col:
        Input dataframe column configured by ``open_col``. Default: ``open``.
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    ema_fast_period:
        Configuration parameter accepted by this feature. Default: ``20``.
    ema_mid_period:
        Configuration parameter accepted by this feature. Default: ``50``.
    ema_slow_period:
        Configuration parameter accepted by this feature. Default: ``100``.
    ema_fast_col:
        Input dataframe column configured by ``ema_fast_col``. Default: ``null``.
    ema_mid_col:
        Input dataframe column configured by ``ema_mid_col``. Default: ``null``.
    ema_slow_col:
        Input dataframe column configured by ``ema_slow_col``. Default: ``null``.
    atr_period:
        Configuration parameter accepted by this feature. Default: ``14``.
    atr_col:
        Output dataframe column configured by ``atr_col``. Default: ``null``.
    atr_pct_col:
        Input dataframe column configured by ``atr_pct_col``. Default: ``atr_pct``.
    atr_pct_rank_window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``100``.
    macd_hist_col:
        Input dataframe column configured by ``macd_hist_col``. Default: ``macd_hist``.
    rsi_period:
        Configuration parameter accepted by this feature. Default: ``14``.
    rsi_col:
        Input dataframe column configured by ``rsi_col``. Default: ``null``.
    stoch_k_col:
        Input dataframe column configured by ``stoch_k_col``. Default: ``stoch_rsi_k``.
    stoch_d_col:
        Input dataframe column configured by ``stoch_d_col``. Default: ``stoch_rsi_d``.
    bollinger_bandwidth_col:
        Input dataframe column configured by ``bollinger_bandwidth_col``. Default: ``bollinger_bandwidth``.
    bollinger_percent_b_col:
        Input dataframe column configured by ``bollinger_percent_b_col``. Default: ``bollinger_percent_b``.
    realized_vol_windows:
        Trailing lookback or forecast horizon controlling this feature. Default: ``[10, 20]``.
    return_windows:
        Trailing lookback or forecast horizon controlling this feature. Default: ``[1, 2, 3, 6]``.
    rolling_return_windows:
        Trailing lookback or forecast horizon controlling this feature. Default: ``[4, 8]``.
    bb_bandwidth_rank_window:
        Trailing lookback or forecast horizon controlling this feature. Default: ``100``.
    include_asset_id:
        Configuration parameter accepted by this feature. Default: ``true``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
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

    out = df if inplace else df.copy()
    out = _ensure_indicator_dependencies(
        out,
        open_col=open_col,
        high_col=high_col,
        low_col=low_col,
        close_col=close_col,
        ema_fast_period=ema_fast_period,
        ema_mid_period=ema_mid_period,
        ema_slow_period=ema_slow_period,
        ema_fast_col=ema_fast_col,
        ema_mid_col=ema_mid_col,
        ema_slow_col=ema_slow_col,
        atr_period=atr_period,
        atr_col=atr_col,
        macd_hist_col=macd_hist_col,
        rsi_period=rsi_period,
        rsi_col=rsi_col,
        stoch_k_col=stoch_k_col,
        stoch_d_col=stoch_d_col,
        bollinger_bandwidth_col=bollinger_bandwidth_col,
        bollinger_percent_b_col=bollinger_percent_b_col,
    )
    _require_columns(out, required, owner="indicator_pullback_features")

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
