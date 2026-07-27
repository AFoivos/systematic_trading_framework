from __future__ import annotations

import math
from numbers import Integral, Real
from typing import Any, Mapping

import numpy as np
import pandas as pd


QMS_ALPHA_STRATEGIES = (
    "kds_pullback_continuation",
    "kalman_residual_reversion",
    "volatility_compression_breakout",
    "lmds_exhaustion_reversal",
    "time_series_momentum",
)

_ALLOWED_MODES = frozenset({"long_only", "short_only", "long_short"})
_COLUMN_KEYS = (
    "trend_col",
    "trend_uncertainty_col",
    "innovation_col",
    "momentum_col",
    "momentum_quality_col",
    "efficiency_col",
    "reversal_pressure_col",
    "exhaustion_col",
    "regime_z_col",
    "fast_slow_ratio_col",
    "vol_of_vol_ratio_col",
    "shock_col",
    "state_uncertainty_col",
    "gap_flag_col",
    "unexpected_gap_col",
    "signal_col",
    "candidate_col",
    "state_col",
    "direction_col",
    "ready_col",
)
_QUANTILE_KEYS = (
    "trend_strength_quantile",
    "trend_weak_quantile",
    "uncertainty_quantile",
    "innovation_quantile",
    "efficiency_quantile",
    "vol_of_vol_quantile",
    "shock_quantile",
    "regime_quantile",
    "fast_slow_quantile",
    "momentum_quantile",
    "momentum_quality_quantile",
    "reversal_pressure_quantile",
    "exhaustion_quantile",
)

_COMMON_DEFAULTS: dict[str, Any] = {
    "strategy": "kds_pullback_continuation",
    "mode": "long_short",
    "lookback_bars": 8064,
    "min_periods": 2016,
    "setup_lookback_bars": 8,
    "signal_on_crossing": True,
    "trend_col": "ktrend_score",
    "trend_uncertainty_col": "ktrend_uncertainty",
    "innovation_col": "kalman_innovation_z",
    "momentum_col": "lmom_score",
    "momentum_quality_col": "qms_momentum_quality",
    "efficiency_col": "lmom_efficiency",
    "reversal_pressure_col": "lmom_reversal_pressure",
    "exhaustion_col": "lmom_exhaustion",
    "regime_z_col": "rlv_regime_z",
    "fast_slow_ratio_col": "rlv_fast_slow_ratio",
    "vol_of_vol_ratio_col": "rlv_vol_of_vol_ratio",
    "shock_col": "rlv_shock_z",
    "state_uncertainty_col": "qms_state_uncertainty",
    "gap_flag_col": "qms_gap_flag",
    "unexpected_gap_col": "qms_unexpected_data_gap",
    "signal_col": "qms_alpha_signal",
    "candidate_col": "qms_alpha_candidate",
    "state_col": "qms_alpha_state",
    "direction_col": "qms_alpha_direction",
    "ready_col": "qms_alpha_threshold_ready",
    "trend_strength_quantile": 0.60,
    "trend_weak_quantile": 0.40,
    "uncertainty_quantile": 0.50,
    "innovation_quantile": 0.90,
    "efficiency_quantile": 0.60,
    "vol_of_vol_quantile": 0.90,
    "shock_quantile": 0.90,
    "regime_quantile": 0.20,
    "fast_slow_quantile": 0.20,
    "momentum_quantile": 0.60,
    "momentum_quality_quantile": 0.60,
    "reversal_pressure_quantile": 0.90,
    "exhaustion_quantile": 0.90,
}

_STRATEGY_DEFAULTS: dict[str, dict[str, float]] = {
    "kds_pullback_continuation": {
        "trend_strength_quantile": 0.60,
        "uncertainty_quantile": 0.50,
        "innovation_quantile": 0.90,
        "vol_of_vol_quantile": 0.90,
    },
    "kalman_residual_reversion": {
        "trend_weak_quantile": 0.40,
        "innovation_quantile": 0.95,
        "efficiency_quantile": 0.40,
        "vol_of_vol_quantile": 0.80,
        "shock_quantile": 0.90,
    },
    "volatility_compression_breakout": {
        "regime_quantile": 0.20,
        "fast_slow_quantile": 0.20,
        "vol_of_vol_quantile": 0.50,
        "shock_quantile": 0.80,
        "momentum_quantile": 0.70,
        "efficiency_quantile": 0.60,
    },
    "lmds_exhaustion_reversal": {
        "trend_strength_quantile": 0.70,
        "reversal_pressure_quantile": 0.90,
        "exhaustion_quantile": 0.90,
        "efficiency_quantile": 0.40,
        "shock_quantile": 0.70,
    },
    "time_series_momentum": {
        "trend_strength_quantile": 0.60,
        "momentum_quantile": 0.60,
        "momentum_quality_quantile": 0.60,
        "efficiency_quantile": 0.60,
        "uncertainty_quantile": 0.50,
        "shock_quantile": 0.90,
    },
}

_REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "kds_pullback_continuation": (
        "trend_col",
        "trend_uncertainty_col",
        "innovation_col",
        "vol_of_vol_ratio_col",
    ),
    "kalman_residual_reversion": (
        "trend_col",
        "innovation_col",
        "efficiency_col",
        "vol_of_vol_ratio_col",
        "shock_col",
    ),
    "volatility_compression_breakout": (
        "trend_col",
        "momentum_col",
        "efficiency_col",
        "regime_z_col",
        "fast_slow_ratio_col",
        "vol_of_vol_ratio_col",
        "shock_col",
    ),
    "lmds_exhaustion_reversal": (
        "trend_col",
        "momentum_col",
        "efficiency_col",
        "reversal_pressure_col",
        "exhaustion_col",
        "shock_col",
    ),
    "time_series_momentum": (
        "trend_col",
        "momentum_col",
        "momentum_quality_col",
        "efficiency_col",
        "state_uncertainty_col",
        "shock_col",
    ),
}

_ALLOWED_KEYS = frozenset(
    {
        "strategy",
        "mode",
        "lookback_bars",
        "min_periods",
        "setup_lookback_bars",
        "signal_on_crossing",
        *_COLUMN_KEYS,
        *_QUANTILE_KEYS,
    }
)


def _merge_cfg(
    signal_cfg: Mapping[str, Any] | None,
    overrides: Mapping[str, Any],
) -> dict[str, Any]:
    raw = dict(signal_cfg or {})
    nested = raw.pop("params", None)
    if nested is not None:
        if not isinstance(nested, Mapping):
            raise TypeError("signal_cfg.params must be a mapping when provided.")
        raw.update(dict(nested))
    raw.update(dict(overrides))
    strategy = str(raw.get("strategy", _COMMON_DEFAULTS["strategy"]))
    if strategy not in _STRATEGY_DEFAULTS:
        raise ValueError(f"strategy must be one of: {', '.join(QMS_ALPHA_STRATEGIES)}.")
    cfg = dict(_COMMON_DEFAULTS)
    cfg.update(_STRATEGY_DEFAULTS[strategy])
    cfg.update(raw)
    return cfg


