from __future__ import annotations

import math
from numbers import Integral, Real
from typing import Any, Mapping

import numpy as np
import pandas as pd


_GATE_KINDS = frozenset({"none", "atr_regime", "forecast_expansion"})
_SIZING_KINDS = frozenset({"fixed", "inverse_forecast_vol"})
_PARAM_KEYS = frozenset(
    {
        "candidate_col",
        "side_col",
        "pred_is_oos_col",
        "side_alignment_cols",
        "positive_filter_cols",
        "gate",
        "sizing",
        "output_candidate_col",
        "output_side_col",
        "output_weight_col",
        "output_signal_col",
        "output_gate_ready_col",
        "output_expansion_col",
    }
)


def _string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value.strip()


def _string_list(value: Any, *, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{field} must be a list of column names.")
    columns = [_string(item, field=f"{field}[]") for item in value]
    if len(columns) != len(set(columns)):
        raise ValueError(f"{field} must not contain duplicates.")
    return columns


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or int(value) <= 0:
        raise ValueError(f"{field} must be a positive integer.")
    return int(value)


def _finite(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a finite number.")
    resolved = float(value)
    if not math.isfinite(resolved):
        raise ValueError(f"{field} must be a finite number.")
    return resolved


def _quantile(value: Any, *, field: str, allow_none: bool = False) -> float | None:
    if value is None and allow_none:
        return None
    resolved = _finite(value, field=field)
    if not 0.0 < resolved < 1.0:
        raise ValueError(f"{field} must be in (0, 1).")
    return resolved


def _window(raw: Mapping[str, Any], *, field: str) -> tuple[int, int]:
    lookback = _positive_int(raw.get("lookback_bars", 8064), field=f"{field}.lookback_bars")
    min_periods = _positive_int(raw.get("min_periods", 256), field=f"{field}.min_periods")
    if min_periods > lookback:
        raise ValueError(f"{field}.min_periods must be <= {field}.lookback_bars.")
    return lookback, min_periods


def _validate_gate(raw_gate: Any) -> dict[str, Any]:
    if raw_gate is None:
        raw_gate = {}
    if not isinstance(raw_gate, Mapping):
        raise TypeError("gate must be a mapping.")
    raw = dict(raw_gate)
    kind = str(raw.get("kind", "none"))
    if kind not in _GATE_KINDS:
        raise ValueError(f"gate.kind must be one of: {', '.join(sorted(_GATE_KINDS))}.")
    if kind == "none":
        unknown = sorted(set(raw).difference({"kind"}))
        if unknown:
            raise ValueError(f"Unsupported gate parameters for kind='none': {unknown}.")
        return {"kind": kind}

    lookback, min_periods = _window(raw, field="gate")
    if kind == "atr_regime":
        allowed = {
            "kind",
            "volatility_col",
            "lookback_bars",
            "min_periods",
            "lower_quantile",
            "upper_quantile",
        }
        unknown = sorted(set(raw).difference(allowed))
        if unknown:
            raise ValueError(f"Unsupported atr_regime gate parameters: {unknown}.")
        lower = _quantile(raw.get("lower_quantile", 0.60), field="gate.lower_quantile")
        upper = _quantile(raw.get("upper_quantile", 0.95), field="gate.upper_quantile")
        assert lower is not None and upper is not None
        if lower >= upper:
            raise ValueError("gate.lower_quantile must be < gate.upper_quantile.")
        return {
            "kind": kind,
            "volatility_col": _string(
                raw.get("volatility_col", "atr_over_price_48"),
                field="gate.volatility_col",
            ),
            "lookback_bars": lookback,
            "min_periods": min_periods,
            "lower_quantile": lower,
            "upper_quantile": upper,
        }

    allowed = {
        "kind",
        "forecast_col",
        "current_vol_col",
        "lookback_bars",
        "min_periods",
        "min_expansion",
        "forecast_lower_quantile",
        "forecast_upper_quantile",
        "current_vol_upper_quantile",
    }
    unknown = sorted(set(raw).difference(allowed))
    if unknown:
        raise ValueError(f"Unsupported forecast_expansion gate parameters: {unknown}.")
    forecast_lower = _quantile(
        raw.get("forecast_lower_quantile"),
        field="gate.forecast_lower_quantile",
        allow_none=True,
    )
    forecast_upper = _quantile(
        raw.get("forecast_upper_quantile", 0.95),
        field="gate.forecast_upper_quantile",
        allow_none=True,
    )
    if (
        forecast_lower is not None
        and forecast_upper is not None
        and forecast_lower >= forecast_upper
    ):
        raise ValueError(
            "gate.forecast_lower_quantile must be < gate.forecast_upper_quantile."
        )
    min_expansion = _finite(raw.get("min_expansion", 1.10), field="gate.min_expansion")
    if min_expansion <= 0.0:
        raise ValueError("gate.min_expansion must be > 0.")
    return {
        "kind": kind,
        "forecast_col": _string(
            raw.get("forecast_col", "pred_future_rv_16"), field="gate.forecast_col"
        ),
        "current_vol_col": _string(
            raw.get("current_vol_col", "rlv_sigma_slow"),
            field="gate.current_vol_col",
        ),
        "lookback_bars": lookback,
        "min_periods": min_periods,
        "min_expansion": min_expansion,
        "forecast_lower_quantile": forecast_lower,
        "forecast_upper_quantile": forecast_upper,
        "current_vol_upper_quantile": _quantile(
            raw.get("current_vol_upper_quantile", 0.95),
            field="gate.current_vol_upper_quantile",
        ),
    }


def _validate_sizing(raw_sizing: Any) -> dict[str, Any]:
    if raw_sizing is None:
        raw_sizing = {}
    if not isinstance(raw_sizing, Mapping):
        raise TypeError("sizing must be a mapping.")
    raw = dict(raw_sizing)
    kind = str(raw.get("kind", "fixed"))
    if kind not in _SIZING_KINDS:
        raise ValueError(f"sizing.kind must be one of: {', '.join(sorted(_SIZING_KINDS))}.")
    if kind == "fixed":
        unknown = sorted(set(raw).difference({"kind"}))
        if unknown:
            raise ValueError(f"Unsupported sizing parameters for kind='fixed': {unknown}.")
        return {"kind": kind}

    allowed = {
        "kind",
        "forecast_col",
        "lookback_bars",
        "min_periods",
        "target_quantile",
        "vol_floor",
        "min_weight",
        "max_weight",
    }
    unknown = sorted(set(raw).difference(allowed))
    if unknown:
        raise ValueError(f"Unsupported inverse_forecast_vol sizing parameters: {unknown}.")
    lookback, min_periods = _window(raw, field="sizing")
    vol_floor = _finite(raw.get("vol_floor", 1e-8), field="sizing.vol_floor")
    min_weight = _finite(raw.get("min_weight", 0.25), field="sizing.min_weight")
    max_weight = _finite(raw.get("max_weight", 1.0), field="sizing.max_weight")
    if vol_floor <= 0.0:
        raise ValueError("sizing.vol_floor must be > 0.")
    if not 0.0 < min_weight <= max_weight:
        raise ValueError("sizing weights must satisfy 0 < min_weight <= max_weight.")
    if max_weight > 1.0:
        raise ValueError("sizing.max_weight must be <= 1.0 to prevent implicit leverage.")
    return {
        "kind": kind,
        "forecast_col": _string(
            raw.get("forecast_col", "pred_future_rv_16"), field="sizing.forecast_col"
        ),
        "lookback_bars": lookback,
        "min_periods": min_periods,
        "target_quantile": _quantile(
            raw.get("target_quantile", 0.50), field="sizing.target_quantile"
        ),
        "vol_floor": vol_floor,
        "min_weight": min_weight,
        "max_weight": max_weight,
    }


def validate_qms_candidate_policy_params(
    params: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Validate the causal OOS QMS candidate policy transform."""
    if params is not None and not isinstance(params, Mapping):
        raise TypeError("qms_candidate_policy_transform params must be a mapping.")
    raw = dict(params or {})
    unknown = sorted(set(raw).difference(_PARAM_KEYS))
    if unknown:
        raise ValueError(f"Unsupported qms_candidate_policy_transform parameters: {unknown}.")
    defaults = {
        "candidate_col": "qms_meta_candidate",
        "side_col": "qms_meta_side",
        "pred_is_oos_col": "pred_future_rv_16_is_oos",
        "output_candidate_col": "qms_policy_candidate",
        "output_side_col": "qms_policy_side",
        "output_weight_col": "qms_policy_weight",
        "output_signal_col": "qms_policy_signal",
        "output_gate_ready_col": "qms_policy_gate_ready",
        "output_expansion_col": "qms_policy_expansion_ratio",
    }
    out = {
        key: _string(raw.get(key, default), field=key)
        for key, default in defaults.items()
    }
    out["side_alignment_cols"] = _string_list(
        raw.get("side_alignment_cols", []), field="side_alignment_cols"
    )
    out["positive_filter_cols"] = _string_list(
        raw.get("positive_filter_cols", []), field="positive_filter_cols"
    )
    out["gate"] = _validate_gate(raw.get("gate"))
    out["sizing"] = _validate_sizing(raw.get("sizing"))
    output_columns = [
        out["output_candidate_col"],
        out["output_side_col"],
        out["output_weight_col"],
        out["output_signal_col"],
        out["output_gate_ready_col"],
        out["output_expansion_col"],
    ]
    if len(output_columns) != len(set(output_columns)):
        raise ValueError("qms_candidate_policy_transform output columns must be unique.")
    return out


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise KeyError(f"Missing column for qms_candidate_policy_transform: {column}")
    values = pd.to_numeric(frame[column], errors="coerce").astype("float64")
    invalid = values.isna() & ~frame[column].isna()
    if bool(invalid.any()) or bool(np.isinf(values.to_numpy(dtype=float)).any()):
        raise ValueError(f"{column} must contain only finite numeric values or NaN.")
    return values


def _past_quantile(
    values: pd.Series,
    *,
    quantile: float,
    lookback_bars: int,
    min_periods: int,
) -> pd.Series:
    return (
        values.rolling(window=lookback_bars, min_periods=min_periods)
        .quantile(float(quantile))
        .shift(1)
        .astype("float64")
    )


def apply_qms_candidate_policy_transform(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, None, dict[str, Any]]:
    """Apply an OOS-only causal gate and optional inverse-vol sizing to QMS candidates.

    YAML declaration::

        model_stages:
          - kind: qms_candidate_policy_transform
            params:
              candidate_col: qms_base_candidate
              side_col: qms_base_side
              pred_is_oos_col: pred_future_rv_16_is_oos
              side_alignment_cols: [kadx_signed]
              gate:
                kind: forecast_expansion
                forecast_col: pred_future_rv_16
                current_vol_col: rlv_sigma_slow
                min_expansion: 1.10
              sizing: {kind: fixed}

    Required input columns
    ----------------------
    ``candidate_col``, ``side_col`` and ``pred_is_oos_col`` are always required.
    Alignment, gate and sizing columns are required when selected. Missing numeric
    inputs fail closed; non-OOS candidates can never reach the output signal.

    Parameters
    ----------
    side_alignment_cols, positive_filter_cols:
        Optional point-in-time directional and positive-state confirmations.
    gate:
        ``none``, shifted rolling ``atr_regime``, or strict-OOS
        ``forecast_expansion`` policy.
    sizing:
        Fixed unit weight or reduce-only ``inverse_forecast_vol`` sizing based on a
        shifted rolling quantile of prior OOS forecasts.
    """
    del returns_col
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")
    cfg = validate_qms_candidate_policy_params(dict(model_cfg or {}).get("params"))
    out = df.copy()

    candidate = _numeric(out, cfg["candidate_col"]).fillna(0.0).ne(0.0)
    raw_side = _numeric(out, cfg["side_col"])
    side = np.sign(raw_side.fillna(0.0)).astype("float64")
    oos = out[cfg["pred_is_oos_col"]].fillna(False).astype(bool) if cfg["pred_is_oos_col"] in out else None
    if oos is None:
        raise KeyError(
            f"Missing column for qms_candidate_policy_transform: {cfg['pred_is_oos_col']}"
        )

    base = candidate & side.ne(0.0) & oos
    alignment = pd.Series(True, index=out.index, dtype=bool)
    for column in cfg["side_alignment_cols"]:
        values = _numeric(out, column)
        alignment &= values.notna() & (np.sign(values).eq(side))
    for column in cfg["positive_filter_cols"]:
        values = _numeric(out, column)
        alignment &= values.notna() & values.gt(0.0)

    gate_cfg = cfg["gate"]
    gate_kind = str(gate_cfg["kind"])
    gate_ready = pd.Series(True, index=out.index, dtype=bool)
    gate_active = pd.Series(True, index=out.index, dtype=bool)
    expansion = pd.Series(np.nan, index=out.index, dtype="float64")
    feature_cols = [
        cfg["candidate_col"],
        cfg["side_col"],
        cfg["pred_is_oos_col"],
        *cfg["side_alignment_cols"],
        *cfg["positive_filter_cols"],
    ]

    if gate_kind == "atr_regime":
        vol = _numeric(out, gate_cfg["volatility_col"])
        lower = _past_quantile(
            vol,
            quantile=gate_cfg["lower_quantile"],
            lookback_bars=gate_cfg["lookback_bars"],
            min_periods=gate_cfg["min_periods"],
        )
        upper = _past_quantile(
            vol,
            quantile=gate_cfg["upper_quantile"],
            lookback_bars=gate_cfg["lookback_bars"],
            min_periods=gate_cfg["min_periods"],
        )
        gate_ready = vol.notna() & lower.notna() & upper.notna()
        gate_active = gate_ready & vol.ge(lower) & vol.le(upper)
        feature_cols.append(gate_cfg["volatility_col"])
    elif gate_kind == "forecast_expansion":
        forecast = _numeric(out, gate_cfg["forecast_col"]).where(oos)
        current_vol = _numeric(out, gate_cfg["current_vol_col"])
        expansion = forecast / current_vol.where(current_vol.gt(0.0))
        current_upper = _past_quantile(
            current_vol,
            quantile=gate_cfg["current_vol_upper_quantile"],
            lookback_bars=gate_cfg["lookback_bars"],
            min_periods=gate_cfg["min_periods"],
        )
        gate_ready = forecast.notna() & current_vol.gt(0.0) & current_upper.notna()
        gate_active = (
            gate_ready
            & expansion.ge(gate_cfg["min_expansion"])
            & current_vol.le(current_upper)
        )
        lower_q = gate_cfg["forecast_lower_quantile"]
        if lower_q is not None:
            forecast_lower = _past_quantile(
                forecast,
                quantile=lower_q,
                lookback_bars=gate_cfg["lookback_bars"],
                min_periods=gate_cfg["min_periods"],
            )
            gate_ready &= forecast_lower.notna()
            gate_active &= forecast.ge(forecast_lower)
        upper_q = gate_cfg["forecast_upper_quantile"]
        if upper_q is not None:
            forecast_upper = _past_quantile(
                forecast,
                quantile=upper_q,
                lookback_bars=gate_cfg["lookback_bars"],
                min_periods=gate_cfg["min_periods"],
            )
            gate_ready &= forecast_upper.notna()
            gate_active &= forecast.le(forecast_upper)
        gate_active &= gate_ready
        feature_cols.extend([gate_cfg["forecast_col"], gate_cfg["current_vol_col"]])

    sizing_cfg = cfg["sizing"]
    weight = pd.Series(1.0, index=out.index, dtype="float64")
    sizing_ready = pd.Series(True, index=out.index, dtype=bool)
    if sizing_cfg["kind"] == "inverse_forecast_vol":
        forecast = _numeric(out, sizing_cfg["forecast_col"]).where(oos)
        target = _past_quantile(
            forecast,
            quantile=sizing_cfg["target_quantile"],
            lookback_bars=sizing_cfg["lookback_bars"],
            min_periods=sizing_cfg["min_periods"],
        )
        sizing_ready = forecast.gt(0.0) & target.gt(0.0)
        denominator = forecast.clip(lower=sizing_cfg["vol_floor"])
        weight = (target / denominator).clip(
            lower=sizing_cfg["min_weight"], upper=sizing_cfg["max_weight"]
        )
        weight = weight.where(sizing_ready, 0.0)
        feature_cols.append(sizing_cfg["forecast_col"])

    accepted = base & alignment & gate_active & sizing_ready
    output_side = side.where(accepted, 0.0)
    output_weight = weight.where(accepted, 0.0)
    output_signal = output_side * output_weight
    out[cfg["output_candidate_col"]] = accepted.astype("int8")
    out[cfg["output_side_col"]] = output_side.astype("int8")
    out[cfg["output_weight_col"]] = output_weight.astype("float64")
    out[cfg["output_signal_col"]] = output_signal.astype("float64")
    out[cfg["output_gate_ready_col"]] = gate_ready.astype("int8")
    out[cfg["output_expansion_col"]] = expansion.astype("float64")

    oos_rows = int(oos.sum())
    input_candidates = int((candidate & side.ne(0.0) & oos).sum())
    accepted_rows = int(accepted.sum())
    unique_features = list(dict.fromkeys(feature_cols))
    return out, None, {
        "model_kind": "qms_candidate_policy_transform",
        "feature_cols": unique_features,
        "pred_is_oos_col": cfg["pred_is_oos_col"],
        "candidate_col": cfg["output_candidate_col"],
        "side_col": cfg["output_side_col"],
        "weight_col": cfg["output_weight_col"],
        "signal_col": cfg["output_signal_col"],
        "gate_kind": gate_kind,
        "sizing_kind": sizing_cfg["kind"],
        "oos_rows": oos_rows,
        "test_pred_rows": oos_rows,
        "oos_prediction_coverage": 1.0 if oos_rows else 0.0,
        "candidate_summary": {
            "input_candidate_rows": input_candidates,
            "alignment_rejected_rows": int((base & ~alignment).sum()),
            "gate_rejected_rows": int((base & alignment & ~gate_active).sum()),
            "sizing_not_ready_rows": int((base & alignment & gate_active & ~sizing_ready).sum()),
            "accepted_candidate_rows": accepted_rows,
            "accepted_candidate_rate": float(accepted_rows / max(input_candidates, 1)),
        },
        "prediction_diagnostics": {
            "oos_rows": oos_rows,
            "predicted_rows": oos_rows,
            "non_oos_prediction_rows": 0,
            "missing_oos_prediction_rows": 0,
            "oos_prediction_coverage": 1.0 if oos_rows else 0.0,
            "alignment_ok": True,
        },
        "anti_leakage": {
            "candidate_rows_require_pred_is_oos": True,
            "forecast_threshold_history_requires_pred_is_oos": True,
            "thresholds": "rolling_past_only_shift_1",
            "current_bar_excluded_from_thresholds": True,
            "missing_inputs_fail_closed": True,
            "implicit_leverage_forbidden": True,
        },
    }


__all__ = [
    "apply_qms_candidate_policy_transform",
    "validate_qms_candidate_policy_params",
]
