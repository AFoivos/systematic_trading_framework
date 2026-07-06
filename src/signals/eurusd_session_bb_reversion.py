from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd


_DEFAULT_CFG: dict[str, Any] = {
    "bb_percent_b_col": "bb_percent_b_40_2.0",
    "rsi_col": "close_rsi_28",
    "roc_col": "roc_8",
    "close_over_ema_col": "close_over_ema_200",
    "atr_rank_col": "atr_pct_rank_336",
    "spread_rank_col": "spread_rank_336",
    "is_weekend_col": "is_weekend",
    "timezone": "UTC",
    "start_hour": 7,
    "end_hour": 18,
    "bb_percent_b_max": 0.12,
    "rsi_max": 35.0,
    "roc_max": -0.0005,
    "max_abs_trend": 0.005,
    "min_atr_rank": 0.10,
    "max_atr_rank": 0.80,
    "max_spread_rank": 0.75,
    "signal_col": "signal_side",
    "candidate_col": "signal_candidate",
    "score_col": "eurusd_bb_reversion_score",
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


def _col(value: Any, default: str, *, field: str) -> str:
    resolved = default if value is None else str(value)
    if not resolved.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return resolved.strip()


def _finite_float(value: Any, *, field: str) -> float:
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"{field} must be finite.")
    return out


def _hour(value: Any, *, field: str, upper: int = 24) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer hour.")
    out = int(value)
    if out < 0 or out > upper:
        raise ValueError(f"{field} must be in [0, {upper}].")
    return out


def _validate_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(cfg)
    for key, default in (
        ("bb_percent_b_col", "bb_percent_b_40_2.0"),
        ("rsi_col", "close_rsi_28"),
        ("roc_col", "roc_8"),
        ("close_over_ema_col", "close_over_ema_200"),
        ("atr_rank_col", "atr_pct_rank_336"),
        ("spread_rank_col", "spread_rank_336"),
        ("is_weekend_col", "is_weekend"),
        ("signal_col", "signal_side"),
        ("candidate_col", "signal_candidate"),
        ("score_col", "eurusd_bb_reversion_score"),
    ):
        normalized[key] = _col(normalized.get(key), default, field=key)

    timezone = _col(normalized.get("timezone"), "UTC", field="timezone")
    normalized["timezone"] = timezone
    normalized["start_hour"] = _hour(normalized.get("start_hour", 7), field="start_hour", upper=23)
    normalized["end_hour"] = _hour(normalized.get("end_hour", 18), field="end_hour", upper=24)
    if normalized["start_hour"] == normalized["end_hour"]:
        raise ValueError("start_hour and end_hour must define a non-empty session window.")

    for key in (
        "bb_percent_b_max",
        "rsi_max",
        "roc_max",
        "max_abs_trend",
        "min_atr_rank",
        "max_atr_rank",
        "max_spread_rank",
    ):
        normalized[key] = _finite_float(normalized.get(key), field=key)
    if normalized["min_atr_rank"] > normalized["max_atr_rank"]:
        raise ValueError("min_atr_rank must be <= max_atr_rank.")
    if normalized["max_abs_trend"] < 0.0:
        raise ValueError("max_abs_trend must be >= 0.")
    return normalized


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for eurusd_session_bb_reversion_signal: {missing}")


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def _index_in_timezone(index: pd.Index, timezone: str) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(pd.to_datetime(index, errors="raise"))
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    return idx.tz_convert(timezone)


def _session_mask(index: pd.Index, *, timezone: str, start_hour: int, end_hour: int) -> pd.Series:
    local_idx = _index_in_timezone(index, timezone)
    hours = pd.Index(local_idx.hour, dtype="int32")
    if start_hour < end_hour:
        mask = (hours >= start_hour) & (hours < end_hour)
    else:
        mask = (hours >= start_hour) | (hours < end_hour)
    return pd.Series(mask, index=index, dtype=bool)


