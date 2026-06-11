from __future__ import annotations

import math
from typing import Any, Mapping

import pandas as pd


_DEFAULT_CFG: dict[str, Any] = {
    "ema_mid_col": "ema_50",
    "ema_slow_col": "ema_96",
    "ema_mid_rms_col": "ema_50__root_mean_square",
    "vwap_rms_col": "vwap_40__root_mean_square",
    "ppo_col": "ppo_12_36",
    "ppo_signal_col": "ppo_signal_9",
    "ppo_hist_min": 0.0002,
    "hmm_regime_col": "hmm_regime",
    "hmm_min_regime": 1,
    "hmm_prob_col": None,
    "hmm_prob_min": None,
    "regime_col": "ema_50_above_ema_96",
    "cross_up_col": "vwap_40_rms_cross_above_ema_50_rms",
    "ppo_hist_col": "ppo_hist_12_36_9",
    "ppo_hist_positive_col": "ppo_hist_12_36_9_positive",
    "ppo_above_signal_col": "ppo_12_36_above_ppo_signal_9",
    "hmm_ok_col": "hmm_regime_ok",
    "long_setup_col": "vwap_40_rms_ema_50_cross_long_hmm_setup",
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
    for key in ("ppo_hist_min", "hmm_min_regime"):
        value = normalized[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be a finite number.")
        normalized[key] = float(value)
        if not math.isfinite(normalized[key]):
            raise ValueError(f"{key} must be a finite number.")
    if normalized["hmm_prob_min"] is not None:
        value = normalized["hmm_prob_min"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("hmm_prob_min must be a finite number or None.")
        normalized["hmm_prob_min"] = float(value)
        if not math.isfinite(normalized["hmm_prob_min"]):
            raise ValueError("hmm_prob_min must be a finite number or None.")
    for key, value in normalized.items():
        if key in {"ppo_hist_min", "hmm_min_regime", "hmm_prob_min"}:
            continue
        if key == "hmm_prob_col" and value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string.")
        normalized[key] = value.strip()
    if (normalized["hmm_prob_col"] is None) != (normalized["hmm_prob_min"] is None):
        raise ValueError("hmm_prob_col and hmm_prob_min must be provided together.")
    return normalized


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def build_vwap_rms_ema_cross_long_hmm_gate_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Build causal long-only VWAP-RMS crossover events gated by an HMM regime.

    Indicators are observed at the current bar close. The backtest remains responsible for
    executing accepted events at the next bar open.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))
    required_cols = [
        str(cfg["ema_mid_col"]),
        str(cfg["ema_slow_col"]),
        str(cfg["ema_mid_rms_col"]),
        str(cfg["vwap_rms_col"]),
        str(cfg["ppo_col"]),
        str(cfg["ppo_signal_col"]),
        str(cfg["hmm_regime_col"]),
    ]
    use_hmm_probability = cfg["hmm_prob_col"] is not None and cfg["hmm_prob_min"] is not None
    if use_hmm_probability:
        required_cols.append(str(cfg["hmm_prob_col"]))
    missing = [column for column in required_cols if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for vwap_rms_ema_cross_long_hmm_gate_signal: {missing}")

    out = df.copy()
    ema_mid = _numeric(out, str(cfg["ema_mid_col"]))
    ema_slow = _numeric(out, str(cfg["ema_slow_col"]))
    ema_mid_rms = _numeric(out, str(cfg["ema_mid_rms_col"]))
    vwap_rms = _numeric(out, str(cfg["vwap_rms_col"]))
    ppo = _numeric(out, str(cfg["ppo_col"]))
    ppo_signal = _numeric(out, str(cfg["ppo_signal_col"]))
    hmm_regime = _numeric(out, str(cfg["hmm_regime_col"]))

    ppo_hist = ppo - ppo_signal
    long_regime = ema_mid.gt(ema_slow)
    cross_up = vwap_rms.shift(1).le(ema_mid_rms.shift(1)) & vwap_rms.gt(ema_mid_rms)
    ppo_hist_positive = ppo_hist.gt(0.0)
    ppo_filter = ppo_hist.gt(float(cfg["ppo_hist_min"]))
    ppo_above_signal = ppo.gt(ppo_signal)
    hmm_filter = hmm_regime.notna() & hmm_regime.ge(float(cfg["hmm_min_regime"]))
    valid = (
        ema_mid.notna()
        & ema_slow.notna()
        & ema_mid_rms.notna()
        & ema_mid_rms.shift(1).notna()
        & vwap_rms.notna()
        & vwap_rms.shift(1).notna()
        & ppo.notna()
        & ppo_signal.notna()
        & hmm_regime.notna()
    )
    if use_hmm_probability:
        hmm_probability = _numeric(out, str(cfg["hmm_prob_col"]))
        hmm_filter = hmm_filter & hmm_probability.ge(float(cfg["hmm_prob_min"]))
        valid = valid & hmm_probability.notna()
    long_setup = valid & long_regime & cross_up & ppo_filter & hmm_filter

    signal_side = pd.Series(0, index=out.index, dtype="int8")
    signal_side.loc[long_setup] = 1

    out[str(cfg["regime_col"])] = long_regime.fillna(False).astype("int8")
    out[str(cfg["cross_up_col"])] = cross_up.fillna(False).astype("int8")
    out[str(cfg["ppo_hist_col"])] = ppo_hist
    out[str(cfg["ppo_hist_positive_col"])] = ppo_hist_positive.fillna(False).astype("int8")
    out[str(cfg["ppo_above_signal_col"])] = ppo_above_signal.fillna(False).astype("int8")
    out[str(cfg["hmm_ok_col"])] = hmm_filter.fillna(False).astype("int8")
    out[str(cfg["long_setup_col"])] = long_setup.fillna(False).astype("int8")
    out[str(cfg["signal_col"])] = signal_side
    out[str(cfg["candidate_col"])] = signal_side.ne(0).astype("int8")

    return out, {
        "kind": "vwap_rms_ema_cross_long_hmm_gate",
        "long_candidates": int(long_setup.sum()),
        "ppo_hist_min": float(cfg["ppo_hist_min"]),
        "hmm_min_regime": float(cfg["hmm_min_regime"]),
        "hmm_prob_min": None if cfg["hmm_prob_min"] is None else float(cfg["hmm_prob_min"]),
        "signal_col": str(cfg["signal_col"]),
        "candidate_col": str(cfg["candidate_col"]),
    }


def vwap_rms_ema_cross_long_hmm_gate_signal(df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    out, _ = build_vwap_rms_ema_cross_long_hmm_gate_signal(df, params)
    return out


__all__ = [
    "build_vwap_rms_ema_cross_long_hmm_gate_signal",
    "vwap_rms_ema_cross_long_hmm_gate_signal",
]
