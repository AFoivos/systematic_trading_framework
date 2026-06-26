from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd


_DEFAULT_CFG: dict[str, Any] = {
    "close_col": "close",
    "ema_fast": 20,
    "ema_mid": 50,
    "ema_slow": 100,
    "ema_fast_col": None,
    "ema_mid_col": None,
    "ema_slow_col": None,
    "ema_slope_fast_col": None,
    "ema_slope_mid_col": None,
    "adx_col": None,
    "min_adx": 18.0,
    "max_adx": 45.0,
    "rsi_col": None,
    "rsi_long_min": 45.0,
    "rsi_long_max": 68.0,
    "rsi_short_min": 32.0,
    "rsi_short_max": 55.0,
    "stoch_k_col": "stoch_rsi_k",
    "stoch_d_col": "stoch_rsi_d",
    "stoch_cross_up_col": "stoch_rsi_cross_up",
    "stoch_cross_down_col": "stoch_rsi_cross_down",
    "stoch_long_max": 60.0,
    "stoch_short_min": 40.0,
    "macd_hist_col": "macd_hist",
    "macd_hist_slope_col": "macd_hist_slope",
    "require_macd_confirmation": True,
    "atr_pct_rank_col": None,
    "min_atr_pct_rank": 0.20,
    "max_atr_pct_rank": 0.90,
    "bb_bandwidth_col": "bollinger_bandwidth",
    "bb_bandwidth_rank_col": "bollinger_bandwidth_rank_100",
    "min_bb_bandwidth": 0.0,
    "min_bb_bandwidth_rank": 0.20,
    "distance_ema_fast_atr_col": None,
    "max_distance_from_ema_atr": 0.75,
    "candidate_long_col": "candidate_long",
    "candidate_short_col": "candidate_short",
    "direction_col": "direction",
    "signal_col": "signal",
    "candidate_col": "signal_candidate",
    "signal_name_col": "signal_name",
    "score_col": "signal_score",
    "signal_name": "indicator_model_adaptive_pullback",
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


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for indicator_model_adaptive_pullback: {missing}")


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def _finite_float(value: Any, *, field: str) -> float:
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"{field} must be finite.")
    return out


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or int(value) <= 0:
        raise ValueError(f"{field} must be a positive integer.")
    return int(value)


def _stoch_threshold(value: Any, *, field: str) -> float:
    threshold = _finite_float(value, field=field)
    if threshold > 1.0:
        threshold = threshold / 100.0
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"{field} must be in [0, 1] or [0, 100].")
    return threshold


def _col(value: Any, default: str, *, field: str) -> str:
    resolved = default if value is None else str(value)
    if not resolved.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return resolved.strip()


