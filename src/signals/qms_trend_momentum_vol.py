from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np
import pandas as pd


_ALLOWED_MODES = frozenset({"long_only", "short_only", "long_short"})
_ALLOWED_COMBINATIONS = frozenset({"trend_only", "trend_momentum", "trend_momentum_vol"})

_DEFAULT_CFG: dict[str, Any] = {
    "mode": "long_short",
    "combination": "trend_momentum_vol",
    "trend_col": "qms_trend",
    "trend_confidence_col": "qms_trend_confidence",
    "trend_uncertainty_col": "ktrend_uncertainty",
    "momentum_col": "qms_momentum",
    "momentum_quality_col": "qms_momentum_quality",
    "alignment_col": "qms_trend_momentum_alignment",
    "acceleration_col": "lmom_acceleration_score",
    "volatility_shock_col": "qms_volatility_shock",
    "state_uncertainty_col": "qms_state_uncertainty",
    "gap_flag_col": "qms_gap_flag",
    "unexpected_gap_col": "qms_unexpected_data_gap",
    "trend_min": 0.03,
    "trend_confidence_min": 0.45,
    "momentum_min": 0.02,
    "momentum_quality_min": 0.15,
    "acceleration_min": 0.0,
    "alignment_min": 0.0,
    "max_abs_volatility_shock": 3.0,
    "volatility_shock_scale": 2.0,
    "max_state_uncertainty": 0.65,
    "score_threshold": 0.30,
    "signal_on_crossing": True,
    "long_score_col": "qms_combo_long_score",
    "short_score_col": "qms_combo_short_score",
    "long_state_col": "qms_combo_long_state",
    "short_state_col": "qms_combo_short_state",
    "signal_col": "qms_combo_signal",
    "candidate_col": "qms_combo_candidate",
}


def _merge_cfg(signal_cfg: Mapping[str, Any] | None, overrides: Mapping[str, Any]) -> dict[str, Any]:
    cfg = dict(_DEFAULT_CFG)
    raw = dict(signal_cfg or {})
    nested = raw.pop("params", None)
    cfg.update(raw)
    if nested is not None:
        if not isinstance(nested, Mapping):
            raise TypeError("signal_cfg.params must be a mapping when provided.")
        cfg.update(dict(nested))
    cfg.update(dict(overrides))
    return cfg


def _finite(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number.")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{field} must be a finite number.")
    return out


def _validate_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    out = dict(cfg)
    mode = str(out["mode"])
    combination = str(out["combination"])
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of {sorted(_ALLOWED_MODES)}.")
    if combination not in _ALLOWED_COMBINATIONS:
        raise ValueError(f"combination must be one of {sorted(_ALLOWED_COMBINATIONS)}.")
    out["mode"] = mode
    out["combination"] = combination

    for key in (
        "trend_min",
        "trend_confidence_min",
        "momentum_min",
        "momentum_quality_min",
        "acceleration_min",
        "alignment_min",
        "max_abs_volatility_shock",
        "volatility_shock_scale",
        "max_state_uncertainty",
        "score_threshold",
    ):
        out[key] = _finite(out[key], field=key)

    for key in (
        "trend_confidence_min",
        "momentum_quality_min",
        "max_state_uncertainty",
        "score_threshold",
    ):
        if not 0.0 <= out[key] <= 1.0:
            raise ValueError(f"{key} must be in [0, 1].")
    if out["volatility_shock_scale"] <= 0.0:
        raise ValueError("volatility_shock_scale must be > 0.")
    if out["max_abs_volatility_shock"] < 0.0:
        raise ValueError("max_abs_volatility_shock must be >= 0.")
    if not isinstance(out["signal_on_crossing"], bool):
        raise TypeError("signal_on_crossing must be boolean.")
    return out


def _num(frame: pd.DataFrame, col: str) -> pd.Series:
    if col not in frame.columns:
        raise KeyError(f"Missing column for qms_trend_momentum_vol signal: {col}")
    return pd.to_numeric(frame[col], errors="coerce").astype(float)


def _scaled_strength(values: pd.Series, floor: float) -> pd.Series:
    denominator = max(1.0 - floor, 1e-12)
    return ((values - floor) / denominator).clip(lower=0.0, upper=1.0)


