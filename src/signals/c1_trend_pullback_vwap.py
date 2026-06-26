from __future__ import annotations

import math
from typing import Any, Mapping

import pandas as pd


_ALLOWED_MODES = frozenset({"long_only", "short_only", "long_short"})

_DEFAULT_CFG: dict[str, Any] = {
    "mode": "long_short",
    "trend_regime_col": "trend_regime",
    "long_trigger_col": "vwap_rms_ema_cross_long_setup",
    "short_trigger_col": "vwap_rms_ema_cross_short_setup",
    "ppo_hist_col": "ppo_hist",
    "ppo_above_signal_col": "ppo_above_signal",
    "ppo_below_signal_col": "ppo_below_signal",
    "mfi_col": "mfi_14",
    "stoch_k_col": "stoch_rsi_k",
    "stoch_d_col": "stoch_rsi_d",
    "zscore_momentum_col": "zscore_momentum_20",
    "volatility_regime_col": "volatility_regime",
    "trend_quality_col": "rolling_r2_trend_quality_96",
    "mfi_long_min": 40.0,
    "mfi_long_max": 80.0,
    "mfi_short_min": 20.0,
    "mfi_short_max": 60.0,
    "long_zscore_min": 0.0,
    "short_zscore_max": 0.0,
    "max_volatility_regime": 1.0,
    "strict_trend_quality_min": 0.35,
    "strict_mfi_long_min": 50.0,
    "strict_mfi_short_max": 50.0,
    "strict_long_zscore_min": 0.5,
    "strict_short_zscore_max": -0.5,
    "use_strict_signal": False,
    "long_candidate_col": "c1_long_candidate",
    "short_candidate_col": "c1_short_candidate",
    "long_candidate_strict_col": "c1_long_candidate_strict",
    "short_candidate_strict_col": "c1_short_candidate_strict",
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


def _finite_float(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number.")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{field} must be a finite number.")
    return out


def _string_value(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value.strip()


def _validate_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(cfg)
    mode = str(normalized.get("mode", "long_short"))
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of: {sorted(_ALLOWED_MODES)}.")
    normalized["mode"] = mode

    string_keys = (
        "trend_regime_col",
        "long_trigger_col",
        "short_trigger_col",
        "ppo_hist_col",
        "ppo_above_signal_col",
        "ppo_below_signal_col",
        "mfi_col",
        "stoch_k_col",
        "stoch_d_col",
        "zscore_momentum_col",
        "volatility_regime_col",
        "trend_quality_col",
        "long_candidate_col",
        "short_candidate_col",
        "long_candidate_strict_col",
        "short_candidate_strict_col",
        "signal_col",
        "candidate_col",
    )
    for key in string_keys:
        normalized[key] = _string_value(normalized.get(key), field=key)

    if not isinstance(normalized.get("use_strict_signal"), bool):
        raise TypeError("use_strict_signal must be boolean.")

    numeric_keys = (
        "mfi_long_min",
        "mfi_long_max",
        "mfi_short_min",
        "mfi_short_max",
        "long_zscore_min",
        "short_zscore_max",
        "max_volatility_regime",
        "strict_trend_quality_min",
        "strict_mfi_long_min",
        "strict_mfi_short_max",
        "strict_long_zscore_min",
        "strict_short_zscore_max",
    )
    for key in numeric_keys:
        normalized[key] = _finite_float(normalized.get(key), field=key)

    if normalized["mfi_long_min"] > normalized["mfi_long_max"]:
        raise ValueError("mfi_long_min must be <= mfi_long_max.")
    if normalized["mfi_short_min"] > normalized["mfi_short_max"]:
        raise ValueError("mfi_short_min must be <= mfi_short_max.")
    if not 0.0 <= normalized["strict_trend_quality_min"] <= 1.0:
        raise ValueError("strict_trend_quality_min must be in [0, 1].")
    return normalized


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def _flag(frame: pd.DataFrame, column: str) -> pd.Series:
    return _numeric(frame, column).fillna(0.0).ne(0.0)


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for c1_trend_pullback_vwap_signal: {missing}")


def _side_series(long_setup: pd.Series, short_setup: pd.Series) -> pd.Series:
    side = pd.Series(0, index=long_setup.index, dtype="int8")
    side.loc[long_setup & ~short_setup] = 1
    side.loc[short_setup & ~long_setup] = -1
    return side


def build_c1_trend_pullback_vwap_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Build the Combination 1 trend-pullback VWAP candidate signal.

    All inputs are current-bar or trailing feature columns. Execution timing remains the
    responsibility of the target/backtest layers.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))
    required_cols = [
        str(cfg["trend_regime_col"]),
        str(cfg["long_trigger_col"]),
        str(cfg["short_trigger_col"]),
        str(cfg["ppo_hist_col"]),
        str(cfg["ppo_above_signal_col"]),
        str(cfg["ppo_below_signal_col"]),
        str(cfg["mfi_col"]),
        str(cfg["stoch_k_col"]),
        str(cfg["stoch_d_col"]),
        str(cfg["zscore_momentum_col"]),
        str(cfg["volatility_regime_col"]),
        str(cfg["trend_quality_col"]),
    ]
    _require_columns(df, required_cols)

    out = df.copy()
    trend_regime = _numeric(out, str(cfg["trend_regime_col"]))
    ppo_hist = _numeric(out, str(cfg["ppo_hist_col"]))
    mfi = _numeric(out, str(cfg["mfi_col"]))
    stoch_k = _numeric(out, str(cfg["stoch_k_col"]))
    stoch_d = _numeric(out, str(cfg["stoch_d_col"]))
    zscore_momentum = _numeric(out, str(cfg["zscore_momentum_col"]))
    volatility_regime = _numeric(out, str(cfg["volatility_regime_col"]))
    trend_quality = _numeric(out, str(cfg["trend_quality_col"]))

    bullish_trend = trend_regime.gt(0.0)
    bearish_trend = trend_regime.lt(0.0)
    long_trigger = _flag(out, str(cfg["long_trigger_col"]))
    short_trigger = _flag(out, str(cfg["short_trigger_col"]))
    ppo_above_signal = _flag(out, str(cfg["ppo_above_signal_col"]))
    ppo_below_signal = _flag(out, str(cfg["ppo_below_signal_col"]))
    volatility_ok = volatility_regime.notna() & volatility_regime.le(float(cfg["max_volatility_regime"]))

    common_valid = (
        trend_regime.notna()
        & ppo_hist.notna()
        & mfi.notna()
        & stoch_k.notna()
        & stoch_d.notna()
        & zscore_momentum.notna()
        & volatility_ok
    )

    long_candidate = (
        common_valid
        & bullish_trend
        & long_trigger
        & ppo_hist.gt(0.0)
        & ppo_above_signal
        & mfi.between(float(cfg["mfi_long_min"]), float(cfg["mfi_long_max"]), inclusive="both")
        & stoch_k.gt(stoch_d)
        & zscore_momentum.gt(float(cfg["long_zscore_min"]))
    )
    short_candidate = (
        common_valid
        & bearish_trend
        & short_trigger
        & ppo_hist.lt(0.0)
        & ppo_below_signal
        & mfi.between(float(cfg["mfi_short_min"]), float(cfg["mfi_short_max"]), inclusive="both")
        & stoch_k.lt(stoch_d)
        & zscore_momentum.lt(float(cfg["short_zscore_max"]))
    )

    strict_valid = common_valid & trend_quality.notna()
    long_candidate_strict = (
        strict_valid
        & bullish_trend
        & trend_quality.gt(float(cfg["strict_trend_quality_min"]))
        & long_trigger
        & ppo_hist.gt(0.0)
        & ppo_above_signal
        & mfi.gt(float(cfg["strict_mfi_long_min"]))
        & stoch_k.gt(stoch_d)
        & zscore_momentum.gt(float(cfg["strict_long_zscore_min"]))
    )
    short_candidate_strict = (
        strict_valid
        & bearish_trend
        & trend_quality.gt(float(cfg["strict_trend_quality_min"]))
        & short_trigger
        & ppo_hist.lt(0.0)
        & ppo_below_signal
        & mfi.lt(float(cfg["strict_mfi_short_max"]))
        & stoch_k.lt(stoch_d)
        & zscore_momentum.lt(float(cfg["strict_short_zscore_max"]))
    )

    if str(cfg["mode"]) == "long_only":
        short_candidate = pd.Series(False, index=out.index)
        short_candidate_strict = pd.Series(False, index=out.index)
    elif str(cfg["mode"]) == "short_only":
        long_candidate = pd.Series(False, index=out.index)
        long_candidate_strict = pd.Series(False, index=out.index)

    signal_long = long_candidate_strict if bool(cfg["use_strict_signal"]) else long_candidate
    signal_short = short_candidate_strict if bool(cfg["use_strict_signal"]) else short_candidate
    side = _side_series(signal_long.fillna(False), signal_short.fillna(False))

    out[str(cfg["long_candidate_col"])] = long_candidate.fillna(False).astype("int8")
    out[str(cfg["short_candidate_col"])] = short_candidate.fillna(False).astype("int8")
    out[str(cfg["long_candidate_strict_col"])] = long_candidate_strict.fillna(False).astype("int8")
    out[str(cfg["short_candidate_strict_col"])] = short_candidate_strict.fillna(False).astype("int8")
    out[str(cfg["signal_col"])] = side
    out[str(cfg["candidate_col"])] = side.ne(0).astype("int8")

    return out, {
        "kind": "c1_trend_pullback_vwap",
        "mode": str(cfg["mode"]),
        "use_strict_signal": bool(cfg["use_strict_signal"]),
        "long_candidates": int(out[str(cfg["long_candidate_col"])].sum()),
        "short_candidates": int(out[str(cfg["short_candidate_col"])].sum()),
        "strict_long_candidates": int(out[str(cfg["long_candidate_strict_col"])].sum()),
        "strict_short_candidates": int(out[str(cfg["short_candidate_strict_col"])].sum()),
        "signal_col": str(cfg["signal_col"]),
        "candidate_col": str(cfg["candidate_col"]),
    }