def _validate_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(cfg)
    ema_fast = _positive_int(normalized.get("ema_fast", 20), field="ema_fast")
    ema_mid = _positive_int(normalized.get("ema_mid", 50), field="ema_mid")
    ema_slow = _positive_int(normalized.get("ema_slow", 100), field="ema_slow")
    if not ema_fast < ema_mid < ema_slow:
        raise ValueError("EMA periods must satisfy ema_fast < ema_mid < ema_slow.")
    normalized["ema_fast"] = ema_fast
    normalized["ema_mid"] = ema_mid
    normalized["ema_slow"] = ema_slow

    normalized["close_col"] = _col(normalized.get("close_col"), "close", field="close_col")
    normalized["ema_fast_col"] = _col(
        normalized.get("ema_fast_col"),
        f"ema_{ema_fast}",
        field="ema_fast_col",
    )
    normalized["ema_mid_col"] = _col(
        normalized.get("ema_mid_col"),
        f"ema_{ema_mid}",
        field="ema_mid_col",
    )
    normalized["ema_slow_col"] = _col(
        normalized.get("ema_slow_col"),
        f"ema_{ema_slow}",
        field="ema_slow_col",
    )
    normalized["ema_slope_fast_col"] = _col(
        normalized.get("ema_slope_fast_col"),
        f"ema_slope_{ema_fast}",
        field="ema_slope_fast_col",
    )
    normalized["ema_slope_mid_col"] = _col(
        normalized.get("ema_slope_mid_col"),
        f"ema_slope_{ema_mid}",
        field="ema_slope_mid_col",
    )
    normalized["adx_col"] = _col(normalized.get("adx_col"), "adx_14", field="adx_col")
    normalized["rsi_col"] = _col(normalized.get("rsi_col"), "rsi_14", field="rsi_col")
    normalized["atr_pct_rank_col"] = _col(
        normalized.get("atr_pct_rank_col"),
        "atr_pct_rank_100",
        field="atr_pct_rank_col",
    )
    normalized["distance_ema_fast_atr_col"] = _col(
        normalized.get("distance_ema_fast_atr_col"),
        f"distance_from_ema{ema_fast}_atr",
        field="distance_ema_fast_atr_col",
    )

    string_keys = (
        "stoch_k_col",
        "stoch_d_col",
        "stoch_cross_up_col",
        "stoch_cross_down_col",
        "macd_hist_col",
        "macd_hist_slope_col",
        "bb_bandwidth_col",
        "candidate_long_col",
        "candidate_short_col",
        "direction_col",
        "signal_col",
        "candidate_col",
        "signal_name_col",
        "score_col",
        "signal_name",
    )
    for key in string_keys:
        normalized[key] = _col(normalized.get(key), str(_DEFAULT_CFG[key]), field=key)

    bb_rank_col = normalized.get("bb_bandwidth_rank_col")
    if bb_rank_col is not None:
        normalized["bb_bandwidth_rank_col"] = _col(
            bb_rank_col,
            "bollinger_bandwidth_rank_100",
            field="bb_bandwidth_rank_col",
        )

    for key in (
        "min_adx",
        "max_adx",
        "rsi_long_min",
        "rsi_long_max",
        "rsi_short_min",
        "rsi_short_max",
        "min_atr_pct_rank",
        "max_atr_pct_rank",
        "min_bb_bandwidth",
        "min_bb_bandwidth_rank",
        "max_distance_from_ema_atr",
    ):
        normalized[key] = _finite_float(normalized.get(key), field=key)

    if normalized["min_adx"] > normalized["max_adx"]:
        raise ValueError("min_adx must be <= max_adx.")
    if normalized["rsi_long_min"] >= normalized["rsi_long_max"]:
        raise ValueError("rsi_long_min must be < rsi_long_max.")
    if normalized["rsi_short_min"] >= normalized["rsi_short_max"]:
        raise ValueError("rsi_short_min must be < rsi_short_max.")
    if normalized["min_atr_pct_rank"] >= normalized["max_atr_pct_rank"]:
        raise ValueError("min_atr_pct_rank must be < max_atr_pct_rank.")
    if normalized["max_distance_from_ema_atr"] < 0.0:
        raise ValueError("max_distance_from_ema_atr must be >= 0.")

    normalized["stoch_long_max"] = _stoch_threshold(
        normalized.get("stoch_long_max"),
        field="stoch_long_max",
    )
    normalized["stoch_short_min"] = _stoch_threshold(
        normalized.get("stoch_short_min"),
        field="stoch_short_min",
    )
    if not isinstance(normalized.get("require_macd_confirmation"), bool):
        raise TypeError("require_macd_confirmation must be boolean.")
    return normalized


def _between_inclusive(series: pd.Series, low: pd.Series, high: pd.Series) -> pd.Series:
    lower = pd.concat([low, high], axis=1).min(axis=1)
    upper = pd.concat([low, high], axis=1).max(axis=1)
    return series.ge(lower) & series.le(upper)


