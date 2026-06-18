from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import pandas as pd


_ALLOWED_MODES = frozenset({"long_only", "short_only", "long_short"})

_DEFAULT_CFG: dict[str, Any] = {
    "mode": "long_short",
    "trend_regime_col": "trend_regime",
    "ppo_col": "ppo",
    "ppo_signal_col": "ppo_signal",
    "ppo_hist_col": "ppo_hist",
    "adx_col": "adx_14",
    "roc_col": "roc_12",
    "zscore_momentum_col": "zscore_momentum_20",
    "volatility_regime_col": "volatility_regime",
    "adx_min": 18.0,
    "zscore_long_min": 0.0,
    "zscore_short_max": 0.0,
    "roc_long_min": 0.0,
    "roc_short_max": 0.0,
    "use_ppo_signal_cross": True,
    "allowed_volatility_regimes": [0, 1],
    "long_candidate_col": "c2_long_candidate",
    "short_candidate_col": "c2_short_candidate",
    "signal_col": "c2_signal",
    "candidate_col": "c2_signal_candidate",
    "bullish_trend_col": "c2_bullish_trend",
    "bearish_trend_col": "c2_bearish_trend",
    "adx_pass_col": "c2_adx_pass",
    "ppo_long_pass_col": "c2_ppo_long_pass",
    "ppo_short_pass_col": "c2_ppo_short_pass",
    "roc_long_pass_col": "c2_roc_long_pass",
    "roc_short_pass_col": "c2_roc_short_pass",
    "zscore_long_pass_col": "c2_zscore_long_pass",
    "zscore_short_pass_col": "c2_zscore_short_pass",
    "volatility_pass_col": "c2_volatility_regime_pass",
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


def _allowed_regime_values(value: Any) -> set[float]:
    if isinstance(value, bool) or isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("allowed_volatility_regimes must be a non-empty sequence of finite numbers.")
    regimes: set[float] = set()
    for idx, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"allowed_volatility_regimes[{idx}] must be a finite number.")
        regime = float(item)
        if not math.isfinite(regime):
            raise ValueError(f"allowed_volatility_regimes[{idx}] must be a finite number.")
        regimes.add(regime)
    if not regimes:
        raise ValueError("allowed_volatility_regimes must not be empty.")
    return regimes


def _validate_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(cfg)
    mode = str(normalized.get("mode", "long_short"))
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of: {sorted(_ALLOWED_MODES)}.")
    normalized["mode"] = mode

    string_keys = (
        "trend_regime_col",
        "ppo_col",
        "ppo_signal_col",
        "ppo_hist_col",
        "adx_col",
        "roc_col",
        "zscore_momentum_col",
        "volatility_regime_col",
        "long_candidate_col",
        "short_candidate_col",
        "signal_col",
        "candidate_col",
        "bullish_trend_col",
        "bearish_trend_col",
        "adx_pass_col",
        "ppo_long_pass_col",
        "ppo_short_pass_col",
        "roc_long_pass_col",
        "roc_short_pass_col",
        "zscore_long_pass_col",
        "zscore_short_pass_col",
        "volatility_pass_col",
    )
    for key in string_keys:
        normalized[key] = _string_value(normalized.get(key), field=key)

    if not isinstance(normalized.get("use_ppo_signal_cross"), bool):
        raise TypeError("use_ppo_signal_cross must be boolean.")

    for key in (
        "adx_min",
        "zscore_long_min",
        "zscore_short_max",
        "roc_long_min",
        "roc_short_max",
    ):
        normalized[key] = _finite_float(normalized.get(key), field=key)

    if normalized["adx_min"] < 0.0:
        raise ValueError("adx_min must be >= 0.")
    normalized["allowed_volatility_regimes"] = _allowed_regime_values(
        normalized.get("allowed_volatility_regimes")
    )
    return normalized


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for c2_regime_aware_momentum_signal: {missing}")


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def _side_series(long_setup: pd.Series, short_setup: pd.Series) -> pd.Series:
    side = pd.Series(0, index=long_setup.index, dtype="int8")
    side.loc[long_setup & ~short_setup] = 1
    side.loc[short_setup & ~long_setup] = -1
    return side


