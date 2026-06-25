from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd


_ALLOWED_MODES = frozenset({"long_only", "short_only", "long_short"})

_DEFAULT_CFG: dict[str, Any] = {
    "close_col": "close",
    "atr_col": "atr_14",
    "ema_fast_rms_col": "ema_20__root_mean_square",
    "ema_mid_rms_col": "ema_50__root_mean_square",
    "ema_slow_rms_col": "ema_100__root_mean_square",
    "vwap_col": "vwap_20",
    "vwap_rms_col": "vwap_20__root_mean_square",
    "ppo_col": "ppo",
    "ppo_signal_col": "ppo_signal",
    "mode": "long_short",
    "require_vwap_rms_filter": False,
    "require_rms_slope_filter": False,
    "max_vwap_distance_atr": 1.0,
    "min_rms_slope": 0.0,
    "signal_col": "signal_side",
    "candidate_col": "signal_candidate",
    "bull_stack_col": "ema_rms_bull_stack",
    "bear_stack_col": "ema_rms_bear_stack",
    "fast_slope_col": "ema_rms_fast_slope",
    "vwap_distance_atr_col": "vwap_distance_atr",
    "vwap_reclaim_col": "vwap_reclaim",
    "vwap_reject_col": "vwap_reject",
    "vwap_rms_long_bias_col": "vwap_rms_long_bias",
    "vwap_rms_short_bias_col": "vwap_rms_short_bias",
    "ppo_hist_col": "ppo_hist",
    "long_setup_col": "ema_rms_long_setup",
    "short_setup_col": "ema_rms_short_setup",
}


def _merge_cfg(signal_cfg: Mapping[str, Any] | None, overrides: Mapping[str, Any]) -> dict[str, Any]:
    cfg = dict(_DEFAULT_CFG)
    raw_cfg = dict(signal_cfg or {})
    nested_params = raw_cfg.pop("params", None)
    cfg.update(raw_cfg)
    if nested_params is not None:
        if not isinstance(nested_params, Mapping):
            raise TypeError("signal_cfg.params must be a mapping when provided.")
        cfg.update(dict(nested_params))
    cfg.update(dict(overrides))
    return cfg


def _finite_float(value: Any, *, field: str) -> float:
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"{field} must be finite.")
    return out


