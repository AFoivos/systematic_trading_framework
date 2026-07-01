from __future__ import annotations

from collections.abc import Mapping
from numbers import Real
from typing import Any

import numpy as np
import pandas as pd


_DEFAULT_CFG: dict[str, Any] = {
    "mode": "long_short",
    "enabled_modes": None,
    "close_col": "close",
    "high_col": "high",
    "low_col": "low",
    "atr_col": "atr_14",
    "vwap_distance_col": "close_minus_vwap_20_atr",
    "vpin_rank_col": "vpin_proxy_50_rank_252",
    "ofi_fast_col": "ofi_proxy_5_norm",
    "ofi_slow_col": "ofi_proxy_15_norm",
    "spread_rank_col": "spread_bps_rank_252",
    "spread_z_col": "spread_bps_z_252",
    "volume_relative_col": "volume_relative_48",
    "close_pos_col": "close_pos_in_bar",
    "bar_range_atr_col": "bar_range_atr",
    "bar_body_atr_col": "bar_body_atr",
    "upper_wick_atr_col": "upper_wick_atr",
    "lower_wick_atr_col": "lower_wick_atr",
    "support_distance_col": "close_minus_support_atr",
    "resistance_distance_col": "resistance_minus_close_atr",
    "session_filter_col": "session_london_ny_liquid",
    "max_spread_rank": 0.85,
    "max_spread_z": 2.5,
    "toxic_min_vpin_rank": 0.70,
    "toxic_long_min_ofi_fast": 0.20,
    "toxic_long_min_ofi_slow": 0.05,
    "toxic_short_max_ofi_fast": -0.20,
    "toxic_short_max_ofi_slow": -0.05,
    "toxic_min_volume_relative": 1.10,
    "toxic_long_min_close_pos": 0.70,
    "toxic_short_max_close_pos": 0.30,
    "sweep_min_wick_atr": 0.35,
    "sweep_long_min_close_pos": 0.60,
    "sweep_short_max_close_pos": 0.40,
    "sweep_min_bar_range_atr": 0.60,
    "sweep_max_support_distance_atr": 0.35,
    "sweep_max_resistance_distance_atr": 0.35,
    "snapback_vwap_distance_atr": 1.0,
    "snapback_max_vpin_rank": 0.80,
    "snapback_min_wick_atr": 0.25,
    "snapback_long_min_close_pos": 0.55,
    "snapback_short_max_close_pos": 0.45,
    "candidate_col": "signal_candidate",
    "signal_col": "signal_side",
    "mode_col": "signal_mode",
    "score_col": "quote_flow_score",
    "spread_ok_col": "qfs_cond_spread_ok",
    "session_ok_col": "qfs_cond_session_ok",
    "toxic_long_col": "qfs_cond_toxic_flow_long",
    "toxic_short_col": "qfs_cond_toxic_flow_short",
    "sweep_long_col": "qfs_cond_sweep_fade_long",
    "sweep_short_col": "qfs_cond_sweep_fade_short",
    "snapback_long_col": "qfs_cond_vwap_snapback_long",
    "snapback_short_col": "qfs_cond_vwap_snapback_short",
}

_ALLOWED_MODES = frozenset({"long_only", "short_only", "long_short"})


