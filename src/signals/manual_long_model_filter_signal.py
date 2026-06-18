from __future__ import annotations

import numpy as np
import pandas as pd


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for manual_long_model_filter_signal: {missing}")


def _normalize_optional_columns(columns: list[str] | tuple[str, ...] | None, *, field: str) -> list[str]:
    if columns is None:
        return []
    if not isinstance(columns, (list, tuple)):
        raise ValueError(f"manual_long_model_filter_signal {field} must be a list of column names.")
    out = [str(col) for col in columns]
    if any(not col.strip() for col in out):
        raise ValueError(f"manual_long_model_filter_signal {field} must contain non-empty column names.")
    return out


def manual_long_model_filter_signal(
    df: pd.DataFrame,
    *,
    prob_col: str = "pred_prob",
    candidate_col: str = "manual_long_candidate",
    base_signal_col: str = "manual_vol_adjusted_candidate",
    threshold: float = 0.55,
    gate_col: str | None = None,
    gate_cols_any: list[str] | tuple[str, ...] | None = None,
    min_signal_abs: float = 0.0,
    expected_value_col: str | None = None,
    min_expected_value_r: float | None = None,
    profit_barrier_r: float = 1.0,
    stop_barrier_r: float = 1.0,
    signal_col: str | None = None,
) -> pd.Series:
    """
    Filter manual long candidates with an out-of-sample model probability.

    The model is only a long-entry filter. It cannot create trades without a manual candidate,
    cannot flip direction, and cannot emit short exposure.

    YAML declaration::

        signals:
          kind: manual_long_model_filter
          params: {}
    """
    output_col = str(signal_col or "model_filtered_long_signal")
    threshold_value = float(threshold)
    if not np.isfinite(threshold_value) or not 0.0 < threshold_value < 1.0:
        raise ValueError("manual_long_model_filter_signal threshold must be in (0, 1).")
    min_signal_value = float(min_signal_abs)
    if not np.isfinite(min_signal_value) or min_signal_value < 0.0:
        raise ValueError("manual_long_model_filter_signal min_signal_abs must be >= 0.")
    profit_r = float(profit_barrier_r)
    stop_r = float(stop_barrier_r)
    if not np.isfinite(profit_r) or profit_r <= 0.0:
        raise ValueError("manual_long_model_filter_signal profit_barrier_r must be > 0.")
    if not np.isfinite(stop_r) or stop_r <= 0.0:
        raise ValueError("manual_long_model_filter_signal stop_barrier_r must be > 0.")
    min_ev: float | None = None
    if min_expected_value_r is not None:
        min_ev = float(min_expected_value_r)
        if not np.isfinite(min_ev):
            raise ValueError("manual_long_model_filter_signal min_expected_value_r must be finite.")

    any_gate_cols = _normalize_optional_columns(gate_cols_any, field="gate_cols_any")
    required_columns = [prob_col, candidate_col, base_signal_col]
    if gate_col is not None:
        required_columns.append(gate_col)
    required_columns.extend(any_gate_cols)
    if expected_value_col is not None:
        required_columns.append(expected_value_col)
    _require_columns(df, required_columns)

    pred_prob = pd.to_numeric(df[prob_col], errors="coerce")
    candidate = pd.to_numeric(df[candidate_col], errors="coerce").fillna(0.0).gt(0.0)
    base_signal = pd.to_numeric(df[base_signal_col], errors="coerce").fillna(0.0)
    long_exposure = base_signal.clip(lower=0.0)

    passes_filter = (
        candidate
        & pred_prob.ge(threshold_value).fillna(False)
        & long_exposure.ge(min_signal_value).fillna(False)
    )
    if gate_col is not None:
        gate = pd.to_numeric(df[gate_col], errors="coerce").fillna(0.0).gt(0.0)
        passes_filter &= gate
    if any_gate_cols:
        any_gate = pd.Series(False, index=df.index)
        for column in any_gate_cols:
            column_gate = pd.to_numeric(df[column], errors="coerce").fillna(0.0).gt(0.0)
            any_gate |= column_gate
        passes_filter &= any_gate
    if min_ev is not None:
        if expected_value_col is not None:
            expected_value = pd.to_numeric(df[expected_value_col], errors="coerce")
        else:
            probability = pred_prob.clip(lower=0.0, upper=1.0)
            expected_value = probability * profit_r - (1.0 - probability) * stop_r
        passes_filter &= expected_value.ge(min_ev).fillna(False)

    signal = long_exposure.where(passes_filter, other=0.0).astype("float32")
    signal.name = output_col
    return signal


__all__ = ["manual_long_model_filter_signal"]
