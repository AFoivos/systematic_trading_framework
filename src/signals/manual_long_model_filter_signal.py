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
    volatility_col: str | None = None,
    round_trip_cost_return: float = 0.0,
    cost_buffer_r: float = 0.0,
    signal_col: str | None = None,
) -> pd.Series:
    """
    Apply the registered ``manual_long_model_filter`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: manual_long_model_filter
          params:
            prob_col: pred_prob
            candidate_col: manual_long_candidate
            base_signal_col: manual_vol_adjusted_candidate
            threshold: 0.55
            gate_col: null
            gate_cols_any: null
            min_signal_abs: 0.0
            expected_value_col: null
            min_expected_value_r: null
            profit_barrier_r: 1.0
            stop_barrier_r: 1.0
            volatility_col: null
            round_trip_cost_return: 0.0
            cost_buffer_r: 0.0
            signal_col: null
            output_cols:
              - manual_long_candidate
              - configured by signal_col
    
    Required input columns
    ----------------------
    prob_col:
        Input dataframe column configured by ``prob_col``. Default: ``pred_prob``.
    gate_col:
        Input dataframe column configured by ``gate_col``. Default: ``null``.
    expected_value_col:
        Input dataframe column configured by ``expected_value_col``. Default: ``null``.
    volatility_col:
        Input dataframe column configured by ``volatility_col``. Default: ``null``.
    
    Parameters
    ----------
    prob_col:
        Input dataframe column configured by ``prob_col``. Default: ``pred_prob``.
    candidate_col:
        Output dataframe column configured by ``candidate_col``. Default: ``manual_long_candidate``.
    base_signal_col:
        Input dataframe column configured by ``base_signal_col``. Default: ``manual_vol_adjusted_candidate``.
    threshold:
        Numeric threshold used by this signal. Default: ``0.55``.
    gate_col:
        Input dataframe column configured by ``gate_col``. Default: ``null``.
    gate_cols_any:
        Configuration parameter accepted by this signal. Default: ``null``.
    min_signal_abs:
        Configuration parameter accepted by this signal. Default: ``0.0``.
    expected_value_col:
        Input dataframe column configured by ``expected_value_col``. Default: ``null``.
    min_expected_value_r:
        Configuration parameter accepted by this signal. Default: ``null``.
    profit_barrier_r:
        Configuration parameter accepted by this signal. Default: ``1.0``.
    stop_barrier_r:
        Configuration parameter accepted by this signal. Default: ``1.0``.
    volatility_col:
        Input dataframe column configured by ``volatility_col``. Default: ``null``.
    round_trip_cost_return:
        Configuration parameter accepted by this signal. Default: ``0.0``.
    cost_buffer_r:
        Configuration parameter accepted by this signal. Default: ``0.0``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``null``.
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
    round_trip_cost = float(round_trip_cost_return)
    if not np.isfinite(round_trip_cost) or round_trip_cost < 0.0:
        raise ValueError("manual_long_model_filter_signal round_trip_cost_return must be >= 0.")
    cost_buffer = float(cost_buffer_r)
    if not np.isfinite(cost_buffer) or cost_buffer < 0.0:
        raise ValueError("manual_long_model_filter_signal cost_buffer_r must be >= 0.")
    if round_trip_cost > 0.0 and volatility_col is None:
        raise ValueError("manual_long_model_filter_signal volatility_col is required when round_trip_cost_return > 0.")

    any_gate_cols = _normalize_optional_columns(gate_cols_any, field="gate_cols_any")
    required_columns = [prob_col, candidate_col, base_signal_col]
    if gate_col is not None:
        required_columns.append(gate_col)
    required_columns.extend(any_gate_cols)
    if expected_value_col is not None:
        required_columns.append(expected_value_col)
    if volatility_col is not None:
        required_columns.append(volatility_col)
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
            if round_trip_cost > 0.0:
                volatility = pd.to_numeric(df[str(volatility_col)], errors="coerce")
                stop_distance = stop_r * volatility.where(volatility.gt(0.0), np.nan)
                expected_value = expected_value - round_trip_cost / stop_distance
            expected_value = expected_value - cost_buffer
        passes_filter &= expected_value.ge(min_ev).fillna(False)

    signal = long_exposure.where(passes_filter, other=0.0).astype("float32")
    signal.name = output_col
    return signal


__all__ = ["manual_long_model_filter_signal"]
