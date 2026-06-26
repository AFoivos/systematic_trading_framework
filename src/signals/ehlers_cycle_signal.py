from __future__ import annotations

from typing import Any, Mapping
import pandas as pd
import math

_ALLOWED_MODES = frozenset({"long_only", "short_only", "long_short", "long_short_hold"})
_ALLOWED_ENTRY_MODES = frozenset({"state", "transition"})


_DEFAULT_CFG : dict[str, Any] = {
    "entry_delay_bars": 0,
    "mode" : "long_only",
    "entry_mode": "state",
    "acp_col": "autocorrelation_periodogram_10_48",
    "acp_power_col": "autocorrelation_periodogram_10_48_power",
    "acp_sdv_col": "autocorrelation_periodogram_10_48__standard_deviation",
    "roofing_filter_col": "roofing_filter_48_10",
    "roofing_filter_slope_col": "roofing_filter_48_10_slope",
    "decycler_osc_col": "decycler_oscillator_30_60",
    "rolling_r2_col": "rolling_r2_96",
    "rolling_r2_slope_col": "rolling_r2_slope_96",
    "signal_col": "cycle_signal",
    "rolling_r2_threshold": 0.0,
    "rolling_r2_slope_threshold":  0.0,
    "acp_threshold":  30.0,
    "acp_power_threshold":  50.0,
    "acp_sdv_threshold":  5.0,
    "acp_ratio_threshold": 0.15,
    "roofing_filter_threshold": 0.0,
    "decycler_osc_threshold":  0.0
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

def _float_value(value: Any, *, field: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field} must be numeric.")
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be numeric.") from None

def _bool_value(value: Any, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{field} must be boolean.")
    return bool(value)

def _non_negative_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or int(value) < 0:
        raise ValueError(f"{field} must be a non-negative integer.")
    return int(value)

def _validate_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(cfg)

    entry_mode = str(normalized.get("entry_mode", "state"))
    mode = str(normalized.get("mode", "long_only"))

    if entry_mode not in _ALLOWED_ENTRY_MODES:
        raise ValueError(f"entry_mode must be one of: {sorted(_ALLOWED_ENTRY_MODES)}.")

    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of: {sorted(_ALLOWED_MODES)}.")

    normalized["entry_mode"] = entry_mode
    normalized["mode"] = mode

    normalized["entry_delay_bars"] = _non_negative_int(
        normalized.get("entry_delay_bars"),
        field="entry_delay_bars",
    )

    string_keys = (
        "acp_col",
        "acp_power_col",
        "acp_sdv_col",
        "roofing_filter_col",
        "roofing_filter_slope_col",
        "decycler_osc_col",
        "rolling_r2_col",
        "rolling_r2_slope_col",
        "signal_col",
    )

    for key in string_keys:
        normalized[key] = _string_value(normalized.get(key), field=key)

    float_keys = (
        "rolling_r2_threshold",
        "rolling_r2_slope_threshold",
        "acp_threshold",
        "acp_power_threshold",
        "acp_sdv_threshold",
        "acp_ratio_threshold",
        "roofing_filter_threshold",
        "decycler_osc_threshold",
    )

    for key in float_keys:
        normalized[key] = _float_value(normalized.get(key), field=key)

    return normalized


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for ehlers_continuation_long_signal: {missing}")


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def _optional_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(math.nan, index=frame.index, dtype=float)
    return _numeric(frame, column)



def build_ehlers_cycle_long_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Apply the registered ``ehlers_cycle_long`` signal transformation.

    This signal creates a long continuation signal from Ehlers/cycle-regime
    features. It requires a strong dominant cycle estimate, strong ACP power,
    low ACP dispersion/noise, positive roofing-filter direction, positive
    decycler oscillator, and acceptable rolling R2 trend quality.

    YAML declaration::

        signals:
          kind: ehlers_cycle_long
          params:
            entry_delay_bars: 0
            mode: long_only
            entry_mode: state
            acp_col: autocorrelation_periodogram_10_48
            acp_power_col: autocorrelation_periodogram_10_48_power
            acp_sdv_col: autocorrelation_periodogram_10_48__standard_deviation
            roofing_filter_col: roofing_filter_48_10
            roofing_filter_slope_col: roofing_filter_48_10_slope
            decycler_osc_col: decycler_oscillator_30_60
            rolling_r2_col: rolling_r2_96
            rolling_r2_slope_col: rolling_r2_slope_96
            signal_col: cycle_signal
            rolling_r2_threshold: 0.0
            rolling_r2_slope_threshold: 0.0
            acp_threshold: 30.0
            acp_power_threshold: 50.0
            acp_sdv_threshold: 5.0
            acp_ratio_threshold: 0.15
            roofing_filter_threshold: 0.0
            decycler_osc_threshold: 0.0
          output_cols:
            - cycle_signal

    Required input columns
    ----------------------
    acp_col:
        Dominant cycle period column, usually produced by
        ``autocorrelation_periodogram``.
    acp_power_col:
        Autocorrelation periodogram power column.
    acp_sdv_col:
        Rolling standard deviation or dispersion column of the ACP value.
    roofing_filter_col:
        Roofing filter value column.
    roofing_filter_slope_col:
        Roofing filter slope column.
    decycler_osc_col:
        Decycler oscillator column.
    rolling_r2_col:
        Rolling R2 trend-quality column.
    rolling_r2_slope_col:
        Rolling R2 slope column.

    Parameters
    ----------
    entry_delay_bars:
        Number of bars to delay the produced signal after the condition is met.
    mode:
        Signal mode metadata. Currently validated against:
        ``long_only``, ``short_only``, ``long_short``, ``long_short_hold``.
    entry_mode:
        If ``state``, the signal remains active while all conditions are true.
        If ``transition``, the signal is active only on the first bar where the
        long state turns true.
    acp_col:
        Input column for the dominant cycle period.
    acp_power_col:
        Input column for ACP power.
    acp_sdv_col:
        Input column for ACP dispersion/noise.
    roofing_filter_col:
        Input column for the roofing filter value.
    roofing_filter_slope_col:
        Input column for the roofing filter slope.
    decycler_osc_col:
        Input column for the decycler oscillator.
    rolling_r2_col:
        Input column for rolling R2 trend quality.
    rolling_r2_slope_col:
        Input column for rolling R2 slope.
    signal_col:
        Output column for the generated signal.
    rolling_r2_threshold:
        Minimum rolling R2 value required.
    rolling_r2_slope_threshold:
        Minimum rolling R2 slope value required.
    acp_threshold:
        Minimum dominant cycle period required.
    acp_power_threshold:
        Minimum ACP power required.
    acp_sdv_threshold:
        Maximum ACP standard deviation allowed.
    acp_ratio_threshold:
        Maximum allowed ratio ``acp_sdv / acp``.
    roofing_filter_threshold:
        Minimum roofing filter value required.
    decycler_osc_threshold:
        Minimum decycler oscillator value required.
    """
    
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")
    
    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))
    required_cols = [
        str(cfg["acp_col"]),
        str(cfg["acp_power_col"]),
        str(cfg["acp_sdv_col"]),
        str(cfg["roofing_filter_col"]),
        str(cfg["roofing_filter_slope_col"]),
        str(cfg["decycler_osc_col"]),
        str(cfg["rolling_r2_col"]),
        str(cfg["rolling_r2_slope_col"])
    ]
    _require_columns(df, list(dict.fromkeys(required_cols)))

    out = df.copy()
    
    acp = _optional_numeric(out, str(cfg["acp_col"]))
    acp_power = _optional_numeric(out, str(cfg["acp_power_col"]))
    acp_sdv = _optional_numeric(out, str(cfg["acp_sdv_col"]))
    acp_ratio = (acp_sdv / acp).where(
        acp_sdv.notna() & acp.notna() & acp.ne(0)
    )
    rf = _optional_numeric(out, str(cfg["roofing_filter_col"]))
    rf_slope = _optional_numeric(out, str(cfg["roofing_filter_slope_col"]))
    do = _optional_numeric(out, str(cfg["decycler_osc_col"]))
    rr2 = _optional_numeric(out, str(cfg["rolling_r2_col"]))
    rr2_slope = _optional_numeric(out, str(cfg["rolling_r2_slope_col"]))
    
    acp_threshold = float(cfg["acp_threshold"])
    acp_power_threshold = float(cfg["acp_power_threshold"])
    acp_sdv_threshold = float(cfg["acp_sdv_threshold"])
    acp_ratio_threshold = float(cfg["acp_ratio_threshold"])
    roofing_filter_threshold = float(cfg["roofing_filter_threshold"])
    rr2_threshold = float(cfg["rolling_r2_threshold"])
    rr2_slope_threshold = float(cfg["rolling_r2_slope_threshold"])
    
    decycler_osc_threshold = float(cfg["decycler_osc_threshold"])

    
    acp_condition = acp.ge(acp_threshold)
    acp_power_condition = acp_power.ge(acp_power_threshold)
    acp_sdv_condition = acp_sdv.le(acp_sdv_threshold)
    acp_ratio_condition = acp_ratio.le(acp_ratio_threshold)
    rf_condition = rf.ge(roofing_filter_threshold)
    rf_slope_condition = rf_slope.gt(0.0)
    do_condition = do.ge(decycler_osc_threshold)
    rr2_condition = rr2.ge(rr2_threshold)
    rr2_slope_condition = rr2_slope.ge(rr2_slope_threshold)
    
    valid = (
        acp.notna()
        & acp_power.notna()
        & acp_sdv.notna()
        & acp_ratio.notna()
        & rf.notna()
        & rf_slope.notna()
        & do.notna()
        & rr2.notna()
        & rr2_slope.notna()
    )
    
    long_state = (
        acp_condition
        & acp_power_condition
        & acp_sdv_condition
        & acp_ratio_condition
        & rf_condition
        & do_condition
        & rf_slope_condition
        & rr2_condition
        & rr2_slope_condition
        & valid
    )
    
    long_entry = long_state & ~long_state.shift(1, fill_value=False)
    
    selected = long_state if str(cfg["entry_mode"]) == "state" else long_entry
    
    signal = selected.fillna(False).astype("int8")
    
    if int(cfg["entry_delay_bars"]) > 0 :
        signal = signal.shift(int(cfg["entry_delay_bars"])).fillna(0).astype("int8")
    
    metadata = {
        "signal_col": str(cfg["signal_col"]),
        "mode": str(cfg["mode"]),
        "entry_mode": str(cfg["entry_mode"]),
        "entry_delay_bars": int(cfg["entry_delay_bars"]),
        "acp_threshold": float(cfg["acp_threshold"]),
        "acp_power_threshold": float(cfg["acp_power_threshold"]),
        "acp_sdv_threshold": float(cfg["acp_sdv_threshold"]),
        "acp_ratio_threshold": float(cfg["acp_ratio_threshold"]),
        "roofing_filter_threshold": float(cfg["roofing_filter_threshold"]),
        "decycler_osc_threshold": float(cfg["decycler_osc_threshold"]),
        "rolling_r2_threshold": float(cfg["rolling_r2_threshold"]),
        "rolling_r2_slope_threshold": float(cfg["rolling_r2_slope_threshold"]),
    }
    out[str(cfg["signal_col"])] = signal
    
    return out, metadata

def ehlers_cycle_long_signal(df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    """
    Apply the registered ``ehlers_cycle_long`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: ehlers_cycle_long
          params:
            entry_delay_bars: 0
            mode: long_only
            entry_mode: state
            acp_col: autocorrelation_periodogram_10_48
            acp_power_col: autocorrelation_periodogram_10_48_power
            acp_sdv_col: autocorrelation_periodogram_10_48__standard_deviation
            roofing_filter_col: roofing_filter_48_10
            roofing_filter_slope_col: roofing_filter_48_10_slope
            decycler_osc_col: decycler_oscillator_30_60
            rolling_r2_col: rolling_r2_96
            rolling_r2_slope_col: rolling_r2_slope_96
            signal_col: cycle_signal
            rolling_r2_threshold: 0.0
            rolling_r2_slope_threshold: 0.0
            acp_threshold: 30.0
            acp_power_threshold: 50.0
            acp_sdv_threshold: 5.0
            acp_ratio_threshold: 0.15
            roofing_filter_threshold: 0.0
            decycler_osc_threshold: 0.0
          output_cols:
            - cycle_signal
    
    Required input columns
    ----------------------
    acp_col:
        Input dataframe column configured by ``acp_col``. Default: ``autocorrelation_periodogram_10_48``.
    acp_power_col:
        Input dataframe column configured by ``acp_power_col``. Default: ``autocorrelation_periodogram_10_48_power``.
    acp_sdv_col:
        Input dataframe column configured by ``acp_sdv_col``. Default: ``autocorrelation_periodogram_10_48__standard_deviation``.
    roofing_filter_col:
        Input dataframe column configured by ``roofing_filter_col``. Default: ``roofing_filter_48_10``.
    roofing_filter_slope_col:
        Input dataframe column configured by ``roofing_filter_slope_col``. Default: ``roofing_filter_48_10_slope``.
    decycler_osc_col:
        Input dataframe column configured by ``decycler_osc_col``. Default: ``decycler_oscillator_30_60``.
    rolling_r2_col:
        Input dataframe column configured by ``rolling_r2_col``. Default: ``rolling_r2_96``.
    rolling_r2_slope_col:
        Input dataframe column configured by ``rolling_r2_slope_col``. Default: ``rolling_r2_slope_96``.
    
    Parameters
    ----------
    entry_delay_bars:
        Configuration parameter accepted by this signal. Default: ``0``.
    mode:
        Mode selector controlling how this signal is applied. Default: ``long_only``.
    entry_mode:
        Mode selector controlling how this signal is applied. Default: ``state``.
    acp_col:
        Input dataframe column configured by ``acp_col``. Default: ``autocorrelation_periodogram_10_48``.
    acp_power_col:
        Input dataframe column configured by ``acp_power_col``. Default: ``autocorrelation_periodogram_10_48_power``.
    acp_sdv_col:
        Input dataframe column configured by ``acp_sdv_col``. Default: ``autocorrelation_periodogram_10_48__standard_deviation``.
    roofing_filter_col:
        Input dataframe column configured by ``roofing_filter_col``. Default: ``roofing_filter_48_10``.
    roofing_filter_slope_col:
        Input dataframe column configured by ``roofing_filter_slope_col``. Default: ``roofing_filter_48_10_slope``.
    decycler_osc_col:
        Input dataframe column configured by ``decycler_osc_col``. Default: ``decycler_oscillator_30_60``.
    rolling_r2_col:
        Input dataframe column configured by ``rolling_r2_col``. Default: ``rolling_r2_96``.
    rolling_r2_slope_col:
        Input dataframe column configured by ``rolling_r2_slope_col``. Default: ``rolling_r2_slope_96``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``cycle_signal``.
    rolling_r2_threshold:
        Numeric threshold used by this signal. Default: ``0.0``.
    rolling_r2_slope_threshold:
        Numeric threshold used by this signal. Default: ``0.0``.
    acp_threshold:
        Numeric threshold used by this signal. Default: ``30.0``.
    acp_power_threshold:
        Numeric threshold used by this signal. Default: ``50.0``.
    acp_sdv_threshold:
        Numeric threshold used by this signal. Default: ``5.0``.
    acp_ratio_threshold:
        Numeric threshold used by this signal. Default: ``0.15``.
    roofing_filter_threshold:
        Numeric threshold used by this signal. Default: ``0.0``.
    decycler_osc_threshold:
        Numeric threshold used by this signal. Default: ``0.0``.
    """
    out, _ = build_ehlers_cycle_long_signal(df, params)
    return out


__all__ = ["build_ehlers_cycle_long_signal", "ehlers_cycle_long_signal"]