def build_quote_flow_scalp_router_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build quote/spread-aware primary scalp candidates from existing features."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))
    required = [
        cfg["close_col"],
        cfg["high_col"],
        cfg["low_col"],
        cfg["atr_col"],
        cfg["vwap_distance_col"],
        cfg["vpin_rank_col"],
        cfg["ofi_fast_col"],
        cfg["ofi_slow_col"],
        cfg["spread_rank_col"],
        cfg["spread_z_col"],
        cfg["volume_relative_col"],
        cfg["close_pos_col"],
        cfg["bar_range_atr_col"],
        cfg["bar_body_atr_col"],
        cfg["upper_wick_atr_col"],
        cfg["lower_wick_atr_col"],
        cfg["support_distance_col"],
        cfg["resistance_distance_col"],
    ]
    session_col = cfg.get("session_filter_col")
    if session_col is not None:
        required.append(session_col)
    _require_columns(df, required)

    out = df.copy()
    vwap_distance = _numeric(out, cfg["vwap_distance_col"])
    vpin_rank = _numeric(out, cfg["vpin_rank_col"])
    ofi_fast = _numeric(out, cfg["ofi_fast_col"])
    ofi_slow = _numeric(out, cfg["ofi_slow_col"])
    spread_rank = _numeric(out, cfg["spread_rank_col"])
    spread_z = _numeric(out, cfg["spread_z_col"])
    volume_relative = _numeric(out, cfg["volume_relative_col"])
    close_pos = _numeric(out, cfg["close_pos_col"])
    bar_range_atr = _numeric(out, cfg["bar_range_atr_col"])
    bar_body_atr = _numeric(out, cfg["bar_body_atr_col"])
    upper_wick_atr = _numeric(out, cfg["upper_wick_atr_col"])
    lower_wick_atr = _numeric(out, cfg["lower_wick_atr_col"])
    support_distance = _numeric(out, cfg["support_distance_col"])
    resistance_distance = _numeric(out, cfg["resistance_distance_col"])

    spread_ok = (
        spread_rank.notna()
        & spread_z.notna()
        & spread_rank.le(float(cfg["max_spread_rank"]))
        & spread_z.abs().le(float(cfg["max_spread_z"]))
    )
    if session_col is None:
        session_ok = pd.Series(True, index=out.index, dtype=bool)
    else:
        session_ok = _numeric(out, session_col).fillna(0.0).eq(1.0)
    filters_ok = spread_ok & session_ok

    toxic_long = (
        filters_ok
        & vpin_rank.ge(float(cfg["toxic_min_vpin_rank"]))
        & ofi_fast.ge(float(cfg["toxic_long_min_ofi_fast"]))
        & ofi_slow.ge(float(cfg["toxic_long_min_ofi_slow"]))
        & volume_relative.ge(float(cfg["toxic_min_volume_relative"]))
        & close_pos.ge(float(cfg["toxic_long_min_close_pos"]))
        & bar_body_atr.gt(0.0)
    )
    toxic_short = (
        filters_ok
        & vpin_rank.ge(float(cfg["toxic_min_vpin_rank"]))
        & ofi_fast.le(float(cfg["toxic_short_max_ofi_fast"]))
        & ofi_slow.le(float(cfg["toxic_short_max_ofi_slow"]))
        & volume_relative.ge(float(cfg["toxic_min_volume_relative"]))
        & close_pos.le(float(cfg["toxic_short_max_close_pos"]))
        & bar_body_atr.lt(0.0)
    )
    sweep_long = (
        filters_ok
        & lower_wick_atr.ge(float(cfg["sweep_min_wick_atr"]))
        & close_pos.ge(float(cfg["sweep_long_min_close_pos"]))
        & bar_range_atr.ge(float(cfg["sweep_min_bar_range_atr"]))
        & support_distance.le(float(cfg["sweep_max_support_distance_atr"]))
        & ofi_fast.lt(0.0)
    )
    sweep_short = (
        filters_ok
        & upper_wick_atr.ge(float(cfg["sweep_min_wick_atr"]))
        & close_pos.le(float(cfg["sweep_short_max_close_pos"]))
        & bar_range_atr.ge(float(cfg["sweep_min_bar_range_atr"]))
        & resistance_distance.le(float(cfg["sweep_max_resistance_distance_atr"]))
        & ofi_fast.gt(0.0)
    )
    snapback_long = (
        filters_ok
        & vwap_distance.le(-float(cfg["snapback_vwap_distance_atr"]))
        & vpin_rank.le(float(cfg["snapback_max_vpin_rank"]))
        & lower_wick_atr.ge(float(cfg["snapback_min_wick_atr"]))
        & close_pos.ge(float(cfg["snapback_long_min_close_pos"]))
    )
    snapback_short = (
        filters_ok
        & vwap_distance.ge(float(cfg["snapback_vwap_distance_atr"]))
        & vpin_rank.le(float(cfg["snapback_max_vpin_rank"]))
        & upper_wick_atr.ge(float(cfg["snapback_min_wick_atr"]))
        & close_pos.le(float(cfg["snapback_short_max_close_pos"]))
    )

    if cfg["mode"] == "long_only":
        toxic_short[:] = False
        sweep_short[:] = False
        snapback_short[:] = False
    elif cfg["mode"] == "short_only":
        toxic_long[:] = False
        sweep_long[:] = False
        snapback_long[:] = False

    enabled_modes = cfg["enabled_modes"]
    if enabled_modes is not None:
        if 1 not in enabled_modes:
            toxic_long[:] = False
            toxic_short[:] = False
        if 2 not in enabled_modes:
            sweep_long[:] = False
            sweep_short[:] = False
        if 3 not in enabled_modes:
            snapback_long[:] = False
            snapback_short[:] = False

    side = pd.Series(0, index=out.index, dtype="int8")
    signal_mode = pd.Series(0, index=out.index, dtype="int8")
    score = pd.Series(0.0, index=out.index, dtype="float32")

    # Priority: sweep fade, toxic continuation, VWAP snapback.
    _assign_mode(
        side,
        signal_mode,
        score,
        long_mask=snapback_long,
        short_mask=snapback_short,
        mode_code=3,
        score_value=1.0,
    )
    _assign_mode(
        side,
        signal_mode,
        score,
        long_mask=toxic_long,
        short_mask=toxic_short,
        mode_code=1,
        score_value=2.0,
    )
    _assign_mode(
        side,
        signal_mode,
        score,
        long_mask=sweep_long,
        short_mask=sweep_short,
        mode_code=2,
        score_value=3.0,
    )

    candidate = side.ne(0).astype("int8")
    out[cfg["candidate_col"]] = candidate
    out[cfg["signal_col"]] = side
    out[cfg["mode_col"]] = signal_mode
    out[cfg["score_col"]] = score
    out[cfg["spread_ok_col"]] = spread_ok.astype("int8")
    out[cfg["session_ok_col"]] = session_ok.astype("int8")
    out[cfg["toxic_long_col"]] = toxic_long.astype("int8")
    out[cfg["toxic_short_col"]] = toxic_short.astype("int8")
    out[cfg["sweep_long_col"]] = sweep_long.astype("int8")
    out[cfg["sweep_short_col"]] = sweep_short.astype("int8")
    out[cfg["snapback_long_col"]] = snapback_long.astype("int8")
    out[cfg["snapback_short_col"]] = snapback_short.astype("int8")

    meta = {
        "kind": "quote_flow_scalp_router",
        "mode": cfg["mode"],
        "enabled_modes": list(cfg["enabled_modes"]) if cfg["enabled_modes"] is not None else None,
        "candidate_col": cfg["candidate_col"],
        "signal_col": cfg["signal_col"],
        "candidate_rows": int(candidate.sum()),
        "long_rows": int(side.eq(1).sum()),
        "short_rows": int(side.eq(-1).sum()),
        "mode_counts": {str(key): int(value) for key, value in signal_mode.value_counts(dropna=False).items()},
    }
    return out, meta