def build_indicator_model_adaptive_pullback_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Build causal indicator-only long/short pullback candidates.

    The emitted ``signal`` is the candidate direction before model filtering. The final
    model-approved signal is expected to be produced later by ``meta_probability_side``.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))
    bb_rank_col = cfg.get("bb_bandwidth_rank_col")
    required = [
        cfg["close_col"],
        cfg["ema_fast_col"],
        cfg["ema_mid_col"],
        cfg["ema_slow_col"],
        cfg["ema_slope_fast_col"],
        cfg["ema_slope_mid_col"],
        cfg["adx_col"],
        cfg["rsi_col"],
        cfg["stoch_k_col"],
        cfg["stoch_d_col"],
        cfg["stoch_cross_up_col"],
        cfg["stoch_cross_down_col"],
        cfg["macd_hist_col"],
        cfg["macd_hist_slope_col"],
        cfg["atr_pct_rank_col"],
        cfg["bb_bandwidth_col"],
        cfg["distance_ema_fast_atr_col"],
    ]
    if bb_rank_col is not None:
        required.append(str(bb_rank_col))
    _require_columns(df, list(dict.fromkeys(str(col) for col in required)))

    out = df.copy()
    close = _numeric(out, cfg["close_col"])
    ema_fast = _numeric(out, cfg["ema_fast_col"])
    ema_mid = _numeric(out, cfg["ema_mid_col"])
    ema_slow = _numeric(out, cfg["ema_slow_col"])
    ema_slope_fast = _numeric(out, cfg["ema_slope_fast_col"])
    ema_slope_mid = _numeric(out, cfg["ema_slope_mid_col"])
    adx = _numeric(out, cfg["adx_col"])
    rsi = _numeric(out, cfg["rsi_col"])
    stoch_k = _numeric(out, cfg["stoch_k_col"])
    stoch_d = _numeric(out, cfg["stoch_d_col"])
    stoch_cross_up = _numeric(out, cfg["stoch_cross_up_col"]).fillna(0.0).ne(0.0)
    stoch_cross_down = _numeric(out, cfg["stoch_cross_down_col"]).fillna(0.0).ne(0.0)
    macd_hist = _numeric(out, cfg["macd_hist_col"])
    macd_hist_slope = _numeric(out, cfg["macd_hist_slope_col"])
    atr_pct_rank = _numeric(out, cfg["atr_pct_rank_col"])
    bb_bandwidth = _numeric(out, cfg["bb_bandwidth_col"])
    distance_fast_atr = _numeric(out, cfg["distance_ema_fast_atr_col"])

    required_valid = (
        close.notna()
        & ema_fast.notna()
        & ema_mid.notna()
        & ema_slow.notna()
        & ema_slope_fast.notna()
        & ema_slope_mid.notna()
        & adx.notna()
        & rsi.notna()
        & stoch_k.notna()
        & stoch_d.notna()
        & macd_hist.notna()
        & macd_hist_slope.notna()
        & atr_pct_rank.notna()
        & bb_bandwidth.notna()
        & distance_fast_atr.notna()
    )
    if bb_rank_col is not None:
        bb_bandwidth_rank = _numeric(out, str(bb_rank_col))
        required_valid &= bb_bandwidth_rank.notna()
        bb_ok = bb_bandwidth_rank.ge(float(cfg["min_bb_bandwidth_rank"]))
    else:
        bb_ok = bb_bandwidth.gt(float(cfg["min_bb_bandwidth"]))

    adx_ok = adx.between(float(cfg["min_adx"]), float(cfg["max_adx"]))
    volatility_ok = (
        atr_pct_rank.between(float(cfg["min_atr_pct_rank"]), float(cfg["max_atr_pct_rank"]))
        & bb_ok
    )

    trend_up = (
        ema_fast.gt(ema_mid)
        & ema_mid.gt(ema_slow)
        & ema_slope_fast.gt(0.0)
        & ema_slope_mid.gt(0.0)
        & adx_ok
    )
    trend_down = (
        ema_fast.lt(ema_mid)
        & ema_mid.lt(ema_slow)
        & ema_slope_fast.lt(0.0)
        & ema_slope_mid.lt(0.0)
        & adx_ok
    )

    pullback_ok = (
        (_between_inclusive(close, ema_fast, ema_mid) | distance_fast_atr.le(float(cfg["max_distance_from_ema_atr"])))
        & distance_fast_atr.le(float(cfg["max_distance_from_ema_atr"]))
    )

    macd_long_ok = macd_hist_slope.ge(0.0) | macd_hist.ge(macd_hist.shift(1))
    macd_short_ok = macd_hist_slope.le(0.0) | macd_hist.le(macd_hist.shift(1))
    if not bool(cfg["require_macd_confirmation"]):
        macd_long_ok = pd.Series(True, index=out.index)
        macd_short_ok = pd.Series(True, index=out.index)

    momentum_long = (
        stoch_cross_up
        & stoch_k.lt(float(cfg["stoch_long_max"]))
        & rsi.between(float(cfg["rsi_long_min"]), float(cfg["rsi_long_max"]))
        & macd_long_ok
    )
    momentum_short = (
        stoch_cross_down
        & stoch_k.gt(float(cfg["stoch_short_min"]))
        & rsi.between(float(cfg["rsi_short_min"]), float(cfg["rsi_short_max"]))
        & macd_short_ok
    )

    candidate_long = trend_up & pullback_ok & momentum_long & volatility_ok & required_valid
    candidate_short = trend_down & pullback_ok & momentum_short & volatility_ok & required_valid
    ambiguous = candidate_long & candidate_short
    candidate_long &= ~ambiguous
    candidate_short &= ~ambiguous

    direction = pd.Series(0, index=out.index, dtype="int8")
    direction.loc[candidate_long] = 1
    direction.loc[candidate_short] = -1
    candidate = direction.ne(0).astype("int8")

    long_score = (
        trend_up.astype("int8")
        + pullback_ok.astype("int8")
        + momentum_long.astype("int8")
        + volatility_ok.astype("int8")
    )
    short_score = (
        trend_down.astype("int8")
        + pullback_ok.astype("int8")
        + momentum_short.astype("int8")
        + volatility_ok.astype("int8")
    )
    signal_score = pd.concat([long_score, short_score], axis=1).max(axis=1).where(required_valid, 0)

    out[str(cfg["candidate_long_col"])] = candidate_long.fillna(False).astype("int8")
    out[str(cfg["candidate_short_col"])] = candidate_short.fillna(False).astype("int8")
    out[str(cfg["direction_col"])] = direction.astype("int8")
    out[str(cfg["signal_col"])] = direction.astype("int8")
    out[str(cfg["candidate_col"])] = candidate.astype("int8")
    out[str(cfg["signal_name_col"])] = str(cfg["signal_name"])
    out[str(cfg["score_col"])] = signal_score.astype("int8")

    output_cols = [
        str(cfg["candidate_long_col"]),
        str(cfg["candidate_short_col"]),
        str(cfg["direction_col"]),
        str(cfg["signal_col"]),
        str(cfg["candidate_col"]),
        str(cfg["signal_name_col"]),
        str(cfg["score_col"]),
    ]
    meta = {
        "kind": "indicator_model_adaptive_pullback",
        "params": {key: cfg[key] for key in sorted(cfg)},
        "output_cols": output_cols,
        "long_candidates": int(out[str(cfg["candidate_long_col"])].sum()),
        "short_candidates": int(out[str(cfg["candidate_short_col"])].sum()),
        "candidate_rows": int(out[str(cfg["candidate_col"])].sum()),
    }
    return out, meta