def _validate_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(cfg)
    string_keys = (
        "close_col",
        "atr_col",
        "ema_fast_rms_col",
        "ema_mid_rms_col",
        "ema_slow_rms_col",
        "vwap_col",
        "vwap_rms_col",
        "ppo_col",
        "ppo_signal_col",
        "signal_col",
        "candidate_col",
        "bull_stack_col",
        "bear_stack_col",
        "fast_slope_col",
        "vwap_distance_atr_col",
        "vwap_reclaim_col",
        "vwap_reject_col",
        "vwap_rms_long_bias_col",
        "vwap_rms_short_bias_col",
        "ppo_hist_col",
        "long_setup_col",
        "short_setup_col",
    )
    for key in string_keys:
        value = normalized.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string.")
        normalized[key] = value.strip()

    mode = str(normalized.get("mode", "long_short"))
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of: {sorted(_ALLOWED_MODES)}.")
    normalized["mode"] = mode

    for key in ("require_vwap_rms_filter", "require_rms_slope_filter"):
        if not isinstance(normalized.get(key), bool):
            raise TypeError(f"{key} must be boolean.")

    normalized["max_vwap_distance_atr"] = _finite_float(
        normalized.get("max_vwap_distance_atr"),
        field="max_vwap_distance_atr",
    )
    normalized["min_rms_slope"] = _finite_float(
        normalized.get("min_rms_slope"),
        field="min_rms_slope",
    )
    if normalized["max_vwap_distance_atr"] <= 0.0:
        raise ValueError("max_vwap_distance_atr must be > 0.")
    if normalized["min_rms_slope"] < 0.0:
        raise ValueError("min_rms_slope must be >= 0.")
    return normalized


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def build_ema_rms_ppo_vwap_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Build causal EMA-RMS trend continuation events confirmed by PPO and VWAP recrosses.

    Indicators are observed at the current bar close. The backtest remains responsible for
    executing accepted events at the next bar open.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))
    required_cols = [
        str(cfg["close_col"]),
        str(cfg["atr_col"]),
        str(cfg["ema_fast_rms_col"]),
        str(cfg["ema_mid_rms_col"]),
        str(cfg["ema_slow_rms_col"]),
        str(cfg["vwap_col"]),
        str(cfg["vwap_rms_col"]),
        str(cfg["ppo_col"]),
        str(cfg["ppo_signal_col"]),
    ]
    missing = [column for column in required_cols if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for ema_rms_ppo_vwap_signal: {missing}")

    out = df.copy()
    close = _numeric(out, str(cfg["close_col"]))
    atr = _numeric(out, str(cfg["atr_col"]))
    ema_fast_rms = _numeric(out, str(cfg["ema_fast_rms_col"]))
    ema_mid_rms = _numeric(out, str(cfg["ema_mid_rms_col"]))
    ema_slow_rms = _numeric(out, str(cfg["ema_slow_rms_col"]))
    vwap = _numeric(out, str(cfg["vwap_col"]))
    vwap_rms = _numeric(out, str(cfg["vwap_rms_col"]))
    ppo = _numeric(out, str(cfg["ppo_col"]))
    ppo_signal = _numeric(out, str(cfg["ppo_signal_col"]))

    fast_slope = ema_fast_rms - ema_fast_rms.shift(1)
    ppo_hist = ppo - ppo_signal
    bull_stack = ema_fast_rms.gt(ema_mid_rms) & ema_mid_rms.gt(ema_slow_rms)
    bear_stack = ema_fast_rms.lt(ema_mid_rms) & ema_mid_rms.lt(ema_slow_rms)
    vwap_reclaim = close.shift(1).le(vwap.shift(1)) & close.gt(vwap)
    vwap_reject = close.shift(1).ge(vwap.shift(1)) & close.lt(vwap)
    vwap_distance_atr = (close - vwap) / atr.where(atr.gt(0.0), np.nan)
    near_vwap = vwap_distance_atr.abs().le(float(cfg["max_vwap_distance_atr"]))
    vwap_rms_long_bias = vwap.gt(vwap_rms)
    vwap_rms_short_bias = vwap.lt(vwap_rms)

    valid = (
        close.notna()
        & atr.gt(0.0)
        & ema_fast_rms.notna()
        & ema_mid_rms.notna()
        & ema_slow_rms.notna()
        & vwap.notna()
        & vwap_rms.notna()
        & ppo.notna()
        & ppo_signal.notna()
        & fast_slope.notna()
    )
    long_filter = pd.Series(True, index=out.index, dtype=bool)
    short_filter = pd.Series(True, index=out.index, dtype=bool)
    if bool(cfg["require_vwap_rms_filter"]):
        long_filter &= vwap_rms_long_bias
        short_filter &= vwap_rms_short_bias
    if bool(cfg["require_rms_slope_filter"]):
        slope_threshold = float(cfg["min_rms_slope"])
        long_filter &= fast_slope.gt(slope_threshold)
        short_filter &= fast_slope.lt(-slope_threshold)

    long_setup = (
        valid
        & bull_stack
        & ppo.gt(0.0)
        & ppo_hist.gt(0.0)
        & vwap_reclaim
        & near_vwap
        & long_filter
    )
    short_setup = (
        valid
        & bear_stack
        & ppo.lt(0.0)
        & ppo_hist.lt(0.0)
        & vwap_reject
        & near_vwap
        & short_filter
    )

    if str(cfg["mode"]) == "long_only":
        short_setup &= False
    elif str(cfg["mode"]) == "short_only":
        long_setup &= False

    signal_side = pd.Series(0, index=out.index, dtype="int8")
    signal_side.loc[long_setup] = 1
    signal_side.loc[short_setup] = -1

    out[str(cfg["bull_stack_col"])] = bull_stack.fillna(False).astype("int8")
    out[str(cfg["bear_stack_col"])] = bear_stack.fillna(False).astype("int8")
    out[str(cfg["fast_slope_col"])] = fast_slope
    out[str(cfg["vwap_distance_atr_col"])] = vwap_distance_atr
    out[str(cfg["vwap_reclaim_col"])] = vwap_reclaim.fillna(False).astype("int8")
    out[str(cfg["vwap_reject_col"])] = vwap_reject.fillna(False).astype("int8")
    out[str(cfg["vwap_rms_long_bias_col"])] = vwap_rms_long_bias.fillna(False).astype("int8")
    out[str(cfg["vwap_rms_short_bias_col"])] = vwap_rms_short_bias.fillna(False).astype("int8")
    out[str(cfg["ppo_hist_col"])] = ppo_hist
    out[str(cfg["long_setup_col"])] = long_setup.fillna(False).astype("int8")
    out[str(cfg["short_setup_col"])] = short_setup.fillna(False).astype("int8")
    out[str(cfg["signal_col"])] = signal_side
    out[str(cfg["candidate_col"])] = signal_side.ne(0).astype("int8")

    return out, {
        "kind": "ema_rms_ppo_vwap",
        "mode": str(cfg["mode"]),
        "require_vwap_rms_filter": bool(cfg["require_vwap_rms_filter"]),
        "require_rms_slope_filter": bool(cfg["require_rms_slope_filter"]),
        "long_candidates": int(long_setup.sum()),
        "short_candidates": int(short_setup.sum()),
        "signal_col": str(cfg["signal_col"]),
        "candidate_col": str(cfg["candidate_col"]),
    }


def ema_rms_ppo_vwap_signal(df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    """
    Apply the registered ``ema_rms_ppo_vwap`` signal transformation.
    
    YAML declaration::
    
        signals:
          kind: ema_rms_ppo_vwap
          params: {}
    
    Required input columns
    ----------------------
    None fixed by signature:
        Required dataframe columns are resolved from configuration or from
        upstream feature/target/signal stages at runtime.
    
    Parameters
    ----------
    params:
        Additional keyword parameters accepted from YAML ``params``.
    """
    out, _ = build_ema_rms_ppo_vwap_signal(df, params)
    return out


__all__ = ["build_ema_rms_ppo_vwap_signal", "ema_rms_ppo_vwap_signal"]
