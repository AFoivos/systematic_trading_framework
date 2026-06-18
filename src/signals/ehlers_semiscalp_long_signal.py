from __future__ import annotations

from typing import Any, Mapping

import pandas as pd


_ALLOWED_ENTRY_MODES = frozenset({"state", "transition"})

_DEFAULT_CFG: dict[str, Any] = {
    "entry_mode": "transition",
    "price_col": "close",
    "supersmoother_col": "ehlers_supersmoother_10",
    "supersmoother_slope_col": "ehlers_supersmoother_10_slope",
    "roofing_col": "ehlers_roofing_48_10",
    "roofing_slope_col": "ehlers_roofing_48_10_slope",
    "roofing_cross_up_col": "ehlers_roofing_48_10_cross_up",
    "roofing_cross_down_col": "ehlers_roofing_48_10_cross_down",
    "hilbert_amplitude_col": "ehlers_hilbert_amplitude_64",
    "dominant_cycle_period_col": "dominant_cycle_period",
    "atr_col": "atr_over_price_14",
    "min_cycle_period": 10.0,
    "max_cycle_period": 48.0,
    "amplitude_quantile_lookback": 252,
    "amplitude_min_quantile": 0.30,
    "atr_quantile_lookback": 252,
    "atr_min_quantile": 0.30,
    "trend_ok_col": "ehlers_trend_ok",
    "timing_ok_col": "ehlers_timing_ok",
    "cycle_ok_col": "ehlers_cycle_ok",
    "energy_ok_col": "ehlers_energy_ok",
    "volatility_ok_col": "ehlers_volatility_ok",
    "long_setup_col": "ehlers_semiscalp_long_setup",
    "entry_col": "ehlers_semiscalp_long_entry",
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


def _non_empty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value.strip()


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer.")
    return int(value)


def _finite_float(value: Any, *, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite number.") from exc
    if not pd.notna(result) or result in {float("inf"), float("-inf")}:
        raise ValueError(f"{field} must be a finite number.")
    return result


def _validate_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(cfg)
    string_keys = (
        "price_col",
        "supersmoother_col",
        "supersmoother_slope_col",
        "roofing_col",
        "roofing_slope_col",
        "roofing_cross_up_col",
        "roofing_cross_down_col",
        "hilbert_amplitude_col",
        "dominant_cycle_period_col",
        "atr_col",
        "trend_ok_col",
        "timing_ok_col",
        "cycle_ok_col",
        "energy_ok_col",
        "volatility_ok_col",
        "long_setup_col",
        "entry_col",
        "signal_col",
        "candidate_col",
    )
    for key in string_keys:
        normalized[key] = _non_empty_string(normalized.get(key), field=key)

    entry_mode = str(normalized.get("entry_mode", "transition"))
    if entry_mode not in _ALLOWED_ENTRY_MODES:
        raise ValueError(f"entry_mode must be one of: {sorted(_ALLOWED_ENTRY_MODES)}.")
    normalized["entry_mode"] = entry_mode

    normalized["amplitude_quantile_lookback"] = _positive_int(
        normalized.get("amplitude_quantile_lookback"),
        field="amplitude_quantile_lookback",
    )
    normalized["atr_quantile_lookback"] = _positive_int(
        normalized.get("atr_quantile_lookback"),
        field="atr_quantile_lookback",
    )
    for key in (
        "min_cycle_period",
        "max_cycle_period",
        "amplitude_min_quantile",
        "atr_min_quantile",
    ):
        normalized[key] = _finite_float(normalized.get(key), field=key)
    if normalized["min_cycle_period"] > normalized["max_cycle_period"]:
        raise ValueError("min_cycle_period must be <= max_cycle_period.")
    for key in ("amplitude_min_quantile", "atr_min_quantile"):
        if not 0.0 <= normalized[key] <= 1.0:
            raise ValueError(f"{key} must be in [0, 1].")
    return normalized


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for ehlers_semiscalp_long_signal: {missing}")


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def build_ehlers_semiscalp_long_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build the causal long-only Ehlers semi-scalp entry signal."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))
    required_cols = [
        str(cfg["price_col"]),
        str(cfg["supersmoother_col"]),
        str(cfg["supersmoother_slope_col"]),
        str(cfg["roofing_col"]),
        str(cfg["roofing_slope_col"]),
        str(cfg["hilbert_amplitude_col"]),
        str(cfg["dominant_cycle_period_col"]),
        str(cfg["atr_col"]),
    ]
    _require_columns(df, required_cols)

    out = df.copy()
    price = _numeric(out, str(cfg["price_col"]))
    supersmoother = _numeric(out, str(cfg["supersmoother_col"]))
    supersmoother_slope = _numeric(out, str(cfg["supersmoother_slope_col"]))
    roofing = _numeric(out, str(cfg["roofing_col"]))
    roofing_slope = _numeric(out, str(cfg["roofing_slope_col"]))
    amplitude = _numeric(out, str(cfg["hilbert_amplitude_col"]))
    dominant_cycle = _numeric(out, str(cfg["dominant_cycle_period_col"]))
    atr = _numeric(out, str(cfg["atr_col"]))

    amplitude_threshold = amplitude.rolling(
        int(cfg["amplitude_quantile_lookback"]),
        min_periods=int(cfg["amplitude_quantile_lookback"]),
    ).quantile(float(cfg["amplitude_min_quantile"]))
    atr_threshold = atr.rolling(
        int(cfg["atr_quantile_lookback"]),
        min_periods=int(cfg["atr_quantile_lookback"]),
    ).quantile(float(cfg["atr_min_quantile"]))

    trend_ok = price.gt(supersmoother) & supersmoother_slope.gt(0.0)
    timing_ok = roofing.gt(0.0) & roofing_slope.gt(0.0)
    cycle_ok = dominant_cycle.between(
        float(cfg["min_cycle_period"]),
        float(cfg["max_cycle_period"]),
        inclusive="both",
    )
    energy_ok = amplitude.gt(amplitude_threshold)
    volatility_ok = atr.gt(atr_threshold)
    valid = (
        price.notna()
        & supersmoother.notna()
        & supersmoother_slope.notna()
        & roofing.notna()
        & roofing_slope.notna()
        & amplitude.notna()
        & amplitude_threshold.notna()
        & dominant_cycle.notna()
        & atr.notna()
        & atr_threshold.notna()
    )
    long_setup = trend_ok & timing_ok & cycle_ok & energy_ok & volatility_ok & valid
    long_entry = long_setup & ~long_setup.shift(1, fill_value=False)
    selected = long_setup if str(cfg["entry_mode"]) == "state" else long_entry

    condition_outputs = {
        str(cfg["trend_ok_col"]): trend_ok,
        str(cfg["timing_ok_col"]): timing_ok,
        str(cfg["cycle_ok_col"]): cycle_ok,
        str(cfg["energy_ok_col"]): energy_ok,
        str(cfg["volatility_ok_col"]): volatility_ok,
        str(cfg["long_setup_col"]): long_setup,
        str(cfg["entry_col"]): long_entry,
    }
    for column, values in condition_outputs.items():
        out[column] = values.fillna(False).astype("int8")
    out[str(cfg["signal_col"])] = selected.fillna(False).astype("int8")
    out[str(cfg["candidate_col"])] = selected.fillna(False).astype("int8")

    return out, {
        "kind": "ehlers_semiscalp_long",
        "long_only": True,
        "entry_mode": str(cfg["entry_mode"]),
        "trend_ok_rows": int(trend_ok.sum()),
        "timing_ok_rows": int(timing_ok.sum()),
        "cycle_ok_rows": int(cycle_ok.sum()),
        "energy_ok_rows": int(energy_ok.sum()),
        "volatility_ok_rows": int(volatility_ok.sum()),
        "long_setup_rows": int(long_setup.sum()),
        "long_entry_rows": int(long_entry.sum()),
        "entry_col": str(cfg["entry_col"]),
        "signal_col": str(cfg["signal_col"]),
        "candidate_col": str(cfg["candidate_col"]),
    }


def ehlers_semiscalp_long_signal(df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    """
    Apply the registered ``ehlers_semiscalp_long`` signal transformation.

    YAML declaration::

        signals:
          kind: ehlers_semiscalp_long
          params: {}
    """
    out, _ = build_ehlers_semiscalp_long_signal(df, params)
    return out


__all__ = ["build_ehlers_semiscalp_long_signal", "ehlers_semiscalp_long_signal"]