def indicator_model_adaptive_pullback_signal(
    df: pd.DataFrame,
    **params: Any,
) -> pd.DataFrame:
    """
    Apply the registered ``indicator_model_adaptive_pullback`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: indicator_model_adaptive_pullback
          params:
            close_col: close
            ema_fast: 20
            ema_mid: 50
            ema_slow: 100
            ema_fast_col: null
            ema_mid_col: null
            ema_slow_col: null
            ema_slope_fast_col: null
            ema_slope_mid_col: null
            adx_col: null
            min_adx: 18.0
            max_adx: 45.0
            rsi_col: null
            rsi_long_min: 45.0
            rsi_long_max: 68.0
            rsi_short_min: 32.0
            rsi_short_max: 55.0
            stoch_k_col: stoch_rsi_k
            stoch_d_col: stoch_rsi_d
            stoch_cross_up_col: stoch_rsi_cross_up
            stoch_cross_down_col: stoch_rsi_cross_down
            stoch_long_max: 60.0
            stoch_short_min: 40.0
            macd_hist_col: macd_hist
            macd_hist_slope_col: macd_hist_slope
            require_macd_confirmation: true
            atr_pct_rank_col: null
            min_atr_pct_rank: 0.2
            max_atr_pct_rank: 0.9
            bb_bandwidth_col: bollinger_bandwidth
            bb_bandwidth_rank_col: bollinger_bandwidth_rank_100
            min_bb_bandwidth: 0.0
            min_bb_bandwidth_rank: 0.2
            distance_ema_fast_atr_col: null
            max_distance_from_ema_atr: 0.75
            candidate_long_col: candidate_long
            candidate_short_col: candidate_short
            direction_col: direction
            signal_col: signal
            candidate_col: signal_candidate
            signal_name_col: signal_name
            score_col: signal_score
            signal_name: indicator_model_adaptive_pullback
          output_cols:
            - signal
            - signal_candidate
    
    Required input columns
    ----------------------
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    ema_fast_col:
        Input dataframe column configured by ``ema_fast_col``. Default: ``null``.
    ema_mid_col:
        Input dataframe column configured by ``ema_mid_col``. Default: ``null``.
    ema_slow_col:
        Input dataframe column configured by ``ema_slow_col``. Default: ``null``.
    ema_slope_fast_col:
        Input dataframe column configured by ``ema_slope_fast_col``. Default: ``null``.
    ema_slope_mid_col:
        Input dataframe column configured by ``ema_slope_mid_col``. Default: ``null``.
    adx_col:
        Input dataframe column configured by ``adx_col``. Default: ``null``.
    rsi_col:
        Input dataframe column configured by ``rsi_col``. Default: ``null``.
    stoch_k_col:
        Input dataframe column configured by ``stoch_k_col``. Default: ``stoch_rsi_k``.
    stoch_d_col:
        Input dataframe column configured by ``stoch_d_col``. Default: ``stoch_rsi_d``.
    stoch_cross_up_col:
        Input dataframe column configured by ``stoch_cross_up_col``. Default: ``stoch_rsi_cross_up``.
    stoch_cross_down_col:
        Input dataframe column configured by ``stoch_cross_down_col``. Default: ``stoch_rsi_cross_down``.
    macd_hist_col:
        Input dataframe column configured by ``macd_hist_col``. Default: ``macd_hist``.
    macd_hist_slope_col:
        Input dataframe column configured by ``macd_hist_slope_col``. Default: ``macd_hist_slope``.
    atr_pct_rank_col:
        Input dataframe column configured by ``atr_pct_rank_col``. Default: ``null``.
    bb_bandwidth_col:
        Input dataframe column configured by ``bb_bandwidth_col``. Default: ``bollinger_bandwidth``.
    bb_bandwidth_rank_col:
        Input dataframe column configured by ``bb_bandwidth_rank_col``. Default: ``bollinger_bandwidth_rank_100``.
    distance_ema_fast_atr_col:
        Input dataframe column configured by ``distance_ema_fast_atr_col``. Default: ``null``.
    candidate_long_col:
        Input dataframe column configured by ``candidate_long_col``. Default: ``candidate_long``.
    candidate_short_col:
        Input dataframe column configured by ``candidate_short_col``. Default: ``candidate_short``.
    direction_col:
        Input dataframe column configured by ``direction_col``. Default: ``direction``.
    signal_name_col:
        Input dataframe column configured by ``signal_name_col``. Default: ``signal_name``.
    score_col:
        Input dataframe column configured by ``score_col``. Default: ``signal_score``.
    
    Parameters
    ----------
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    ema_fast:
        Configuration parameter accepted by this signal. Default: ``20``.
    ema_mid:
        Configuration parameter accepted by this signal. Default: ``50``.
    ema_slow:
        Configuration parameter accepted by this signal. Default: ``100``.
    ema_fast_col:
        Input dataframe column configured by ``ema_fast_col``. Default: ``null``.
    ema_mid_col:
        Input dataframe column configured by ``ema_mid_col``. Default: ``null``.
    ema_slow_col:
        Input dataframe column configured by ``ema_slow_col``. Default: ``null``.
    ema_slope_fast_col:
        Input dataframe column configured by ``ema_slope_fast_col``. Default: ``null``.
    ema_slope_mid_col:
        Input dataframe column configured by ``ema_slope_mid_col``. Default: ``null``.
    adx_col:
        Input dataframe column configured by ``adx_col``. Default: ``null``.
    min_adx:
        Configuration parameter accepted by this signal. Default: ``18.0``.
    max_adx:
        Configuration parameter accepted by this signal. Default: ``45.0``.
    rsi_col:
        Input dataframe column configured by ``rsi_col``. Default: ``null``.
    rsi_long_min:
        Numeric threshold used by this signal. Default: ``45.0``.
    rsi_long_max:
        Numeric threshold used by this signal. Default: ``68.0``.
    rsi_short_min:
        Numeric threshold used by this signal. Default: ``32.0``.
    rsi_short_max:
        Numeric threshold used by this signal. Default: ``55.0``.
    stoch_k_col:
        Input dataframe column configured by ``stoch_k_col``. Default: ``stoch_rsi_k``.
    stoch_d_col:
        Input dataframe column configured by ``stoch_d_col``. Default: ``stoch_rsi_d``.
    stoch_cross_up_col:
        Input dataframe column configured by ``stoch_cross_up_col``. Default: ``stoch_rsi_cross_up``.
    stoch_cross_down_col:
        Input dataframe column configured by ``stoch_cross_down_col``. Default: ``stoch_rsi_cross_down``.
    stoch_long_max:
        Numeric threshold used by this signal. Default: ``60.0``.
    stoch_short_min:
        Numeric threshold used by this signal. Default: ``40.0``.
    macd_hist_col:
        Input dataframe column configured by ``macd_hist_col``. Default: ``macd_hist``.
    macd_hist_slope_col:
        Input dataframe column configured by ``macd_hist_slope_col``. Default: ``macd_hist_slope``.
    require_macd_confirmation:
        Configuration parameter accepted by this signal. Default: ``true``.
    atr_pct_rank_col:
        Input dataframe column configured by ``atr_pct_rank_col``. Default: ``null``.
    min_atr_pct_rank:
        Configuration parameter accepted by this signal. Default: ``0.2``.
    max_atr_pct_rank:
        Configuration parameter accepted by this signal. Default: ``0.9``.
    bb_bandwidth_col:
        Input dataframe column configured by ``bb_bandwidth_col``. Default: ``bollinger_bandwidth``.
    bb_bandwidth_rank_col:
        Input dataframe column configured by ``bb_bandwidth_rank_col``. Default: ``bollinger_bandwidth_rank_100``.
    min_bb_bandwidth:
        Configuration parameter accepted by this signal. Default: ``0.0``.
    min_bb_bandwidth_rank:
        Configuration parameter accepted by this signal. Default: ``0.2``.
    distance_ema_fast_atr_col:
        Input dataframe column configured by ``distance_ema_fast_atr_col``. Default: ``null``.
    max_distance_from_ema_atr:
        Configuration parameter accepted by this signal. Default: ``0.75``.
    candidate_long_col:
        Input dataframe column configured by ``candidate_long_col``. Default: ``candidate_long``.
    candidate_short_col:
        Input dataframe column configured by ``candidate_short_col``. Default: ``candidate_short``.
    direction_col:
        Input dataframe column configured by ``direction_col``. Default: ``direction``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``signal``.
    candidate_col:
        Output dataframe column configured by ``candidate_col``. Default: ``signal_candidate``.
    signal_name_col:
        Input dataframe column configured by ``signal_name_col``. Default: ``signal_name``.
    score_col:
        Input dataframe column configured by ``score_col``. Default: ``signal_score``.
    signal_name:
        Configuration parameter accepted by this signal. Default: ``indicator_model_adaptive_pullback``.
    """
    out, _ = build_indicator_model_adaptive_pullback_signal(df, params)
    return out


__all__ = [
    "build_indicator_model_adaptive_pullback_signal",
    "indicator_model_adaptive_pullback_signal",
]
