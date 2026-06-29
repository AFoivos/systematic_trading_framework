from __future__ import annotations

from numbers import Integral, Real
from typing import Any, Mapping

import pandas as pd


_ALLOWED_ENTRY_MODES = frozenset({"state", "transition"})
_ALLOWED_PULLBACK_MODES = frozenset({"any", "vwap", "supersmoother", "ema"})
_ALLOWED_STOCH_RSI_MODES = frozenset({"k_gt_d"})

_DEFAULT_CFG: dict[str, Any] = {
    "entry_mode": "state",
    "entry_delay_bars": 0,
    "long_only": True,
    "signal_col": "signal_side",
    "candidate_col": "signal_candidate",
    "state_col": "ehlers_trend_pullback_long_state",
    "entry_col": "ehlers_trend_pullback_long_entry",
    "ema_fast_col": "ema_50",
    "ema_slow_col": "ema_100",
    "close_col": "close",
    "mama_col": "mama",
    "fama_col": "fama",
    "decycler_osc_col": "decycler_oscillator_30_60",
    "rolling_r2_col": "rolling_r2_96",
    "trend_slope_vol_ratio_col": "trend_slope_vol_ratio_96",
    "atr_pct_col": "atr_over_price_14",
    "atr_z_col": "atr_over_price_z_252",
    "vov_ratio_col": "vov_atr_96_ratio_192",
    "vwap_distance_atr_col": "close_minus_vwap_20_over_atr_14",
    "supersmoother_distance_atr_col": "close_minus_supersmoother_10_over_atr_14",
    "ema_distance_atr_col": "close_minus_ema_50_over_atr_14",
    "roofing_col": "roofing_filter_48_10",
    "roofing_slope_col": "roofing_filter_48_10_slope",
    "stoch_rsi_k_col": "stoch_rsi_k",
    "stoch_rsi_d_col": "stoch_rsi_d",
    "laguerre_rsi_col": "laguerre_rsi",
    "acp_power_col": "autocorrelation_periodogram_10_48_power",
    "hilbert_amplitude_z_col": "hilbert_amplitude_z_252",
    "hilbert_cycle_ok_col": "hilbert_cycle_ok_64",
    "near_resistance_col": "near_resistance",
    "shock_active_col": "shock_active_window",
    "session_allowed_col": "session_allowed",
    "min_rolling_r2": 0.35,
    "min_decycler_osc": 0.0,
    "min_trend_slope_vol_ratio": 0.0,
    "max_atr_z": 1.5,
    "max_abs_vwap_distance_atr": 1.0,
    "max_abs_supersmoother_distance_atr": 1.0,
    "max_abs_ema_distance_atr": 1.25,
    "require_ema_regime": True,
    "require_mama_fama": True,
    "require_decycler_positive": True,
    "require_rolling_r2": True,
    "require_trend_slope_positive": False,
    "require_atr_z_filter": True,
    "require_pullback_to_value": True,
    "pullback_mode": "any",
    "require_roofing_positive": True,
    "require_roofing_slope_positive": True,
    "require_stoch_rsi_confirmation": True,
    "stoch_rsi_mode": "k_gt_d",
    "require_laguerre_rising": False,
    "laguerre_rsi_min": 0.20,
    "laguerre_rsi_max": 0.85,
    "require_acp_power": False,
    "min_acp_power": 0.10,
    "require_hilbert_amplitude": False,
    "min_hilbert_amplitude_z": 0.0,
    "require_hilbert_cycle_ok": False,
    "avoid_near_resistance": False,
    "avoid_shock_active": True,
    "require_session_allowed": False,
}