def build_eurusd_session_bb_reversion_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))
    required = [
        cfg["bb_percent_b_col"],
        cfg["rsi_col"],
        cfg["roc_col"],
        cfg["close_over_ema_col"],
        cfg["atr_rank_col"],
        cfg["spread_rank_col"],
        cfg["is_weekend_col"],
    ]
    _require_columns(df, required)

    out = df.copy()
    in_session = _session_mask(
        out.index,
        timezone=str(cfg["timezone"]),
        start_hour=int(cfg["start_hour"]),
        end_hour=int(cfg["end_hour"]),
    )
    not_weekend = _numeric(out, str(cfg["is_weekend_col"])).fillna(1.0).eq(0.0)
    bb_ok = _numeric(out, str(cfg["bb_percent_b_col"])).le(float(cfg["bb_percent_b_max"]))
    rsi_ok = _numeric(out, str(cfg["rsi_col"])).le(float(cfg["rsi_max"]))
    pullback_ok = _numeric(out, str(cfg["roc_col"])).le(float(cfg["roc_max"]))
    trend_ok = _numeric(out, str(cfg["close_over_ema_col"])).abs().le(float(cfg["max_abs_trend"]))
    atr_ok = _numeric(out, str(cfg["atr_rank_col"])).between(float(cfg["min_atr_rank"]), float(cfg["max_atr_rank"]))
    spread_ok = _numeric(out, str(cfg["spread_rank_col"])).le(float(cfg["max_spread_rank"]))

    condition_cols = {
        "cond_session": in_session,
        "cond_not_weekend": not_weekend,
        "cond_bb_washout": bb_ok,
        "cond_rsi_washout": rsi_ok,
        "cond_pullback": pullback_ok,
        "cond_flat_medium_trend": trend_ok,
        "cond_atr_regime": atr_ok,
        "cond_spread_regime": spread_ok,
    }
    for name, values in condition_cols.items():
        out[name] = values.fillna(False).astype("int8")

    score = out[list(condition_cols)].sum(axis=1).astype("int16")
    candidate = out[list(condition_cols)].all(axis=1)
    out[str(cfg["score_col"])] = score
    out[str(cfg["candidate_col"])] = candidate.astype("int8")
    out[str(cfg["signal_col"])] = out[str(cfg["candidate_col"])].astype("float32")

    meta = {
        "kind": "eurusd_session_bb_reversion",
        "side": "long_only",
        "conditions": list(condition_cols),
        "params": {key: cfg[key] for key in sorted(cfg)},
        "candidate_rows": int(out[str(cfg["candidate_col"])].sum()),
    }
    return out, meta


def eurusd_session_bb_reversion_signal(df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    """
    Apply the registered ``eurusd_session_bb_reversion`` signal transformation.

    This signal uses current-bar and trailing feature columns only. It emits a
    long-only candidate for EURUSD 30m session Bollinger/RSI washout
    mean-reversion research.

    YAML declaration::

        signals:
          kind: eurusd_session_bb_reversion
          params:
            bb_percent_b_col: bb_percent_b_40_2.0
            rsi_col: close_rsi_28
            roc_col: roc_8
            close_over_ema_col: close_over_ema_200
            atr_rank_col: atr_pct_rank_336
            spread_rank_col: spread_rank_336
            is_weekend_col: is_weekend
            timezone: UTC
            start_hour: 7
            end_hour: 18
            bb_percent_b_max: 0.12
            rsi_max: 35.0
            roc_max: -0.0005
            max_abs_trend: 0.005
            min_atr_rank: 0.10
            max_atr_rank: 0.80
            max_spread_rank: 0.75
            signal_col: signal_side
            candidate_col: signal_candidate
            score_col: eurusd_bb_reversion_score

    Required input columns
    ----------------------
    bb_percent_b_col:
        Bollinger percent-B feature.
    rsi_col:
        RSI feature.
    roc_col:
        Trailing return or ROC feature.
    close_over_ema_col:
        Close-over-EMA trend distance feature.
    atr_rank_col:
        ATR percent-rank regime feature.
    spread_rank_col:
        Spread percent-rank feature.
    is_weekend_col:
        Weekend flag where 0 means tradable weekday.

    Parameters
    ----------
    params:
        Signal parameter overrides for columns, thresholds, session hours, and
        output columns.
    """
    out, _ = build_eurusd_session_bb_reversion_signal(df, params)
    return out


__all__ = ["build_eurusd_session_bb_reversion_signal", "eurusd_session_bb_reversion_signal"]