def build_c2_regime_aware_momentum_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Build the Combination 2 regime-aware momentum continuation signal.

    All signal inputs are current-bar or trailing feature columns. The backtest and target
    layers remain responsible for next-bar execution and event-label timing.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))
    required_cols = [
        str(cfg["trend_regime_col"]),
        str(cfg["ppo_hist_col"]),
        str(cfg["adx_col"]),
        str(cfg["roc_col"]),
        str(cfg["zscore_momentum_col"]),
        str(cfg["volatility_regime_col"]),
    ]
    if bool(cfg["use_ppo_signal_cross"]):
        required_cols.extend([str(cfg["ppo_col"]), str(cfg["ppo_signal_col"])])
    _require_columns(df, required_cols)

    out = df.copy()
    trend_regime = _numeric(out, str(cfg["trend_regime_col"]))
    ppo_hist = _numeric(out, str(cfg["ppo_hist_col"]))
    adx = _numeric(out, str(cfg["adx_col"]))
    roc = _numeric(out, str(cfg["roc_col"]))
    zscore = _numeric(out, str(cfg["zscore_momentum_col"]))
    volatility_regime = _numeric(out, str(cfg["volatility_regime_col"]))

    bullish_trend = trend_regime.gt(0.0)
    bearish_trend = trend_regime.lt(0.0)
    adx_pass = adx.gt(float(cfg["adx_min"]))
    roc_long_pass = roc.gt(float(cfg["roc_long_min"]))
    roc_short_pass = roc.lt(float(cfg["roc_short_max"]))
    zscore_long_pass = zscore.gt(float(cfg["zscore_long_min"]))
    zscore_short_pass = zscore.lt(float(cfg["zscore_short_max"]))
    volatility_pass = volatility_regime.isin(set(cfg["allowed_volatility_regimes"]))

    ppo_long_pass = ppo_hist.gt(0.0)
    ppo_short_pass = ppo_hist.lt(0.0)
    if bool(cfg["use_ppo_signal_cross"]):
        ppo = _numeric(out, str(cfg["ppo_col"]))
        ppo_signal = _numeric(out, str(cfg["ppo_signal_col"]))
        ppo_long_pass &= ppo.gt(ppo_signal)
        ppo_short_pass &= ppo.lt(ppo_signal)

    common_valid = (
        trend_regime.notna()
        & ppo_hist.notna()
        & adx.notna()
        & roc.notna()
        & zscore.notna()
        & volatility_regime.notna()
    )

    long_candidate = (
        common_valid
        & bullish_trend
        & ppo_long_pass
        & zscore_long_pass
        & roc_long_pass
        & adx_pass
        & volatility_pass
    )
    short_candidate = (
        common_valid
        & bearish_trend
        & ppo_short_pass
        & zscore_short_pass
        & roc_short_pass
        & adx_pass
        & volatility_pass
    )

    if str(cfg["mode"]) == "long_only":
        short_candidate = pd.Series(False, index=out.index)
    elif str(cfg["mode"]) == "short_only":
        long_candidate = pd.Series(False, index=out.index)

    side = _side_series(long_candidate.fillna(False), short_candidate.fillna(False))

    out[str(cfg["bullish_trend_col"])] = bullish_trend.fillna(False).astype("int8")
    out[str(cfg["bearish_trend_col"])] = bearish_trend.fillna(False).astype("int8")
    out[str(cfg["adx_pass_col"])] = adx_pass.fillna(False).astype("int8")
    out[str(cfg["ppo_long_pass_col"])] = ppo_long_pass.fillna(False).astype("int8")
    out[str(cfg["ppo_short_pass_col"])] = ppo_short_pass.fillna(False).astype("int8")
    out[str(cfg["roc_long_pass_col"])] = roc_long_pass.fillna(False).astype("int8")
    out[str(cfg["roc_short_pass_col"])] = roc_short_pass.fillna(False).astype("int8")
    out[str(cfg["zscore_long_pass_col"])] = zscore_long_pass.fillna(False).astype("int8")
    out[str(cfg["zscore_short_pass_col"])] = zscore_short_pass.fillna(False).astype("int8")
    out[str(cfg["volatility_pass_col"])] = volatility_pass.fillna(False).astype("int8")
    out[str(cfg["long_candidate_col"])] = long_candidate.fillna(False).astype("int8")
    out[str(cfg["short_candidate_col"])] = short_candidate.fillna(False).astype("int8")
    out[str(cfg["signal_col"])] = side
    out[str(cfg["candidate_col"])] = side.ne(0).astype("int8")

    return out, {
        "kind": "c2_regime_aware_momentum",
        "mode": str(cfg["mode"]),
        "adx_min": float(cfg["adx_min"]),
        "zscore_long_min": float(cfg["zscore_long_min"]),
        "zscore_short_max": float(cfg["zscore_short_max"]),
        "roc_long_min": float(cfg["roc_long_min"]),
        "roc_short_max": float(cfg["roc_short_max"]),
        "use_ppo_signal_cross": bool(cfg["use_ppo_signal_cross"]),
        "allowed_volatility_regimes": sorted(float(v) for v in cfg["allowed_volatility_regimes"]),
        "long_candidates": int(out[str(cfg["long_candidate_col"])].sum()),
        "short_candidates": int(out[str(cfg["short_candidate_col"])].sum()),
        "signal_col": str(cfg["signal_col"]),
        "candidate_col": str(cfg["candidate_col"]),
    }


def c2_regime_aware_momentum_signal(df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    """
    Apply the registered ``c2_regime_aware_momentum`` signal transformation.

    YAML declaration::

        signals:
          kind: c2_regime_aware_momentum
          params: {}
    """
    out, _ = build_c2_regime_aware_momentum_signal(df, params)
    return out


__all__ = ["build_c2_regime_aware_momentum_signal", "c2_regime_aware_momentum_signal"]