def c1_trend_pullback_vwap_signal(df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    """
    Apply the registered ``c1_trend_pullback_vwap`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: c1_trend_pullback_vwap
          params:
            mode: long_short
            trend_regime_col: trend_regime
            long_trigger_col: vwap_rms_ema_cross_long_setup
            short_trigger_col: vwap_rms_ema_cross_short_setup
            ppo_hist_col: ppo_hist
            ppo_above_signal_col: ppo_above_signal
            ppo_below_signal_col: ppo_below_signal
            mfi_col: mfi_14
            stoch_k_col: stoch_rsi_k
            stoch_d_col: stoch_rsi_d
            zscore_momentum_col: zscore_momentum_20
            volatility_regime_col: volatility_regime
            trend_quality_col: rolling_r2_trend_quality_96
            mfi_long_min: 40.0
            mfi_long_max: 80.0
            mfi_short_min: 20.0
            mfi_short_max: 60.0
            long_zscore_min: 0.0
            short_zscore_max: 0.0
            max_volatility_regime: 1.0
            strict_trend_quality_min: 0.35
            strict_mfi_long_min: 50.0
            strict_mfi_short_max: 50.0
            strict_long_zscore_min: 0.5
            strict_short_zscore_max: -0.5
            use_strict_signal: false
            long_candidate_col: c1_long_candidate
            short_candidate_col: c1_short_candidate
            long_candidate_strict_col: c1_long_candidate_strict
            short_candidate_strict_col: c1_short_candidate_strict
            signal_col: signal_side
            candidate_col: signal_candidate
          output_cols:
            - c1_long_candidate
            - c1_short_candidate
            - signal_side
            - signal_candidate
    
    Required input columns
    ----------------------
    trend_regime_col:
        Input dataframe column configured by ``trend_regime_col``. Default: ``trend_regime``.
    long_trigger_col:
        Input dataframe column configured by ``long_trigger_col``. Default: ``vwap_rms_ema_cross_long_setup``.
    short_trigger_col:
        Input dataframe column configured by ``short_trigger_col``. Default: ``vwap_rms_ema_cross_short_setup``.
    ppo_hist_col:
        Input dataframe column configured by ``ppo_hist_col``. Default: ``ppo_hist``.
    mfi_col:
        Input dataframe column configured by ``mfi_col``. Default: ``mfi_14``.
    stoch_k_col:
        Input dataframe column configured by ``stoch_k_col``. Default: ``stoch_rsi_k``.
    stoch_d_col:
        Input dataframe column configured by ``stoch_d_col``. Default: ``stoch_rsi_d``.
    zscore_momentum_col:
        Input dataframe column configured by ``zscore_momentum_col``. Default: ``zscore_momentum_20``.
    volatility_regime_col:
        Input dataframe column configured by ``volatility_regime_col``. Default: ``volatility_regime``.
    long_candidate_strict_col:
        Input dataframe column configured by ``long_candidate_strict_col``. Default: ``c1_long_candidate_strict``.
    short_candidate_strict_col:
        Input dataframe column configured by ``short_candidate_strict_col``. Default: ``c1_short_candidate_strict``.
    
    Parameters
    ----------
    mode:
        Mode selector controlling how this signal is applied. Default: ``long_short``.
    trend_regime_col:
        Input dataframe column configured by ``trend_regime_col``. Default: ``trend_regime``.
    long_trigger_col:
        Input dataframe column configured by ``long_trigger_col``. Default: ``vwap_rms_ema_cross_long_setup``.
    short_trigger_col:
        Input dataframe column configured by ``short_trigger_col``. Default: ``vwap_rms_ema_cross_short_setup``.
    ppo_hist_col:
        Input dataframe column configured by ``ppo_hist_col``. Default: ``ppo_hist``.
    ppo_above_signal_col:
        Input dataframe column configured by ``ppo_above_signal_col``. Default: ``ppo_above_signal``.
    ppo_below_signal_col:
        Input dataframe column configured by ``ppo_below_signal_col``. Default: ``ppo_below_signal``.
    mfi_col:
        Input dataframe column configured by ``mfi_col``. Default: ``mfi_14``.
    stoch_k_col:
        Input dataframe column configured by ``stoch_k_col``. Default: ``stoch_rsi_k``.
    stoch_d_col:
        Input dataframe column configured by ``stoch_d_col``. Default: ``stoch_rsi_d``.
    zscore_momentum_col:
        Input dataframe column configured by ``zscore_momentum_col``. Default: ``zscore_momentum_20``.
    volatility_regime_col:
        Input dataframe column configured by ``volatility_regime_col``. Default: ``volatility_regime``.
    trend_quality_col:
        Input dataframe column configured by ``trend_quality_col``. Default: ``rolling_r2_trend_quality_96``.
    mfi_long_min:
        Numeric threshold used by this signal. Default: ``40.0``.
    mfi_long_max:
        Numeric threshold used by this signal. Default: ``80.0``.
    mfi_short_min:
        Numeric threshold used by this signal. Default: ``20.0``.
    mfi_short_max:
        Numeric threshold used by this signal. Default: ``60.0``.
    long_zscore_min:
        Numeric threshold used by this signal. Default: ``0.0``.
    short_zscore_max:
        Numeric threshold used by this signal. Default: ``0.0``.
    max_volatility_regime:
        Configuration parameter accepted by this signal. Default: ``1.0``.
    strict_trend_quality_min:
        Numeric threshold used by this signal. Default: ``0.35``.
    strict_mfi_long_min:
        Numeric threshold used by this signal. Default: ``50.0``.
    strict_mfi_short_max:
        Numeric threshold used by this signal. Default: ``50.0``.
    strict_long_zscore_min:
        Numeric threshold used by this signal. Default: ``0.5``.
    strict_short_zscore_max:
        Numeric threshold used by this signal. Default: ``-0.5``.
    use_strict_signal:
        Boolean switch controlling optional signal behavior. Default: ``false``.
    long_candidate_col:
        Output dataframe column configured by ``long_candidate_col``. Default: ``c1_long_candidate``.
    short_candidate_col:
        Output dataframe column configured by ``short_candidate_col``. Default: ``c1_short_candidate``.
    long_candidate_strict_col:
        Input dataframe column configured by ``long_candidate_strict_col``. Default: ``c1_long_candidate_strict``.
    short_candidate_strict_col:
        Input dataframe column configured by ``short_candidate_strict_col``. Default: ``c1_short_candidate_strict``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``signal_side``.
    candidate_col:
        Output dataframe column configured by ``candidate_col``. Default: ``signal_candidate``.
    """
    out, _ = build_c1_trend_pullback_vwap_signal(df, params)
    return out


__all__ = ["build_c1_trend_pullback_vwap_signal", "c1_trend_pullback_vwap_signal"]
