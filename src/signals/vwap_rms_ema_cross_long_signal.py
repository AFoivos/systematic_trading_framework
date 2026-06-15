from __future__ import annotations

import math
from typing import Any, Mapping

import pandas as pd


_ALLOWED_MODES = frozenset({"long_only", "short_only", "long_short"})

_DEFAULT_CFG: dict[str, Any] = {
    "ema_mid_col": "ema_50",
    "ema_slow_col": "ema_100",
    "ema_mid_rms_col": "ema_50__root_mean_square",
    "vwap_rms_col": "vwap_20__root_mean_square",
    "ppo_col": "ppo",
    "ppo_signal_col": "ppo_signal",
    "ppo_hist_min": 0.0,
    "use_ppo_confirmation": True,
    "use_ema_regime": True,
    "use_vwap_rms_cross": True,
    "use_mfi_confirmation": False,
    "mfi_col": "mfi_14",
    "mfi_lower": 40.0,
    "mfi_upper": 80.0,
    "entry_delay_bars": 0,
    "mode": "long_only",
    "regime_col": "ema_50_above_ema_100",
    "short_regime_col": "ema_50_below_ema_100",
    "cross_up_col": "vwap_rms_cross_above_ema_50_rms",
    "cross_down_col": "vwap_rms_cross_below_ema_50_rms",
    "ppo_hist_col": "ppo_hist",
    "ppo_hist_positive_col": "ppo_hist_positive",
    "ppo_hist_negative_col": "ppo_hist_negative",
    "ppo_above_signal_col": "ppo_above_signal",
    "ppo_below_signal_col": "ppo_below_signal",
    "mfi_confirmation_col": "mfi_confirmation",
    "long_setup_col": "vwap_rms_ema_cross_long_setup",
    "short_setup_col": "vwap_rms_ema_cross_short_setup",
    "signal_col": "signal_side",
    "candidate_col": "signal_candidate",
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


def _validate_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(cfg)
    mode = str(normalized.get("mode", "long_only"))
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of: {sorted(_ALLOWED_MODES)}.")
    normalized["mode"] = mode

    boolean_keys = {
        "use_ppo_confirmation",
        "use_ema_regime",
        "use_vwap_rms_cross",
        "use_mfi_confirmation",
    }
    for key in boolean_keys:
        if not isinstance(normalized.get(key), bool):
            raise TypeError(f"{key} must be boolean.")

    numeric_keys = {"ppo_hist_min", "mfi_lower", "mfi_upper"}
    for key in numeric_keys:
        value = normalized[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be a finite number.")
        normalized[key] = float(value)
        if not math.isfinite(normalized[key]):
            raise ValueError(f"{key} must be a finite number.")
    if normalized["mfi_lower"] > normalized["mfi_upper"]:
        raise ValueError("mfi_lower must be <= mfi_upper.")

    entry_delay_bars = normalized["entry_delay_bars"]
    if isinstance(entry_delay_bars, bool) or int(entry_delay_bars) != entry_delay_bars:
        raise ValueError("entry_delay_bars must be a non-negative integer.")
    normalized["entry_delay_bars"] = int(entry_delay_bars)
    if normalized["entry_delay_bars"] < 0:
        raise ValueError("entry_delay_bars must be a non-negative integer.")

    for key, value in normalized.items():
        if key in numeric_keys or key in boolean_keys or key in {"mode", "entry_delay_bars"}:
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string.")
        normalized[key] = value.strip()
    return normalized


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def build_vwap_rms_ema_cross_long_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Build causal VWAP-RMS crossover events within a simple-EMA trend regime.

    Indicators are observed at the current bar close. The backtest remains responsible for
    executing accepted events at the next bar open.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))
    required_cols = [str(cfg["ema_mid_col"]), str(cfg["ema_slow_col"])]
    if bool(cfg["use_vwap_rms_cross"]):
        required_cols.extend([str(cfg["ema_mid_rms_col"]), str(cfg["vwap_rms_col"])])
    if bool(cfg["use_ppo_confirmation"]):
        required_cols.extend([str(cfg["ppo_col"]), str(cfg["ppo_signal_col"])])
    if bool(cfg["use_mfi_confirmation"]):
        required_cols.append(str(cfg["mfi_col"]))
    missing = [column for column in required_cols if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for vwap_rms_ema_cross_long_signal: {missing}")

    out = df.copy()
    ema_mid = _numeric(out, str(cfg["ema_mid_col"]))
    ema_slow = _numeric(out, str(cfg["ema_slow_col"]))
    ema_mid_rms = (
        _numeric(out, str(cfg["ema_mid_rms_col"]))
        if str(cfg["ema_mid_rms_col"]) in out.columns
        else pd.Series(0.0, index=out.index, dtype=float)
    )
    vwap_rms = (
        _numeric(out, str(cfg["vwap_rms_col"]))
        if str(cfg["vwap_rms_col"]) in out.columns
        else pd.Series(0.0, index=out.index, dtype=float)
    )
    ppo = (
        _numeric(out, str(cfg["ppo_col"]))
        if str(cfg["ppo_col"]) in out.columns
        else pd.Series(0.0, index=out.index, dtype=float)
    )
    ppo_signal = (
        _numeric(out, str(cfg["ppo_signal_col"]))
        if str(cfg["ppo_signal_col"]) in out.columns
        else pd.Series(0.0, index=out.index, dtype=float)
    )
    mfi = (
        _numeric(out, str(cfg["mfi_col"]))
        if bool(cfg["use_mfi_confirmation"])
        else pd.Series(50.0, index=out.index, dtype=float)
    )

    ppo_hist = ppo - ppo_signal
    long_regime = ema_mid.gt(ema_slow)
    short_regime = ema_mid.lt(ema_slow)
    cross_up = vwap_rms.shift(1).le(ema_mid_rms.shift(1)) & vwap_rms.gt(ema_mid_rms)
    cross_down = vwap_rms.shift(1).ge(ema_mid_rms.shift(1)) & vwap_rms.lt(ema_mid_rms)
    ppo_hist_positive = ppo_hist.gt(0.0)
    ppo_hist_negative = ppo_hist.lt(0.0)
    ppo_hist_above_min = ppo_hist.gt(float(cfg["ppo_hist_min"]))
    ppo_hist_below_min = ppo_hist.lt(-float(cfg["ppo_hist_min"]))
    ppo_above_signal = ppo.gt(ppo_signal)
    ppo_below_signal = ppo.lt(ppo_signal)
    mfi_confirmation = mfi.between(float(cfg["mfi_lower"]), float(cfg["mfi_upper"]), inclusive="both")
    valid = (
        ema_mid.notna()
        & ema_slow.notna()
        & ema_mid_rms.notna()
        & ema_mid_rms.shift(1).notna()
        & vwap_rms.notna()
        & vwap_rms.shift(1).notna()
        & ppo.notna()
        & ppo_signal.notna()
        & mfi.notna()
    )
    long_filter = pd.Series(True, index=out.index, dtype=bool)
    short_filter = pd.Series(True, index=out.index, dtype=bool)
    if bool(cfg["use_ema_regime"]):
        long_filter &= long_regime
        short_filter &= short_regime
    if bool(cfg["use_vwap_rms_cross"]):
        long_filter &= cross_up
        short_filter &= cross_down
    if bool(cfg["use_ppo_confirmation"]):
        long_filter &= ppo_hist_above_min
        short_filter &= ppo_hist_below_min
    if bool(cfg["use_mfi_confirmation"]):
        long_filter &= mfi_confirmation
        short_filter &= mfi_confirmation

    long_setup = valid & long_filter
    short_setup = valid & short_filter

    if str(cfg["mode"]) == "long_only":
        short_setup = pd.Series(False, index=out.index)
    elif str(cfg["mode"]) == "short_only":
        long_setup = pd.Series(False, index=out.index)

    signal_side = pd.Series(0, index=out.index, dtype="int8")
    signal_side.loc[long_setup] = 1
    signal_side.loc[short_setup] = -1
    if int(cfg["entry_delay_bars"]) > 0:
        signal_side = signal_side.shift(int(cfg["entry_delay_bars"])).fillna(0).astype("int8")

    out[str(cfg["regime_col"])] = long_regime.fillna(False).astype("int8")
    out[str(cfg["short_regime_col"])] = short_regime.fillna(False).astype("int8")
    out[str(cfg["cross_up_col"])] = cross_up.fillna(False).astype("int8")
    out[str(cfg["cross_down_col"])] = cross_down.fillna(False).astype("int8")
    out[str(cfg["ppo_hist_col"])] = ppo_hist
    out[str(cfg["ppo_hist_positive_col"])] = ppo_hist_positive.fillna(False).astype("int8")
    out[str(cfg["ppo_hist_negative_col"])] = ppo_hist_negative.fillna(False).astype("int8")
    out[str(cfg["ppo_above_signal_col"])] = ppo_above_signal.fillna(False).astype("int8")
    out[str(cfg["ppo_below_signal_col"])] = ppo_below_signal.fillna(False).astype("int8")
    out[str(cfg["mfi_confirmation_col"])] = mfi_confirmation.fillna(False).astype("int8")
    out[str(cfg["long_setup_col"])] = long_setup.fillna(False).astype("int8")
    out[str(cfg["short_setup_col"])] = short_setup.fillna(False).astype("int8")
    out[str(cfg["signal_col"])] = signal_side
    out[str(cfg["candidate_col"])] = signal_side.ne(0).astype("int8")

    return out, {
        "kind": "vwap_rms_ema_cross_long",
        "mode": str(cfg["mode"]),
        "long_candidates": int(long_setup.sum()),
        "short_candidates": int(short_setup.sum()),
        "ppo_hist_min": float(cfg["ppo_hist_min"]),
        "use_ppo_confirmation": bool(cfg["use_ppo_confirmation"]),
        "use_ema_regime": bool(cfg["use_ema_regime"]),
        "use_vwap_rms_cross": bool(cfg["use_vwap_rms_cross"]),
        "use_mfi_confirmation": bool(cfg["use_mfi_confirmation"]),
        "mfi_lower": float(cfg["mfi_lower"]),
        "mfi_upper": float(cfg["mfi_upper"]),
        "entry_delay_bars": int(cfg["entry_delay_bars"]),
        "signal_col": str(cfg["signal_col"]),
        "candidate_col": str(cfg["candidate_col"]),
    }


def vwap_rms_ema_cross_long_signal(df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    out, _ = build_vwap_rms_ema_cross_long_signal(df, params)
    return out


__all__ = ["build_vwap_rms_ema_cross_long_signal", "vwap_rms_ema_cross_long_signal"]
