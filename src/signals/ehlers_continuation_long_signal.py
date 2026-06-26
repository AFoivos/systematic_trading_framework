from __future__ import annotations

import math
from typing import Any, Mapping

import pandas as pd


_ALLOWED_ENTRY_MODES = frozenset({"state", "transition"})

_DEFAULT_CFG: dict[str, Any] = {
    "entry_mode": "state",
    "entry_delay_bars": 0,
    "long_only": True,
    "use_ema_regime": True,
    "use_mama_fama": True,
    "use_roofing_gt_slope": True,
    "use_decycler": True,
    "ema_fast_col": "ema_50",
    "ema_slow_col": "ema_100",
    "mama_col": "mama",
    "fama_col": "fama",
    "roofing_col": "roofing_filter_48_10",
    "roofing_slope_col": "roofing_filter_48_10_slope",
    "decycler_osc_col": "decycler_oscillator_30_60",
    "ema_condition_col": "ehlers_continuation_ema50_gt_ema100",
    "mama_condition_col": "ehlers_continuation_mama_gt_fama",
    "roofing_positive_col": "ehlers_continuation_roofing_gt_zero",
    "roofing_slope_positive_col": "ehlers_continuation_roofing_slope_gt_zero",
    "roofing_gt_slope_col": "ehlers_continuation_roofing_gt_slope",
    "decycler_positive_col": "ehlers_continuation_decycler_osc_gt_zero",
    "state_col": "ehlers_continuation_long_state",
    "entry_col": "ehlers_continuation_long_entry",
    "signal_col": "ehlers_continuation_signal",
    "candidate_col": "ehlers_continuation_candidate",
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


def _non_negative_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or int(value) < 0:
        raise ValueError(f"{field} must be a non-negative integer.")
    return int(value)


def _validate_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(cfg)
    entry_mode = str(normalized.get("entry_mode", "state"))
    if entry_mode not in _ALLOWED_ENTRY_MODES:
        raise ValueError(f"entry_mode must be one of: {sorted(_ALLOWED_ENTRY_MODES)}.")
    normalized["entry_mode"] = entry_mode
    normalized["entry_delay_bars"] = _non_negative_int(
        normalized.get("entry_delay_bars"),
        field="entry_delay_bars",
    )

    for key in ("long_only", "use_ema_regime", "use_mama_fama", "use_roofing_gt_slope", "use_decycler"):
        normalized[key] = _bool_value(normalized.get(key), field=key)
    if not bool(normalized["long_only"]):
        raise ValueError("ehlers_continuation_long_signal is long-only; long_only must be true.")

    string_keys = (
        "ema_fast_col",
        "ema_slow_col",
        "mama_col",
        "fama_col",
        "roofing_col",
        "roofing_slope_col",
        "decycler_osc_col",
        "ema_condition_col",
        "mama_condition_col",
        "roofing_positive_col",
        "roofing_slope_positive_col",
        "roofing_gt_slope_col",
        "decycler_positive_col",
        "state_col",
        "entry_col",
        "signal_col",
        "candidate_col",
    )
    for key in string_keys:
        normalized[key] = _string_value(normalized.get(key), field=key)
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


def build_ehlers_continuation_long_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Build the long-only Ehlers bullish continuation signal.

    The default state is the six-condition v1 rule. Optional condition toggles are used only
    for ablations and leave the v1 defaults unchanged.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))
    required_cols = [str(cfg["roofing_col"]), str(cfg["roofing_slope_col"])]
    if bool(cfg["use_ema_regime"]):
        required_cols.extend([str(cfg["ema_fast_col"]), str(cfg["ema_slow_col"])])
    if bool(cfg["use_mama_fama"]):
        required_cols.extend([str(cfg["mama_col"]), str(cfg["fama_col"])])
    if bool(cfg["use_decycler"]):
        required_cols.append(str(cfg["decycler_osc_col"]))
    _require_columns(df, list(dict.fromkeys(required_cols)))

    out = df.copy()
    ema_fast = _optional_numeric(out, str(cfg["ema_fast_col"]))
    ema_slow = _optional_numeric(out, str(cfg["ema_slow_col"]))
    mama = _optional_numeric(out, str(cfg["mama_col"]))
    fama = _optional_numeric(out, str(cfg["fama_col"]))
    roofing = _numeric(out, str(cfg["roofing_col"]))
    roofing_slope = _numeric(out, str(cfg["roofing_slope_col"]))
    decycler_osc = _optional_numeric(out, str(cfg["decycler_osc_col"]))

    ema_condition = ema_fast.gt(ema_slow)
    mama_condition = mama.gt(fama)
    roofing_positive = roofing.gt(0.0)
    roofing_slope_positive = roofing_slope.gt(0.0)
    roofing_gt_slope = roofing.gt(roofing_slope)
    decycler_positive = decycler_osc.gt(0.0)

    valid = roofing.notna() & roofing_slope.notna()
    long_state = roofing_positive & roofing_slope_positive
    if bool(cfg["use_ema_regime"]):
        valid &= ema_fast.notna() & ema_slow.notna()
        long_state &= ema_condition
    if bool(cfg["use_mama_fama"]):
        valid &= mama.notna() & fama.notna()
        long_state &= mama_condition
    if bool(cfg["use_roofing_gt_slope"]):
        long_state &= roofing_gt_slope
    if bool(cfg["use_decycler"]):
        valid &= decycler_osc.notna()
        long_state &= decycler_positive
    long_state &= valid
    long_entry = long_state & ~long_state.shift(1, fill_value=False)

    selected = long_state if str(cfg["entry_mode"]) == "state" else long_entry
    signal = selected.fillna(False).astype("int8")
    if int(cfg["entry_delay_bars"]) > 0:
        signal = signal.shift(int(cfg["entry_delay_bars"])).fillna(0).astype("int8")

    out[str(cfg["ema_condition_col"])] = ema_condition.fillna(False).astype("int8")
    out[str(cfg["mama_condition_col"])] = mama_condition.fillna(False).astype("int8")
    out[str(cfg["roofing_positive_col"])] = roofing_positive.fillna(False).astype("int8")
    out[str(cfg["roofing_slope_positive_col"])] = roofing_slope_positive.fillna(False).astype("int8")
    out[str(cfg["roofing_gt_slope_col"])] = roofing_gt_slope.fillna(False).astype("int8")
    out[str(cfg["decycler_positive_col"])] = decycler_positive.fillna(False).astype("int8")
    out[str(cfg["state_col"])] = long_state.fillna(False).astype("int8")
    out[str(cfg["entry_col"])] = long_entry.fillna(False).astype("int8")
    out[str(cfg["signal_col"])] = signal
    out[str(cfg["candidate_col"])] = signal.ne(0).astype("int8")

    return out, {
        "kind": "ehlers_continuation_long",
        "entry_mode": str(cfg["entry_mode"]),
        "entry_delay_bars": int(cfg["entry_delay_bars"]),
        "long_only": True,
        "use_ema_regime": bool(cfg["use_ema_regime"]),
        "use_mama_fama": bool(cfg["use_mama_fama"]),
        "use_roofing_gt_slope": bool(cfg["use_roofing_gt_slope"]),
        "use_decycler": bool(cfg["use_decycler"]),
        "long_state_rows": int(long_state.sum()),
        "long_entry_rows": int(long_entry.sum()),
        "signal_rows": int(signal.sum()),
        "state_col": str(cfg["state_col"]),
        "entry_col": str(cfg["entry_col"]),
        "signal_col": str(cfg["signal_col"]),
        "candidate_col": str(cfg["candidate_col"]),
    }