def _validate_cfg(cfg: Mapping[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(cfg).difference(_ALLOWED_KEYS))
    if unknown:
        raise ValueError(f"Unsupported qms_alpha_strategy parameters: {unknown}.")
    out = dict(cfg)
    strategy = str(out["strategy"])
    if strategy not in _STRATEGY_DEFAULTS:
        raise ValueError(f"strategy must be one of: {', '.join(QMS_ALPHA_STRATEGIES)}.")
    mode = str(out["mode"])
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of: {', '.join(sorted(_ALLOWED_MODES))}.")
    out["strategy"] = strategy
    out["mode"] = mode

    for key in ("lookback_bars", "min_periods", "setup_lookback_bars"):
        value = out[key]
        if isinstance(value, bool) or not isinstance(value, Integral) or int(value) <= 0:
            raise ValueError(f"{key} must be a positive integer.")
        out[key] = int(value)
    if out["min_periods"] > out["lookback_bars"]:
        raise ValueError("min_periods must be <= lookback_bars.")
    if out["setup_lookback_bars"] > out["lookback_bars"]:
        raise ValueError("setup_lookback_bars must be <= lookback_bars.")
    if not isinstance(out["signal_on_crossing"], bool):
        raise TypeError("signal_on_crossing must be boolean.")

    for key in _COLUMN_KEYS:
        value = out[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string.")
        out[key] = value.strip()
    for key in _QUANTILE_KEYS:
        value = out[key]
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError(f"{key} must be a finite number in (0, 1).")
        resolved = float(value)
        if not math.isfinite(resolved) or not 0.0 < resolved < 1.0:
            raise ValueError(f"{key} must be a finite number in (0, 1).")
        out[key] = resolved
    return out


def validate_qms_alpha_strategy_params(params: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate signal parameters without requiring a feature frame."""
    if params is not None and not isinstance(params, Mapping):
        raise TypeError("qms_alpha_strategy params must be a mapping.")
    return _validate_cfg(_merge_cfg(params, {}))


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise KeyError(f"Missing column for qms_alpha_strategy: {column}")
    values = pd.to_numeric(frame[column], errors="coerce").astype("float64")
    invalid = values.isna() & ~frame[column].isna()
    if bool(invalid.any()) or bool(np.isinf(values.to_numpy(dtype=float)).any()):
        raise ValueError(f"{column} must contain only finite numeric values or NaN.")
    return values


def _rolling_quantile(values: pd.Series, *, quantile: float, cfg: Mapping[str, Any]) -> pd.Series:
    return (
        values.rolling(
            window=int(cfg["lookback_bars"]),
            min_periods=int(cfg["min_periods"]),
        )
        .quantile(float(quantile))
        .shift(1)
        .astype("float64")
    )


def _combine_ready(*thresholds: pd.Series) -> pd.Series:
    ready = pd.Series(True, index=thresholds[0].index, dtype=bool)
    for threshold in thresholds:
        ready &= threshold.notna()
    return ready


def _strategy_state(
    frame: pd.DataFrame,
    *,
    cfg: Mapping[str, Any],
) -> tuple[pd.Series, pd.Series, pd.Series]:
    strategy = str(cfg["strategy"])
    keys = (*_REQUIRED_COLUMNS[strategy], "gap_flag_col", "unexpected_gap_col")
    values = {key: _numeric(frame, str(cfg[key])) for key in keys}
    no_gap = values["gap_flag_col"].fillna(1.0).eq(0.0) & values[
        "unexpected_gap_col"
    ].fillna(1.0).eq(0.0)

    if strategy == "kds_pullback_continuation":
        trend = values["trend_col"]
        uncertainty = values["trend_uncertainty_col"]
        innovation = values["innovation_col"]
        vol_of_vol = values["vol_of_vol_ratio_col"]
        trend_threshold = _rolling_quantile(
            trend.abs(), quantile=float(cfg["trend_strength_quantile"]), cfg=cfg
        )
        uncertainty_threshold = _rolling_quantile(
            uncertainty, quantile=float(cfg["uncertainty_quantile"]), cfg=cfg
        )
        innovation_threshold = _rolling_quantile(
            innovation.abs(), quantile=float(cfg["innovation_quantile"]), cfg=cfg
        )
        vol_of_vol_threshold = _rolling_quantile(
            vol_of_vol, quantile=float(cfg["vol_of_vol_quantile"]), cfg=cfg
        )
        ready = _combine_ready(
            trend_threshold,
            uncertainty_threshold,
            innovation_threshold,
            vol_of_vol_threshold,
        )
        direction = np.sign(trend).astype("float64")
        state = (
            ready
            & no_gap
            & trend.abs().ge(trend_threshold)
            & uncertainty.le(uncertainty_threshold)
            & innovation.abs().ge(innovation_threshold)
            & np.sign(innovation).eq(-direction)
            & vol_of_vol.le(vol_of_vol_threshold)
            & direction.ne(0.0)
        )
    elif strategy == "kalman_residual_reversion":
        trend = values["trend_col"]
        innovation = values["innovation_col"]
        efficiency = values["efficiency_col"]
        vol_of_vol = values["vol_of_vol_ratio_col"]
        shock = values["shock_col"]
        trend_threshold = _rolling_quantile(
            trend.abs(), quantile=float(cfg["trend_weak_quantile"]), cfg=cfg
        )
        innovation_threshold = _rolling_quantile(
            innovation.abs(), quantile=float(cfg["innovation_quantile"]), cfg=cfg
        )
        efficiency_threshold = _rolling_quantile(
            efficiency, quantile=float(cfg["efficiency_quantile"]), cfg=cfg
        )
        vol_of_vol_threshold = _rolling_quantile(
            vol_of_vol, quantile=float(cfg["vol_of_vol_quantile"]), cfg=cfg
        )
        shock_threshold = _rolling_quantile(
            shock.abs(), quantile=float(cfg["shock_quantile"]), cfg=cfg
        )
        ready = _combine_ready(
            trend_threshold,
            innovation_threshold,
            efficiency_threshold,
            vol_of_vol_threshold,
            shock_threshold,
        )
        direction = -np.sign(innovation).astype("float64")
        state = (
            ready
            & no_gap
            & trend.abs().le(trend_threshold)
            & innovation.abs().ge(innovation_threshold)
            & efficiency.le(efficiency_threshold)
            & vol_of_vol.le(vol_of_vol_threshold)
            & shock.abs().le(shock_threshold)
            & direction.ne(0.0)
        )
    elif strategy == "volatility_compression_breakout":
        trend = values["trend_col"]
        momentum = values["momentum_col"]
        efficiency = values["efficiency_col"]
        regime_z = values["regime_z_col"]
        fast_slow = values["fast_slow_ratio_col"]
        vol_of_vol = values["vol_of_vol_ratio_col"]
        shock = values["shock_col"]
        regime_threshold = _rolling_quantile(
            regime_z, quantile=float(cfg["regime_quantile"]), cfg=cfg
        )
        fast_slow_threshold = _rolling_quantile(
            fast_slow, quantile=float(cfg["fast_slow_quantile"]), cfg=cfg
        )
        vol_of_vol_threshold = _rolling_quantile(
            vol_of_vol, quantile=float(cfg["vol_of_vol_quantile"]), cfg=cfg
        )
        shock_threshold = _rolling_quantile(
            shock, quantile=float(cfg["shock_quantile"]), cfg=cfg
        )
        momentum_threshold = _rolling_quantile(
            momentum.abs(), quantile=float(cfg["momentum_quantile"]), cfg=cfg
        )
        efficiency_threshold = _rolling_quantile(
            efficiency, quantile=float(cfg["efficiency_quantile"]), cfg=cfg
        )
        ready = _combine_ready(
            regime_threshold,
            fast_slow_threshold,
            vol_of_vol_threshold,
            shock_threshold,
            momentum_threshold,
            efficiency_threshold,
        )
        compression = (
            ready
            & no_gap
            & regime_z.le(regime_threshold)
            & fast_slow.le(fast_slow_threshold)
            & vol_of_vol.le(vol_of_vol_threshold)
        )
        armed = (
            compression.shift(1, fill_value=False)
            .rolling(int(cfg["setup_lookback_bars"]), min_periods=1)
            .max()
            .fillna(0.0)
            .astype(bool)
        )
        direction = np.sign(momentum).astype("float64")
        state = (
            ready
            & no_gap
            & armed
            & shock.ge(shock_threshold)
            & momentum.abs().ge(momentum_threshold)
            & efficiency.ge(efficiency_threshold)
            & np.sign(trend).eq(direction)
            & direction.ne(0.0)
        )
    elif strategy == "lmds_exhaustion_reversal":
        trend = values["trend_col"]
        momentum = values["momentum_col"]
        efficiency = values["efficiency_col"]
        reversal_pressure = values["reversal_pressure_col"]
        exhaustion = values["exhaustion_col"]
        shock = values["shock_col"]
        trend_threshold = _rolling_quantile(
            trend.abs(), quantile=float(cfg["trend_strength_quantile"]), cfg=cfg
        )
        reversal_threshold = _rolling_quantile(
            reversal_pressure,
            quantile=float(cfg["reversal_pressure_quantile"]),
            cfg=cfg,
        )
        exhaustion_threshold = _rolling_quantile(
            exhaustion, quantile=float(cfg["exhaustion_quantile"]), cfg=cfg
        )
        efficiency_threshold = _rolling_quantile(
            efficiency, quantile=float(cfg["efficiency_quantile"]), cfg=cfg
        )
        shock_threshold = _rolling_quantile(
            shock.abs(), quantile=float(cfg["shock_quantile"]), cfg=cfg
        )
        ready = _combine_ready(
            trend_threshold,
            reversal_threshold,
            exhaustion_threshold,
            efficiency_threshold,
            shock_threshold,
        )
        direction = np.sign(momentum).astype("float64")
        state = (
            ready
            & no_gap
            & trend.abs().ge(trend_threshold)
            & (
                reversal_pressure.ge(reversal_threshold)
                | exhaustion.ge(exhaustion_threshold)
            )
            & efficiency.le(efficiency_threshold)
            & shock.abs().ge(shock_threshold)
            & np.sign(trend).eq(-direction)
            & direction.ne(0.0)
        )
    else:
        trend = values["trend_col"]
        momentum = values["momentum_col"]
        momentum_quality = values["momentum_quality_col"]
        efficiency = values["efficiency_col"]
        state_uncertainty = values["state_uncertainty_col"]
        shock = values["shock_col"]
        trend_threshold = _rolling_quantile(
            trend.abs(), quantile=float(cfg["trend_strength_quantile"]), cfg=cfg
        )
        momentum_threshold = _rolling_quantile(
            momentum.abs(), quantile=float(cfg["momentum_quantile"]), cfg=cfg
        )
        quality_threshold = _rolling_quantile(
            momentum_quality,
            quantile=float(cfg["momentum_quality_quantile"]),
            cfg=cfg,
        )
        efficiency_threshold = _rolling_quantile(
            efficiency, quantile=float(cfg["efficiency_quantile"]), cfg=cfg
        )
        uncertainty_threshold = _rolling_quantile(
            state_uncertainty, quantile=float(cfg["uncertainty_quantile"]), cfg=cfg
        )
        shock_threshold = _rolling_quantile(
            shock.abs(), quantile=float(cfg["shock_quantile"]), cfg=cfg
        )
        ready = _combine_ready(
            trend_threshold,
            momentum_threshold,
            quality_threshold,
            efficiency_threshold,
            uncertainty_threshold,
            shock_threshold,
        )
        direction = np.sign(trend).astype("float64")
        state = (
            ready
            & no_gap
            & trend.abs().ge(trend_threshold)
            & momentum.abs().ge(momentum_threshold)
            & momentum_quality.ge(quality_threshold)
            & efficiency.ge(efficiency_threshold)
            & state_uncertainty.le(uncertainty_threshold)
            & shock.abs().le(shock_threshold)
            & np.sign(momentum).eq(direction)
            & direction.ne(0.0)
        )

    return state.fillna(False), direction.where(ready), ready.fillna(False)


def build_qms_alpha_strategy_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build one of five causal QMS alpha hypotheses from rolling past-only thresholds."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")
    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))
    out = df.copy()
    state, direction, ready = _strategy_state(out, cfg=cfg)

    if str(cfg["mode"]) == "long_only":
        state &= direction.gt(0.0)
    elif str(cfg["mode"]) == "short_only":
        state &= direction.lt(0.0)

    entry = state
    if bool(cfg["signal_on_crossing"]):
        entry = state & ~state.shift(1, fill_value=False)

    signal = pd.Series(0, index=out.index, dtype="int8")
    signal.loc[entry & direction.gt(0.0)] = 1
    signal.loc[entry & direction.lt(0.0)] = -1

    out[str(cfg["ready_col"])] = ready.astype("int8")
    out[str(cfg["direction_col"])] = direction.astype("float64")
    out[str(cfg["state_col"])] = state.astype("int8")
    out[str(cfg["signal_col"])] = signal
    out[str(cfg["candidate_col"])] = signal.ne(0).astype("int8")
    return out, {
        "kind": "qms_alpha_strategy",
        "strategy": str(cfg["strategy"]),
        "mode": str(cfg["mode"]),
        "lookback_bars": int(cfg["lookback_bars"]),
        "min_periods": int(cfg["min_periods"]),
        "long_signals": int(signal.eq(1).sum()),
        "short_signals": int(signal.eq(-1).sum()),
        "signal_col": str(cfg["signal_col"]),
        "candidate_col": str(cfg["candidate_col"]),
    }


def qms_alpha_strategy_signal(df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    """
    Apply the registered ``qms_alpha_strategy`` signal transformation.

    The transform implements five explicit QMS alpha hypotheses. All adaptive
    thresholds are rolling quantiles shifted by one bar, so the current signal
    uses only information available before or at the current closed bar.

    YAML declaration::

        signals:
          kind: qms_alpha_strategy
          params:
            strategy: kds_pullback_continuation
            lookback_bars: 8064
            min_periods: 2016
            signal_on_crossing: true
            signal_col: qms_alpha_signal
            candidate_col: qms_alpha_candidate

    Required input columns
    ----------------------
    Common:
        ``qms_gap_flag`` and ``qms_unexpected_data_gap``.
    Strategy-specific:
        Selected KDS, RLVS, and LMDS columns configured by the ``*_col``
        parameters. The default names are produced by ``quant_market_state``.

    Parameters
    ----------
    strategy:
        One of ``kds_pullback_continuation``, ``kalman_residual_reversion``,
        ``volatility_compression_breakout``, ``lmds_exhaustion_reversal``, or
        ``time_series_momentum``.
    lookback_bars:
        Past-only rolling threshold window. Default: ``8064``.
    min_periods:
        Minimum past observations before signals are eligible. Default: ``2016``.
    signal_on_crossing:
        Emit only state transitions when true. Default: ``true``.
    signal_col:
        Output side column containing ``-1``, ``0``, or ``1``.
    candidate_col:
        Output event-candidate flag.
    """
    out, _ = build_qms_alpha_strategy_signal(df, params)
    return out


__all__ = [
    "QMS_ALPHA_STRATEGIES",
    "build_qms_alpha_strategy_signal",
    "qms_alpha_strategy_signal",
    "validate_qms_alpha_strategy_params",
]
