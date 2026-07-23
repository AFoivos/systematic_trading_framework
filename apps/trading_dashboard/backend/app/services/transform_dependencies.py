from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Any, TypeVar

import pandas as pd

from src.features import (
    add_adx_features,
    add_atr_features,
    add_close_returns,
    add_multi_timeframe_features,
    add_price_momentum_features,
    add_regime_context_features,
    add_return_momentum_features,
    add_roc_features,
    add_rsi_features,
    add_session_context_features,
    add_stochastic_features,
    add_stochastic_rsi_features,
    add_volatility_features,
    add_vwap_features,
)
from src.features.helpers import compute_ratio, compute_rms
from src.features.technical.ema import compute_ema
from src.features.technical.ppo import add_ppo_features
from src.features.technical.trend import add_trend_features, add_trend_regime_features
from src.features.transforms import compute_rolling_zscore_transform
from src.signals import roc_long_only_conditions_signal


T = TypeVar("T")

_COLUMN_TOKEN = re.compile(r"'([A-Za-z_][A-Za-z0-9_.-]*)'")
_LAG = re.compile(r"^lag_(.+)_(\d+)$")
_VOL_ROLLING = re.compile(r"^vol_rolling_(\d+)$")
_VOL_EWMA = re.compile(r"^vol_ewma_(\d+)$")
_ATR = re.compile(r"^(?:atr|atr_over_price)_(\d+)$")
_ADX = re.compile(r"^(?:adx|plus_di|minus_di)_(\d+)$")
_RSI = re.compile(r"^close_rsi_(\d+)$")
_ROC = re.compile(r"^roc_(\d+)$")
_PRICE_MOMENTUM = re.compile(r"^close_mom_(\d+)$")
_RETURN_MOMENTUM = re.compile(r"^(close_(?:logret|ret))_mom_(\d+)$")
_SMA = re.compile(r"^close_(?:over_)?sma_(\d+)$")
_EMA = re.compile(r"^close_(?:over_)?ema_(\d+)$")
_EMA_ALIAS = re.compile(r"^ema_(\d+)$")
_STOCHASTIC = re.compile(r"^close_stoch_[kd]_(\d+)$")
_REGIME = re.compile(r"^regime_(?:vol_ratio|high_vol_state|low_vol_state|vol_ratio_z|absret_z)_(\d+)_(\d+)$")
_TREND_REGIME = re.compile(r"^close_trend_(?:regime_sma_(\d+)|state_sma_(\d+)_(\d+))$")
_MTF = re.compile(
    r"^mtf_([^_]+)_(?:open|high|low|close|volume|close_logret|volatility|trend_score|atr|adx|regime_vol_ratio)$"
)
_PPO = re.compile(r"^ppo_(\d+)_(\d+)$")
_PPO_SIGNAL = re.compile(r"^ppo_signal_(\d+)$")
_PPO_HIST = re.compile(r"^ppo_hist_(\d+)_(\d+)_(\d+)$")
_VWAP = re.compile(r"^vwap_(\d+)$")
_RMS = re.compile(r"^(.+)__root_mean_square$")

_ROC_SIGNAL_OUTPUTS = {
    "manual_long_signal",
    "manual_conviction_score",
    "manual_all_conditions_signal",
    "manual_vol_adjusted_signal",
    "short_signal",
    "combined_signal",
}


def _new_columns(before: Iterable[str], after: Iterable[str]) -> list[str]:
    before_set = set(before)
    return [str(column) for column in after if column not in before_set]


def _extract_missing_columns(exc: KeyError) -> list[str]:
    raw = str(exc.args[0] if exc.args else exc)
    columns: list[str] = []
    for token in _COLUMN_TOKEN.findall(raw):
        if token not in columns:
            columns.append(token)
    return columns


