from __future__ import annotations

from numbers import Real
from typing import Any, Mapping

import pandas as pd


_DEFAULT_CFG: dict[str, Any] = {
    "decycler_osc_col": "decycler_oscillator_30_60",
    "decycler_ratio_col": "ehlers_decycler_over_close",
    "decycler_osc_min": 0.45,
    "decycler_ratio_max": 0.9940,
    "entry_mode": "state",
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


def _validate_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(cfg)
    for key in ("decycler_osc_col", "decycler_ratio_col", "signal_col", "candidate_col"):
        value = normalized.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string.")
        normalized[key] = value.strip()
    for key in ("decycler_osc_min", "decycler_ratio_max"):
        value = normalized.get(key)
        if isinstance(value, bool) or not isinstance(value, Real) or not pd.notna(float(value)):
            raise ValueError(f"{key} must be a finite number.")
        normalized[key] = float(value)
    if normalized.get("entry_mode") not in {"state", "transition"}:
        raise ValueError("entry_mode must be one of: state, transition.")
    return normalized


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for ehlers_decycler_continuation_signal: {missing}")


def build_ehlers_decycler_continuation_signal(
    df: pd.DataFrame,
    signal_cfg: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Build a long-only Ehlers decycler continuation candidate.

    This is a causal threshold rule over already-computed Ehlers features. It
    does not estimate thresholds at runtime; thresholds must be declared in the
    config, preferably from a training-only calibration window.

    YAML declaration::

        signals:
          kind: ehlers_decycler_continuation
          params:
            decycler_osc_col: decycler_oscillator_30_60
            decycler_ratio_col: ehlers_decycler_over_close
            decycler_osc_min: 0.45
            decycler_ratio_max: 0.9940
            signal_col: signal_side
            candidate_col: signal_candidate

    Required input columns
    ----------------------
    decycler_osc_col:
        Decycler oscillator column. Larger values indicate stronger
        continuation pressure.
    decycler_ratio_col:
        Decycler divided by close. Lower values indicate price stretched above
        the decycler trend estimate.

    Parameters
    ----------
    decycler_osc_col:
        Input dataframe column name consumed by the component.
    decycler_ratio_col:
        Input dataframe column name consumed by the component.
    decycler_osc_min:
        Minimum decycler oscillator value required.
    decycler_ratio_max:
        Maximum decycler/close ratio allowed.
    entry_mode:
        If ``state``, emits while both conditions hold. If ``transition``,
        emits only on false-to-true changes.
    signal_col:
        Output long-side signal column.
    candidate_col:
        Output model/backtest candidate column.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")
    cfg = _validate_cfg(_merge_cfg(signal_cfg, overrides))
    _require_columns(df, [cfg["decycler_osc_col"], cfg["decycler_ratio_col"]])

    osc = pd.to_numeric(df[cfg["decycler_osc_col"]], errors="coerce").astype(float)
    ratio = pd.to_numeric(df[cfg["decycler_ratio_col"]], errors="coerce").astype(float)
    state = osc.ge(float(cfg["decycler_osc_min"])) & ratio.le(float(cfg["decycler_ratio_max"]))
    selected = state & ~state.shift(1, fill_value=False) if cfg["entry_mode"] == "transition" else state

    out = df.copy()
    out[cfg["signal_col"]] = selected.fillna(False).astype("int8")
    out[cfg["candidate_col"]] = selected.fillna(False).astype("int8")
    return out, {
        "kind": "ehlers_decycler_continuation",
        "long_only": True,
        "entry_mode": str(cfg["entry_mode"]),
        "decycler_osc_col": str(cfg["decycler_osc_col"]),
        "decycler_ratio_col": str(cfg["decycler_ratio_col"]),
        "decycler_osc_min": float(cfg["decycler_osc_min"]),
        "decycler_ratio_max": float(cfg["decycler_ratio_max"]),
        "candidate_rows": int(out[cfg["candidate_col"]].sum()),
        "signal_col": str(cfg["signal_col"]),
        "candidate_col": str(cfg["candidate_col"]),
    }


def ehlers_decycler_continuation_feature(df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    """
    Apply the registered ``ehlers_decycler_continuation`` feature-compatible transformation.

    This compatibility feature applies the same long-only Ehlers decycler
    continuation rule used by the signal registry, but exposes the result as a
    feature/model setup step for older experiment and dashboard configurations.

    YAML declaration::

        features:
          - step: ehlers_decycler_continuation
            params:
              decycler_osc_col: decycler_oscillator_30_60
              decycler_ratio_col: ehlers_decycler_over_close
              decycler_osc_min: 0.45
              decycler_ratio_max: 0.994
              entry_mode: state
              signal_col: signal_side
              candidate_col: signal_candidate
          output_cols:
            - signal_side
            - signal_candidate

    Required input columns
    ----------------------
    decycler_osc_col:
        Decycler oscillator column.
    decycler_ratio_col:
        Decycler divided by close or equivalent ratio helper output.

    Parameters
    ----------
    params:
        Additional keyword parameters accepted from YAML ``params``. Supported
        keys match ``ehlers_decycler_continuation`` signal parameters.
    """
    out, _ = build_ehlers_decycler_continuation_signal(df, params)
    return out


def ehlers_decycler_continuation_signal(df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    """
    Apply the registered ``ehlers_decycler_continuation`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: ehlers_decycler_continuation
          params:
            decycler_osc_col: decycler_oscillator_30_60
            decycler_ratio_col: ehlers_decycler_over_close
            decycler_osc_min: 0.45
            decycler_ratio_max: 0.994
            entry_mode: state
            signal_col: signal_side
            candidate_col: signal_candidate
          output_cols:
            - signal_candidate
    
    Required input columns
    ----------------------
    decycler_osc_col:
        Input dataframe column configured by ``decycler_osc_col``. Default: ``decycler_oscillator_30_60``.
    decycler_ratio_col:
        Input dataframe column configured by ``decycler_ratio_col``. Default: ``ehlers_decycler_over_close``.
    
    Parameters
    ----------
    decycler_osc_col:
        Input dataframe column configured by ``decycler_osc_col``. Default: ``decycler_oscillator_30_60``.
    decycler_ratio_col:
        Input dataframe column configured by ``decycler_ratio_col``. Default: ``ehlers_decycler_over_close``.
    decycler_osc_min:
        Numeric threshold used by this signal. Default: ``0.45``.
    decycler_ratio_max:
        Numeric threshold used by this signal. Default: ``0.994``.
    entry_mode:
        Mode selector controlling how this signal is applied. Default: ``state``.
    signal_col:
        Input dataframe column configured by ``signal_col``. Default: ``signal_side``.
    candidate_col:
        Output dataframe column configured by ``candidate_col``. Default: ``signal_candidate``.
    """
    out, _ = build_ehlers_decycler_continuation_signal(df, params)
    return out


__all__ = [
    "build_ehlers_decycler_continuation_signal",
    "ehlers_decycler_continuation_feature",
    "ehlers_decycler_continuation_signal",
]