_COND_COLS = {
    "ema": "ehlers_tp_cond_ema_regime",
    "mama": "ehlers_tp_cond_mama_fama",
    "decycler": "ehlers_tp_cond_decycler",
    "r2": "ehlers_tp_cond_rolling_r2",
    "volatility": "ehlers_tp_cond_volatility",
    "pullback": "ehlers_tp_cond_pullback",
    "roofing": "ehlers_tp_cond_roofing",
    "stoch": "ehlers_tp_cond_stoch_rsi",
    "cycle": "ehlers_tp_cond_cycle",
    "avoid": "ehlers_tp_cond_avoid",
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


def _string_value(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value.strip()


def _bool_value(value: Any, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{field} must be boolean.")
    return bool(value)


def _finite_number(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a finite number.")
    out = float(value)
    if not pd.notna(out):
        raise ValueError(f"{field} must be a finite number.")
    return out


def _non_negative_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or int(value) < 0:
        raise ValueError(f"{field} must be a non-negative integer.")
    return int(value)


def _validate_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(cfg)
    entry_mode = str(normalized.get("entry_mode", "state"))
    if entry_mode not in _ALLOWED_ENTRY_MODES:
        raise ValueError(f"entry_mode must be one of: {sorted(_ALLOWED_ENTRY_MODES)}.")
    normalized["entry_mode"] = entry_mode
    normalized["entry_delay_bars"] = _non_negative_int(
        normalized.get("entry_delay_bars", 0),
        field="entry_delay_bars",
    )
    pullback_mode = str(normalized.get("pullback_mode", "any"))
    if pullback_mode not in _ALLOWED_PULLBACK_MODES:
        raise ValueError(f"pullback_mode must be one of: {sorted(_ALLOWED_PULLBACK_MODES)}.")
    normalized["pullback_mode"] = pullback_mode
    stoch_mode = str(normalized.get("stoch_rsi_mode", "k_gt_d"))
    if stoch_mode not in _ALLOWED_STOCH_RSI_MODES:
        raise ValueError(f"stoch_rsi_mode must be one of: {sorted(_ALLOWED_STOCH_RSI_MODES)}.")
    normalized["stoch_rsi_mode"] = stoch_mode

    bool_keys = (
        "long_only",
        "require_ema_regime",
        "require_mama_fama",
        "require_decycler_positive",
        "require_rolling_r2",
        "require_trend_slope_positive",
        "require_atr_z_filter",
        "require_pullback_to_value",
        "require_roofing_positive",
        "require_roofing_slope_positive",
        "require_stoch_rsi_confirmation",
        "require_laguerre_rising",
        "require_acp_power",
        "require_hilbert_amplitude",
        "require_hilbert_cycle_ok",
        "avoid_near_resistance",
        "avoid_shock_active",
        "require_session_allowed",
    )
    for key in bool_keys:
        normalized[key] = _bool_value(normalized.get(key), field=key)
    if not normalized["long_only"]:
        raise ValueError("ehlers_trend_pullback_continuation_long is long-only; long_only must be true.")

    string_keys = (
        "signal_col",
        "candidate_col",
        "state_col",
        "entry_col",
        "ema_fast_col",
        "ema_slow_col",
        "close_col",
        "mama_col",
        "fama_col",
        "decycler_osc_col",
        "rolling_r2_col",
        "trend_slope_vol_ratio_col",
        "atr_pct_col",
        "atr_z_col",
        "vov_ratio_col",
        "vwap_distance_atr_col",
        "supersmoother_distance_atr_col",
        "ema_distance_atr_col",
        "roofing_col",
        "roofing_slope_col",
        "stoch_rsi_k_col",
        "stoch_rsi_d_col",
        "laguerre_rsi_col",
        "acp_power_col",
        "hilbert_amplitude_z_col",
        "hilbert_cycle_ok_col",
        "near_resistance_col",
        "shock_active_col",
        "session_allowed_col",
    )
    for key in string_keys:
        normalized[key] = _string_value(normalized.get(key), field=key)

    for key in (
        "min_rolling_r2",
        "min_decycler_osc",
        "min_trend_slope_vol_ratio",
        "max_atr_z",
        "max_abs_vwap_distance_atr",
        "max_abs_supersmoother_distance_atr",
        "max_abs_ema_distance_atr",
        "laguerre_rsi_min",
        "laguerre_rsi_max",
        "min_acp_power",
        "min_hilbert_amplitude_z",
    ):
        normalized[key] = _finite_number(normalized.get(key), field=key)
    if normalized["laguerre_rsi_min"] > normalized["laguerre_rsi_max"]:
        raise ValueError("laguerre_rsi_min must be <= laguerre_rsi_max.")
    return normalized


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in dict.fromkeys(columns) if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for ehlers_trend_pullback_continuation_long_signal: {missing}")


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df[column], errors="coerce").astype(float)


def _true(index: pd.Index) -> pd.Series:
    return pd.Series(True, index=index, dtype=bool)


def _maybe_numeric(df: pd.DataFrame, column: str) -> pd.Series | None:
    if column not in df.columns:
        return None
    return _numeric(df, column)


def build_ehlers_trend_pullback_continuation_long_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build the causal long-only Ehlers trend pullback continuation signal."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))
    required: list[str] = []
    if cfg["require_ema_regime"]:
        required.extend([cfg["ema_fast_col"], cfg["ema_slow_col"]])
    if cfg["require_mama_fama"]:
        required.extend([cfg["mama_col"], cfg["fama_col"]])
    if cfg["require_decycler_positive"]:
        required.append(cfg["decycler_osc_col"])
    if cfg["require_rolling_r2"]:
        required.append(cfg["rolling_r2_col"])
    if cfg["require_trend_slope_positive"]:
        required.append(cfg["trend_slope_vol_ratio_col"])
    if cfg["require_atr_z_filter"]:
        required.append(cfg["atr_z_col"])
    if cfg["require_pullback_to_value"]:
        if cfg["pullback_mode"] in {"any", "vwap"}:
            required.append(cfg["vwap_distance_atr_col"])
        if cfg["pullback_mode"] in {"any", "supersmoother"}:
            required.append(cfg["supersmoother_distance_atr_col"])
        if cfg["pullback_mode"] == "ema":
            required.append(cfg["ema_distance_atr_col"])
    if cfg["require_roofing_positive"]:
        required.append(cfg["roofing_col"])
    if cfg["require_roofing_slope_positive"]:
        required.append(cfg["roofing_slope_col"])
    if cfg["require_stoch_rsi_confirmation"]:
        required.extend([cfg["stoch_rsi_k_col"], cfg["stoch_rsi_d_col"]])
    if cfg["require_laguerre_rising"]:
        required.append(cfg["laguerre_rsi_col"])
    if cfg["require_acp_power"]:
        required.append(cfg["acp_power_col"])
    if cfg["require_hilbert_amplitude"]:
        required.append(cfg["hilbert_amplitude_z_col"])
    if cfg["require_hilbert_cycle_ok"]:
        required.append(cfg["hilbert_cycle_ok_col"])
    if cfg["avoid_near_resistance"]:
        required.append(cfg["near_resistance_col"])
    if cfg["require_session_allowed"]:
        required.append(cfg["session_allowed_col"])
    _require_columns(df, required)

    out = df.copy()
    idx = out.index

    ema_cond = (
        _numeric(out, cfg["ema_fast_col"]).gt(_numeric(out, cfg["ema_slow_col"]))
        if cfg["require_ema_regime"]
        else _true(idx)
    )
    mama_cond = (
        _numeric(out, cfg["mama_col"]).gt(_numeric(out, cfg["fama_col"]))
        if cfg["require_mama_fama"]
        else _true(idx)
    )
    decycler_cond = (
        _numeric(out, cfg["decycler_osc_col"]).ge(cfg["min_decycler_osc"])
        if cfg["require_decycler_positive"]
        else _true(idx)
    )
    r2_cond = (
        _numeric(out, cfg["rolling_r2_col"]).ge(cfg["min_rolling_r2"])
        if cfg["require_rolling_r2"]
        else _true(idx)
    )
    trend_slope_cond = (
        _numeric(out, cfg["trend_slope_vol_ratio_col"]).gt(cfg["min_trend_slope_vol_ratio"])
        if cfg["require_trend_slope_positive"]
        else _true(idx)
    )
    volatility_cond = (
        _numeric(out, cfg["atr_z_col"]).le(cfg["max_atr_z"])
        if cfg["require_atr_z_filter"]
        else _true(idx)
    )

    if cfg["require_pullback_to_value"]:
        vwap_pullback = _numeric(out, cfg["vwap_distance_atr_col"]).abs().le(cfg["max_abs_vwap_distance_atr"])
        smoother_pullback = _numeric(out, cfg["supersmoother_distance_atr_col"]).abs().le(
            cfg["max_abs_supersmoother_distance_atr"]
        )
        ema_series = _maybe_numeric(out, cfg["ema_distance_atr_col"])
        ema_pullback = (
            ema_series.abs().le(cfg["max_abs_ema_distance_atr"])
            if ema_series is not None
            else pd.Series(False, index=idx, dtype=bool)
        )
        if cfg["pullback_mode"] == "vwap":
            pullback_cond = vwap_pullback
        elif cfg["pullback_mode"] == "supersmoother":
            pullback_cond = smoother_pullback
        elif cfg["pullback_mode"] == "ema":
            pullback_cond = ema_pullback
        else:
            pullback_cond = vwap_pullback | smoother_pullback | ema_pullback
    else:
        pullback_cond = _true(idx)

    roofing_parts: list[pd.Series] = []
    if cfg["require_roofing_positive"]:
        roofing_parts.append(_numeric(out, cfg["roofing_col"]).gt(0.0))
    if cfg["require_roofing_slope_positive"]:
        roofing_parts.append(_numeric(out, cfg["roofing_slope_col"]).gt(0.0))
    roofing_cond = roofing_parts[0] if roofing_parts else _true(idx)
    for part in roofing_parts[1:]:
        roofing_cond &= part

    stoch_cond = (
        _numeric(out, cfg["stoch_rsi_k_col"]).gt(_numeric(out, cfg["stoch_rsi_d_col"]))
        if cfg["require_stoch_rsi_confirmation"]
        else _true(idx)
    )
    if cfg["require_laguerre_rising"]:
        laguerre = _numeric(out, cfg["laguerre_rsi_col"])
        laguerre_cond = (
            laguerre.gt(laguerre.shift(1))
            & laguerre.between(cfg["laguerre_rsi_min"], cfg["laguerre_rsi_max"], inclusive="both")
        )
    else:
        laguerre_cond = _true(idx)

    cycle_cond = _true(idx)
    if cfg["require_acp_power"]:
        cycle_cond &= _numeric(out, cfg["acp_power_col"]).ge(cfg["min_acp_power"])
    if cfg["require_hilbert_amplitude"]:
        cycle_cond &= _numeric(out, cfg["hilbert_amplitude_z_col"]).ge(cfg["min_hilbert_amplitude_z"])
    if cfg["require_hilbert_cycle_ok"]:
        cycle_cond &= _numeric(out, cfg["hilbert_cycle_ok_col"]).eq(1.0)

    avoid_cond = _true(idx)
    if cfg["avoid_near_resistance"]:
        avoid_cond &= ~_numeric(out, cfg["near_resistance_col"]).eq(1.0)
    if cfg["avoid_shock_active"] and cfg["shock_active_col"] in out.columns:
        avoid_cond &= ~_numeric(out, cfg["shock_active_col"]).eq(1.0)
    if cfg["require_session_allowed"]:
        avoid_cond &= _numeric(out, cfg["session_allowed_col"]).eq(1.0)

    condition_map = {
        _COND_COLS["ema"]: ema_cond,
        _COND_COLS["mama"]: mama_cond,
        _COND_COLS["decycler"]: decycler_cond,
        _COND_COLS["r2"]: r2_cond & trend_slope_cond,
        _COND_COLS["volatility"]: volatility_cond,
        _COND_COLS["pullback"]: pullback_cond,
        _COND_COLS["roofing"]: roofing_cond,
        _COND_COLS["stoch"]: stoch_cond & laguerre_cond,
        _COND_COLS["cycle"]: cycle_cond,
        _COND_COLS["avoid"]: avoid_cond,
    }
    state = _true(idx)
    for values in condition_map.values():
        state &= values.fillna(False)
    entry = state & ~state.shift(1, fill_value=False)
    selected = state if cfg["entry_mode"] == "state" else entry
    signal = selected.fillna(False).astype("int8")
    if cfg["entry_delay_bars"] > 0:
        signal = signal.shift(cfg["entry_delay_bars"]).fillna(0).astype("int8")

    for col, values in condition_map.items():
        out[col] = values.fillna(False).astype("int8")
    out["ehlers_tp_score"] = sum(out[col].astype("int16") for col in condition_map).astype("int16")
    out[cfg["state_col"]] = state.fillna(False).astype("int8")
    out[cfg["entry_col"]] = entry.fillna(False).astype("int8")
    out[cfg["candidate_col"]] = selected.fillna(False).astype("int8")
    out[cfg["signal_col"]] = signal

    return out, {
        "kind": "ehlers_trend_pullback_continuation_long",
        "entry_mode": cfg["entry_mode"],
        "entry_delay_bars": cfg["entry_delay_bars"],
        "long_only": True,
        "pullback_mode": cfg["pullback_mode"],
        "state_rows": int(state.sum()),
        "entry_rows": int(entry.sum()),
        "candidate_rows": int(out[cfg["candidate_col"]].sum()),
        "signal_rows": int(signal.sum()),
        "state_col": cfg["state_col"],
        "entry_col": cfg["entry_col"],
        "candidate_col": cfg["candidate_col"],
        "signal_col": cfg["signal_col"],
        "condition_cols": sorted(condition_map),
        "score_col": "ehlers_tp_score",
    }


def ehlers_trend_pullback_continuation_long_signal(df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    """
    Apply the registered ``ehlers_trend_pullback_continuation_long`` signal transformation.

    This signal consumes already-built feature/helper columns and writes a
    deterministic long-only candidate/signal without training or target access.

    YAML declaration::

        signals:
          kind: ehlers_trend_pullback_continuation_long
          params:
            entry_mode: state
            entry_delay_bars: 0
            long_only: true
            signal_col: signal_side
            candidate_col: signal_candidate

    Required input columns
    ----------------------
    Configured trend, volatility, pullback and timing columns are required only
    when their corresponding ``require_*`` or avoid filter is enabled.

    Parameters
    ----------
    params:
        Keyword parameters matching ``build_ehlers_trend_pullback_continuation_long_signal``.
    """
    out, _ = build_ehlers_trend_pullback_continuation_long_signal(df, params)
    return out


__all__ = [
    "build_ehlers_trend_pullback_continuation_long_signal",
    "ehlers_trend_pullback_continuation_long_signal",
]