def _infer_base_interval_minutes(df: pd.DataFrame) -> int:
    index = pd.DatetimeIndex(pd.to_datetime(df.index, errors="raise"))
    if len(index) < 2:
        raise ValueError("Cannot infer the base interval for multi-timeframe prerequisites from fewer than two rows.")
    deltas = pd.Series(index).diff().dropna()
    if deltas.empty:
        raise ValueError("Cannot infer the base interval for multi-timeframe prerequisites.")
    minutes = int(deltas.median().total_seconds() // 60)
    if minutes <= 0:
        raise ValueError("Inferred multi-timeframe base interval must be positive.")
    return minutes


def _materialize_roc_signal(df: pd.DataFrame, *, active: set[str]) -> pd.DataFrame:
    out = df
    prerequisites = [
        "roc_12",
        "regime_vol_ratio_z_24_168",
        "close_z",
        "mtf_1h_trend_score",
        "mtf_4h_trend_score",
        "is_weekend",
    ]
    for prerequisite in prerequisites:
        out = _ensure_column(out, prerequisite, active=active)
    return roc_long_only_conditions_signal(out)


def _materialize_ppo_aliases(df: pd.DataFrame) -> pd.DataFrame:
    generated = add_ppo_features(df, price_col="close", fast=12, slow=26, signal=9)
    out = df.copy()
    aliases = {
        "ppo": "ppo_12_26",
        "ppo_signal": "ppo_signal_9",
        "ppo_hist": "ppo_hist_12_26_9",
    }
    for alias, source_col in aliases.items():
        if alias not in out.columns:
            out[alias] = generated[source_col]
    return out


def _ensure_column(df: pd.DataFrame, column: str, *, active: set[str]) -> pd.DataFrame:
    if column in df.columns:
        return df
    if column in active:
        raise KeyError(f"Cyclic dashboard prerequisite detected while materializing '{column}'.")

    active.add(column)
    try:
        out = df
        lag_match = _LAG.fullmatch(column)
        rolling_match = _VOL_ROLLING.fullmatch(column)
        ewma_match = _VOL_EWMA.fullmatch(column)
        atr_match = _ATR.fullmatch(column)
        adx_match = _ADX.fullmatch(column)
        rsi_match = _RSI.fullmatch(column)
        roc_match = _ROC.fullmatch(column)
        price_momentum_match = _PRICE_MOMENTUM.fullmatch(column)
        return_momentum_match = _RETURN_MOMENTUM.fullmatch(column)
        sma_match = _SMA.fullmatch(column)
        ema_match = _EMA.fullmatch(column)
        ema_alias_match = _EMA_ALIAS.fullmatch(column)
        stochastic_match = _STOCHASTIC.fullmatch(column)
        regime_match = _REGIME.fullmatch(column)
        trend_regime_match = _TREND_REGIME.fullmatch(column)
        mtf_match = _MTF.fullmatch(column)
        ppo_match = _PPO.fullmatch(column)
        ppo_signal_match = _PPO_SIGNAL.fullmatch(column)
        ppo_hist_match = _PPO_HIST.fullmatch(column)
        vwap_match = _VWAP.fullmatch(column)
        rms_match = _RMS.fullmatch(column)

        if column in {"close_ret", "close_logret"}:
            out = add_close_returns(out, log=column.endswith("_logret"), col_name=column)
        elif rms_match:
            source_col = rms_match.group(1)
            out = _ensure_column(out, source_col, active=active)
            out = out.copy()
            out[column] = compute_rms(
                out[source_col],
                window=48,
            )
        elif lag_match:
            source_col, lag = lag_match.groups()
            out = _ensure_column(out, source_col, active=active)
            out = out.copy()
            out[column] = out[source_col].shift(int(lag))
        elif rolling_match:
            out = _ensure_column(out, "close_logret", active=active)
            out = add_volatility_features(
                out,
                returns_col="close_logret",
                rolling_windows=[int(rolling_match.group(1))],
                ewma_spans=[],
                annualization_factor=None,
            )
        elif ewma_match:
            out = _ensure_column(out, "close_logret", active=active)
            out = add_volatility_features(
                out,
                returns_col="close_logret",
                rolling_windows=[],
                ewma_spans=[int(ewma_match.group(1))],
                annualization_factor=None,
            )
        elif atr_match:
            window = int(atr_match.group(1))
            out = add_atr_features(out, windows=[window])
            if column.startswith("atr_over_price_"):
                out = out.copy()
                out[column] = compute_ratio(out[f"atr_{window}"], out["close"], subtract=0.0)
        elif adx_match:
            out = add_adx_features(out, windows=[int(adx_match.group(1))])
        elif rsi_match:
            out = add_rsi_features(out, windows=[int(rsi_match.group(1))])
        elif roc_match:
            out = add_roc_features(out, windows=[int(roc_match.group(1))])
        elif price_momentum_match:
            out = add_price_momentum_features(out, windows=[int(price_momentum_match.group(1))])
        elif return_momentum_match:
            returns_col, window = return_momentum_match.groups()
            out = _ensure_column(out, returns_col, active=active)
            out = add_return_momentum_features(out, returns_col=returns_col, windows=[int(window)])
        elif sma_match:
            window = int(sma_match.group(1))
            out = add_trend_features(out, sma_windows=[window], ema_spans=[])
            if column.startswith("close_over_sma_"):
                out = out.copy()
                out[column] = compute_ratio(out["close"], out[f"close_sma_{window}"], subtract=1.0)
        elif ema_match:
            span = int(ema_match.group(1))
            out = add_trend_features(out, sma_windows=[], ema_spans=[span])
            if column.startswith("close_over_ema_"):
                out = out.copy()
                out[column] = compute_ratio(out["close"], out[f"close_ema_{span}"], subtract=1.0)
        elif ema_alias_match:
            out = out.copy()
            out[column] = compute_ema(out["close"].astype(float), span=int(ema_alias_match.group(1)))
        elif stochastic_match:
            out = add_stochastic_features(out, window=int(stochastic_match.group(1)))
        elif column.startswith("stoch_rsi_"):
            out = add_stochastic_rsi_features(out)
        elif regime_match:
            short_window, long_window = (int(value) for value in regime_match.groups())
            out = add_regime_context_features(
                out,
                vol_short_window=short_window,
                vol_long_window=long_window,
                vol_window_pairs=[(short_window, long_window)],
            )
        elif trend_regime_match:
            base_window, short_window, long_window = trend_regime_match.groups()
            if base_window is not None:
                out = _ensure_column(out, f"close_sma_{base_window}", active=active)
                out = _ensure_column(out, f"close_over_sma_{base_window}", active=active)
                out = add_trend_regime_features(
                    out,
                    base_sma_for_sign=int(base_window),
                    short_sma=int(base_window),
                    long_sma=int(base_window),
                )
            else:
                out = _ensure_column(out, f"close_sma_{short_window}", active=active)
                out = _ensure_column(out, f"close_sma_{long_window}", active=active)
                out = _ensure_column(out, f"close_over_sma_{long_window}", active=active)
                out = add_trend_regime_features(
                    out,
                    base_sma_for_sign=int(long_window),
                    short_sma=int(short_window),
                    long_sma=int(long_window),
                )
        elif mtf_match:
            out = add_multi_timeframe_features(
                out,
                base_interval_minutes=_infer_base_interval_minutes(out),
                timeframes=[mtf_match.group(1)],
            )
        elif column == "is_weekend":
            out = add_session_context_features(out)
        elif column == "close_z":
            out = out.copy()
            out[column] = compute_rolling_zscore_transform(out["close"], window=2520, shift=1)
        elif column in _ROC_SIGNAL_OUTPUTS:
            out = _materialize_roc_signal(out, active=active)
        elif column in {"ppo", "ppo_signal", "ppo_hist"}:
            out = _materialize_ppo_aliases(out)
        elif ppo_match:
            fast, slow = (int(value) for value in ppo_match.groups())
            out = add_ppo_features(out, fast=fast, slow=slow)
        elif ppo_signal_match:
            out = add_ppo_features(out, signal=int(ppo_signal_match.group(1)))
        elif ppo_hist_match:
            fast, slow, signal = (int(value) for value in ppo_hist_match.groups())
            out = add_ppo_features(out, fast=fast, slow=slow, signal=signal)
        elif vwap_match:
            out = add_vwap_features(out, windows=[int(vwap_match.group(1))])

        if column not in out.columns:
            raise KeyError(
                f"Dashboard auto-materialization cannot derive prerequisite column '{column}' from the loaded frame."
            )
        return out
    finally:
        active.remove(column)


def materialize_columns(df: pd.DataFrame, columns: Iterable[str]) -> tuple[pd.DataFrame, list[str]]:
    before = list(df.columns)
    out = df
    for column in columns:
        normalized = str(column)
        if normalized and normalized not in out.columns:
            out = _ensure_column(out, normalized, active=set())
    return out, _new_columns(before, out.columns)


def call_with_materialized_dependencies(
    df: pd.DataFrame,
    call: Callable[[pd.DataFrame], T],
) -> tuple[T, list[str]]:
    out = df
    materialized: list[str] = []
    for _ in range(32):
        try:
            return call(out), materialized
        except KeyError as exc:
            missing = _extract_missing_columns(exc)
            if not missing:
                raise
            before = list(out.columns)
            try:
                out, generated = materialize_columns(out, missing)
            except KeyError as dependency_exc:
                raise KeyError(
                    f"{exc.args[0]} Dashboard auto-materialization failed: {dependency_exc.args[0]}"
                ) from exc
            materialized.extend(_new_columns(materialized, generated))
            if not _new_columns(before, out.columns):
                raise
    raise RuntimeError("Dashboard prerequisite materialization exceeded the retry limit.")


__all__ = ["call_with_materialized_dependencies", "materialize_columns"]