def _side_signal(long_state: pd.Series, short_state: pd.Series) -> pd.Series:
    side = pd.Series(0, index=long_state.index, dtype="int8")
    side.loc[long_state & ~short_state] = 1
    side.loc[short_state & ~long_state] = -1
    return side


def build_qms_trend_momentum_vol_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build a causal QMS directional-entry signal with controlled ablations.

    Trend defines the allowed side. Momentum provides timing and directional
    confirmation. Volatility is a veto/quality adjustment rather than a vote on
    direction. ``combination`` supports trend-only, trend+momentum, and the full
    trend+momentum+volatility system for like-for-like ablation tests.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))
    out = df.copy()

    trend = _num(out, str(cfg["trend_col"]))
    confidence = _num(out, str(cfg["trend_confidence_col"]))
    trend_uncertainty = _num(out, str(cfg["trend_uncertainty_col"]))
    gap_flag = _num(out, str(cfg["gap_flag_col"]))
    unexpected_gap = _num(out, str(cfg["unexpected_gap_col"]))

    valid = trend.notna() & confidence.notna() & trend_uncertainty.notna()
    no_gap = gap_flag.fillna(1.0).eq(0.0) & unexpected_gap.fillna(1.0).eq(0.0)

    trend_long = trend
    trend_short = -trend
    trend_long_strength = _scaled_strength(trend_long, float(cfg["trend_min"]))
    trend_short_strength = _scaled_strength(trend_short, float(cfg["trend_min"]))
    trend_precision = (1.0 - trend_uncertainty).clip(lower=0.0, upper=1.0)

    # Trend-only score is independently normalized to [0, 1].
    long_score = (
        0.45 * trend_long_strength
        + 0.30 * confidence.clip(lower=0.0, upper=1.0)
        + 0.25 * trend_precision
    ).clip(lower=0.0, upper=1.0)
    short_score = (
        0.45 * trend_short_strength
        + 0.30 * confidence.clip(lower=0.0, upper=1.0)
        + 0.25 * trend_precision
    ).clip(lower=0.0, upper=1.0)

    long_gate = (
        valid
        & no_gap
        & trend_long.ge(float(cfg["trend_min"]))
        & confidence.ge(float(cfg["trend_confidence_min"]))
    )
    short_gate = (
        valid
        & no_gap
        & trend_short.ge(float(cfg["trend_min"]))
        & confidence.ge(float(cfg["trend_confidence_min"]))
    )

    if str(cfg["combination"]) in {"trend_momentum", "trend_momentum_vol"}:
        momentum = _num(out, str(cfg["momentum_col"]))
        quality = _num(out, str(cfg["momentum_quality_col"]))
        alignment = _num(out, str(cfg["alignment_col"]))
        acceleration = _num(out, str(cfg["acceleration_col"]))

        momentum_long_strength = _scaled_strength(momentum, float(cfg["momentum_min"]))
        momentum_short_strength = _scaled_strength(-momentum, float(cfg["momentum_min"]))
        acceleration_long_strength = _scaled_strength(acceleration, float(cfg["acceleration_min"]))
        acceleration_short_strength = _scaled_strength(-acceleration, float(cfg["acceleration_min"]))
        alignment_strength = alignment.clip(lower=0.0, upper=1.0)
        quality_strength = quality.clip(lower=0.0, upper=1.0)

        long_score = (
            0.30 * trend_long_strength
            + 0.18 * confidence.clip(lower=0.0, upper=1.0)
            + 0.12 * trend_precision
            + 0.18 * momentum_long_strength
            + 0.10 * acceleration_long_strength
            + 0.07 * quality_strength
            + 0.05 * alignment_strength
        ).clip(lower=0.0, upper=1.0)
        short_score = (
            0.30 * trend_short_strength
            + 0.18 * confidence.clip(lower=0.0, upper=1.0)
            + 0.12 * trend_precision
            + 0.18 * momentum_short_strength
            + 0.10 * acceleration_short_strength
            + 0.07 * quality_strength
            + 0.05 * alignment_strength
        ).clip(lower=0.0, upper=1.0)

        momentum_valid = momentum.notna() & quality.notna() & alignment.notna() & acceleration.notna()
        long_gate &= (
            momentum_valid
            & momentum.ge(float(cfg["momentum_min"]))
            & quality.ge(float(cfg["momentum_quality_min"]))
            & acceleration.ge(float(cfg["acceleration_min"]))
            & alignment.ge(float(cfg["alignment_min"]))
        )
        short_gate &= (
            momentum_valid
            & momentum.le(-float(cfg["momentum_min"]))
            & quality.ge(float(cfg["momentum_quality_min"]))
            & acceleration.le(-float(cfg["acceleration_min"]))
            & alignment.ge(float(cfg["alignment_min"]))
        )

    if str(cfg["combination"]) == "trend_momentum_vol":
        shock = _num(out, str(cfg["volatility_shock_col"]))
        state_uncertainty = _num(out, str(cfg["state_uncertainty_col"]))
        shock_scale = float(cfg["volatility_shock_scale"])
        vol_quality = pd.Series(
            np.exp(-0.5 * np.square(shock.abs().to_numpy(dtype=float) / shock_scale)),
            index=out.index,
            dtype="float64",
        )
        state_precision = (1.0 - state_uncertainty).clip(lower=0.0, upper=1.0)
        quality_multiplier = (0.65 + 0.35 * vol_quality) * (0.65 + 0.35 * state_precision)
        long_score = (long_score * quality_multiplier).clip(lower=0.0, upper=1.0)
        short_score = (short_score * quality_multiplier).clip(lower=0.0, upper=1.0)

        vol_valid = shock.notna() & state_uncertainty.notna()
        common_vol_gate = (
            vol_valid
            & shock.abs().le(float(cfg["max_abs_volatility_shock"]))
            & state_uncertainty.le(float(cfg["max_state_uncertainty"]))
        )
        long_gate &= common_vol_gate
        short_gate &= common_vol_gate

    long_state = long_gate & long_score.ge(float(cfg["score_threshold"]))
    short_state = short_gate & short_score.ge(float(cfg["score_threshold"]))

    if str(cfg["mode"]) == "long_only":
        short_state = pd.Series(False, index=out.index)
    elif str(cfg["mode"]) == "short_only":
        long_state = pd.Series(False, index=out.index)

    if bool(cfg["signal_on_crossing"]):
        long_signal = long_state & ~long_state.shift(1, fill_value=False)
        short_signal = short_state & ~short_state.shift(1, fill_value=False)
    else:
        long_signal = long_state
        short_signal = short_state

    signal = _side_signal(long_signal.fillna(False), short_signal.fillna(False))

    out[str(cfg["long_score_col"])] = long_score.where(valid)
    out[str(cfg["short_score_col"])] = short_score.where(valid)
    out[str(cfg["long_state_col"])] = long_state.fillna(False).astype("int8")
    out[str(cfg["short_state_col"])] = short_state.fillna(False).astype("int8")
    out[str(cfg["signal_col"])] = signal
    out[str(cfg["candidate_col"])] = signal.ne(0).astype("int8")

    return out, {
        "kind": "qms_trend_momentum_vol",
        "mode": str(cfg["mode"]),
        "combination": str(cfg["combination"]),
        "score_threshold": float(cfg["score_threshold"]),
        "long_signals": int(signal.eq(1).sum()),
        "short_signals": int(signal.eq(-1).sum()),
        "signal_col": str(cfg["signal_col"]),
        "candidate_col": str(cfg["candidate_col"]),
    }


def qms_trend_momentum_vol_signal(df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    """Apply the registered causal QMS trend/momentum/volatility signal.

    YAML declaration::

        signals:
          kind: qms_trend_momentum_vol
          params:
            combination: trend_momentum_vol
            mode: long_short

    Required input columns
    ----------------------
    The configured QMS trend, momentum, volatility, uncertainty, and
    gap-diagnostic columns.

    Parameters
    ----------
    combination:
        Selects the trend-only, trend/momentum, or full volatility-filtered
        ablation.
    mode:
        One of ``long_only``, ``short_only``, or ``long_short``.
    signal_col, candidate_col:
        Configurable output column names.
    """
    out, _ = build_qms_trend_momentum_vol_signal(df, params)
    return out


__all__ = ["build_qms_trend_momentum_vol_signal", "qms_trend_momentum_vol_signal"]