def ehlers_continuation_long_signal(df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    """
    Apply the registered ``ehlers_continuation_long`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: ehlers_continuation_long
          params:
            entry_mode: state
            entry_delay_bars: 0
            long_only: true
            use_ema_regime: true
            use_mama_fama: true
            use_roofing_gt_slope: true
            use_decycler: true
            ema_fast_col: ema_50
            ema_slow_col: ema_100
            mama_col: mama
            fama_col: fama
            roofing_col: roofing_filter_48_10
            roofing_slope_col: roofing_filter_48_10_slope
            decycler_osc_col: decycler_oscillator_30_60
            ema_condition_col: ehlers_continuation_ema50_gt_ema100
            mama_condition_col: ehlers_continuation_mama_gt_fama
            roofing_positive_col: ehlers_continuation_roofing_gt_zero
            roofing_slope_positive_col: ehlers_continuation_roofing_slope_gt_zero
            roofing_gt_slope_col: ehlers_continuation_roofing_gt_slope
            decycler_positive_col: ehlers_continuation_decycler_osc_gt_zero
            state_col: ehlers_continuation_long_state
            entry_col: ehlers_continuation_long_entry
            signal_col: ehlers_continuation_signal
            candidate_col: ehlers_continuation_candidate
          output_cols:
            - ehlers_continuation_signal
            - ehlers_continuation_candidate
    
    Required input columns
    ----------------------
    ema_fast_col:
        Input dataframe column configured by ``ema_fast_col``. Default: ``ema_50``.
    ema_slow_col:
        Input dataframe column configured by ``ema_slow_col``. Default: ``ema_100``.
    mama_col:
        Input dataframe column configured by ``mama_col``. Default: ``mama``.
    fama_col:
        Input dataframe column configured by ``fama_col``. Default: ``fama``.
    roofing_col:
        Input dataframe column configured by ``roofing_col``. Default: ``roofing_filter_48_10``.
    roofing_slope_col:
        Input dataframe column configured by ``roofing_slope_col``. Default: ``roofing_filter_48_10_slope``.
    decycler_osc_col:
        Input dataframe column configured by ``decycler_osc_col``. Default: ``decycler_oscillator_30_60``.
    ema_condition_col:
        Input dataframe column configured by ``ema_condition_col``. Default: ``ehlers_continuation_ema50_gt_ema100``.
    mama_condition_col:
        Input dataframe column configured by ``mama_condition_col``. Default: ``ehlers_continuation_mama_gt_fama``.
    roofing_positive_col:
        Input dataframe column configured by ``roofing_positive_col``. Default: ``ehlers_continuation_roofing_gt_zero``.
    roofing_slope_positive_col:
        Input dataframe column configured by ``roofing_slope_positive_col``. Default: ``ehlers_continuation_roofing_slope_gt_zero``.
    roofing_gt_slope_col:
        Input dataframe column configured by ``roofing_gt_slope_col``. Default: ``ehlers_continuation_roofing_gt_slope``.
    decycler_positive_col:
        Input dataframe column configured by ``decycler_positive_col``. Default: ``ehlers_continuation_decycler_osc_gt_zero``.
    state_col:
        Input dataframe column configured by ``state_col``. Default: ``ehlers_continuation_long_state``.
    entry_col:
        Input dataframe column configured by ``entry_col``. Default: ``ehlers_continuation_long_entry``.
    
    Parameters
    ----------
    entry_mode:
        Mode selector controlling how this signal is applied. Default: ``state``.
    entry_delay_bars:
        Configuration parameter accepted by this signal. Default: ``0``.
    long_only:
        Configuration parameter accepted by this signal. Default: ``true``.
    use_ema_regime:
        Boolean switch controlling optional signal behavior. Default: ``true``.
    use_mama_fama:
        Boolean switch controlling optional signal behavior. Default: ``true``.
    use_roofing_gt_slope:
        Boolean switch controlling optional signal behavior. Default: ``true``.
    use_decycler:
        Boolean switch controlling optional signal behavior. Default: ``true``.
    ema_fast_col:
        Input dataframe column configured by ``ema_fast_col``. Default: ``ema_50``.
    ema_slow_col:
        Input dataframe column configured by ``ema_slow_col``. Default: ``ema_100``.
    mama_col:
        Input dataframe column configured by ``mama_col``. Default: ``mama``.
    fama_col:
        Input dataframe column configured by ``fama_col``. Default: ``fama``.
    roofing_col:
        Input dataframe column configured by ``roofing_col``. Default: ``roofing_filter_48_10``.
    roofing_slope_col:
        Input dataframe column configured by ``roofing_slope_col``. Default: ``roofing_filter_48_10_slope``.
    decycler_osc_col:
        Input dataframe column configured by ``decycler_osc_col``. Default: ``decycler_oscillator_30_60``.
    ema_condition_col:
        Input dataframe column configured by ``ema_condition_col``. Default: ``ehlers_continuation_ema50_gt_ema100``.
    mama_condition_col:
        Input dataframe column configured by ``mama_condition_col``. Default: ``ehlers_continuation_mama_gt_fama``.
    roofing_positive_col:
        Input dataframe column configured by ``roofing_positive_col``. Default: ``ehlers_continuation_roofing_gt_zero``.
    roofing_slope_positive_col:
        Input dataframe column configured by ``roofing_slope_positive_col``. Default: ``ehlers_continuation_roofing_slope_gt_zero``.
    roofing_gt_slope_col:
        Input dataframe column configured by ``roofing_gt_slope_col``. Default: ``ehlers_continuation_roofing_gt_slope``.
    decycler_positive_col:
        Input dataframe column configured by ``decycler_positive_col``. Default: ``ehlers_continuation_decycler_osc_gt_zero``.
    state_col:
        Input dataframe column configured by ``state_col``. Default: ``ehlers_continuation_long_state``.
    entry_col:
        Input dataframe column configured by ``entry_col``. Default: ``ehlers_continuation_long_entry``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``ehlers_continuation_signal``.
    candidate_col:
        Output dataframe column configured by ``candidate_col``. Default: ``ehlers_continuation_candidate``.
    """
    out, _ = build_ehlers_continuation_long_signal(df, params)
    return out


__all__ = ["build_ehlers_continuation_long_signal", "ehlers_continuation_long_signal"]