def quote_flow_scalp_router_signal(df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    """
    Apply the registered ``quote_flow_scalp_router`` signal transformation.

    This signal builds deterministic scalp candidates from point-in-time
    quote-flow, spread, volume, wick, support/resistance, and session features.

    YAML declaration::

        signals:
          kind: quote_flow_scalp_router
          params:
            mode: long_short
            close_col: close
            atr_col: atr_14
            vwap_distance_col: close_minus_vwap_20_atr
            vpin_rank_col: vpin_proxy_50_rank_252
            ofi_fast_col: ofi_proxy_5_norm
            ofi_slow_col: ofi_proxy_15_norm
            spread_rank_col: spread_bps_rank_252
            spread_z_col: spread_bps_z_252
            volume_relative_col: volume_relative_48
            close_pos_col: close_pos_in_bar
            signal_col: signal_side

    Required input columns
    ----------------------
    close_col, high_col, low_col, atr_col:
        Current-bar price and volatility context.
    vwap_distance_col, vpin_rank_col, ofi_fast_col, ofi_slow_col:
        Current-bar quote-flow and VWAP context.
    spread_rank_col, spread_z_col, volume_relative_col:
        Current-bar liquidity filters.
    close_pos_col, bar_range_atr_col, bar_body_atr_col:
        Current-bar candle structure features.
    upper_wick_atr_col, lower_wick_atr_col:
        Current-bar wick structure features.
    support_distance_col, resistance_distance_col:
        Current-bar support/resistance distance features.
    session_filter_col:
        Optional current-bar liquidity-session filter.

    Parameters
    ----------
    mode:
        One of ``long_only``, ``short_only``, or ``long_short``.
    max_spread_rank, max_spread_z:
        Spread filter thresholds.
    enabled_modes:
        Optional list of router mode codes to keep: ``1`` toxic continuation,
        ``2`` liquidity sweep fade, ``3`` VWAP snapback. ``None`` keeps all
        modes and preserves historical behavior.
    toxic_*, sweep_*, snapback_*:
        Thresholds controlling the three candidate routing modes.
    *_col:
        Input and output column names used by this signal.
    """
    out, _ = build_quote_flow_scalp_router_signal(df, params)
    return out


def _assign_mode(
    side: pd.Series,
    signal_mode: pd.Series,
    score: pd.Series,
    *,
    long_mask: pd.Series,
    short_mask: pd.Series,
    mode_code: int,
    score_value: float,
) -> None:
    long_only = long_mask & ~short_mask
    short_only = short_mask & ~long_mask
    side.loc[long_only] = 1
    side.loc[short_only] = -1
    signal_mode.loc[long_only | short_only] = int(mode_code)
    score.loc[long_only | short_only] = float(score_value)


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
    mode = str(normalized.get("mode", "long_short"))
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of: {sorted(_ALLOWED_MODES)}.")
    normalized["mode"] = mode

    enabled_modes = normalized.get("enabled_modes")
    if enabled_modes is None:
        normalized["enabled_modes"] = None
    else:
        if (
            isinstance(enabled_modes, (str, bytes))
            or not isinstance(enabled_modes, (list, tuple, set))
            or len(enabled_modes) == 0
        ):
            raise ValueError("enabled_modes must be a non-empty list of mode codes or null.")
        parsed_modes: list[int] = []
        for raw_mode in enabled_modes:
            if isinstance(raw_mode, bool) or not isinstance(raw_mode, int):
                raise ValueError("enabled_modes entries must be integers in {1, 2, 3}.")
            if int(raw_mode) not in {1, 2, 3}:
                raise ValueError("enabled_modes entries must be in {1, 2, 3}.")
            if int(raw_mode) not in parsed_modes:
                parsed_modes.append(int(raw_mode))
        normalized["enabled_modes"] = parsed_modes

    optional_cols = {"session_filter_col"}
    for key, default in _DEFAULT_CFG.items():
        if key in optional_cols and normalized.get(key) is None:
            continue
        if key.endswith("_col") or key in {
            "close_col",
            "high_col",
            "low_col",
            "atr_col",
            "mode",
        }:
            if key == "mode":
                continue
            normalized[key] = _string_value(normalized.get(key, default), field=key)

    for key, default in _DEFAULT_CFG.items():
        if key.endswith("_col") or key in {
            "mode",
            "enabled_modes",
            "close_col",
            "high_col",
            "low_col",
            "atr_col",
        }:
            continue
        normalized[key] = _finite_float(normalized.get(key, default), field=key)

    if not 0.0 <= float(normalized["max_spread_rank"]) <= 1.0:
        raise ValueError("max_spread_rank must be in [0, 1].")
    if not 0.0 <= float(normalized["toxic_min_vpin_rank"]) <= 1.0:
        raise ValueError("toxic_min_vpin_rank must be in [0, 1].")
    if not 0.0 <= float(normalized["snapback_max_vpin_rank"]) <= 1.0:
        raise ValueError("snapback_max_vpin_rank must be in [0, 1].")
    return normalized


def _string_value(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value.strip()


def _finite_float(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a finite number.")
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"{field} must be a finite number.")
    return out


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for quote_flow_scalp_router: {missing}")


__all__ = ["build_quote_flow_scalp_router_signal", "quote_flow_scalp_router_signal"]
