from __future__ import annotations

from numbers import Integral, Real

import numpy as np
import pandas as pd


EPSILON = 1e-12


def require_columns(df: pd.DataFrame, columns: list[str], *, feature: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for {feature}: {missing}")


def validate_int(value: int, *, name: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or int(value) < minimum:
        raise ValueError(f"{name} must be an integer greater than or equal to {minimum}.")
    return int(value)


def validate_float(value: float, *, name: str, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not np.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number.")
    resolved = float(value)
    if minimum is not None and resolved < minimum:
        raise ValueError(f"{name} must be greater than or equal to {minimum}.")
    if maximum is not None and resolved > maximum:
        raise ValueError(f"{name} must be less than or equal to {maximum}.")
    return resolved


def validate_bool(value: bool, *, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be boolean.")
    return value


def validate_mama_limits(fast_limit: float, slow_limit: float) -> tuple[float, float]:
    fast = validate_float(fast_limit, name="fast_limit", minimum=EPSILON, maximum=1.0)
    slow = validate_float(slow_limit, name="slow_limit", minimum=EPSILON, maximum=1.0)
    if slow > fast:
        raise ValueError("slow_limit must be less than or equal to fast_limit.")
    return fast, slow


def resolve_output_col(output_col: str | None, default: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError("output_col must be a non-empty string.")
    return output_col


def resolve_named_col(value: str | None, *, default: str, name: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
    return value


def ensure_unique_columns(columns: list[str], *, feature: str) -> None:
    if len(set(columns)) != len(columns):
        raise ValueError(f"{feature} output columns must be unique.")


def as_float_array(series: pd.Series) -> np.ndarray:
    return series.astype(float).to_numpy()


def compute_weighted_smooth(values: np.ndarray) -> np.ndarray:
    smooth = np.full(values.size, np.nan, dtype=float)
    for idx in range(values.size):
        if idx < 3:
            if np.isfinite(values[idx]):
                smooth[idx] = values[idx]
            continue
        sample = values[idx - 3 : idx + 1]
        if np.isfinite(sample).all():
            smooth[idx] = (4.0 * sample[3] + 3.0 * sample[2] + 2.0 * sample[1] + sample[0]) / 10.0
    return smooth


def _fir_hilbert(values: np.ndarray, idx: int, scale: float) -> float:
    if idx < 6:
        return 0.0
    sample = values[[idx, idx - 2, idx - 4, idx - 6]]
    if not np.isfinite(sample).all():
        return 0.0
    return (0.0962 * sample[0] + 0.5769 * sample[1] - 0.5769 * sample[2] - 0.0962 * sample[3]) * scale


def compute_mesa_components(
    values: np.ndarray,
    *,
    fast_limit: float = 0.5,
    slow_limit: float = 0.05,
) -> dict[str, np.ndarray]:
    """Compute causal MESA phase, period, MAMA, and FAMA components."""
    fast, slow = validate_mama_limits(fast_limit, slow_limit)
    size = values.size
    smooth = compute_weighted_smooth(values)
    detrender = np.zeros(size, dtype=float)
    q1 = np.zeros(size, dtype=float)
    i1 = np.zeros(size, dtype=float)
    ji = np.zeros(size, dtype=float)
    jq = np.zeros(size, dtype=float)
    i2 = np.zeros(size, dtype=float)
    q2 = np.zeros(size, dtype=float)
    re = np.zeros(size, dtype=float)
    im = np.zeros(size, dtype=float)

    period = np.full(size, np.nan, dtype=float)
    smooth_period = np.full(size, np.nan, dtype=float)
    phase = np.full(size, np.nan, dtype=float)
    delta_phase = np.full(size, np.nan, dtype=float)
    alpha = np.full(size, np.nan, dtype=float)
    mama = np.full(size, np.nan, dtype=float)
    fama = np.full(size, np.nan, dtype=float)

    previous_period = 10.0
    previous_smooth_period = 10.0
    previous_phase = 0.0
    previous_mama = np.nan
    previous_fama = np.nan

    for idx in range(size):
        price = values[idx]
        if not np.isfinite(price):
            continue
        if np.isnan(previous_mama):
            previous_mama = price
            previous_fama = price

        scale = 0.075 * previous_period + 0.54
        detrender[idx] = _fir_hilbert(smooth, idx, scale)
        q1[idx] = _fir_hilbert(detrender, idx, scale)
        i1[idx] = detrender[idx - 3] if idx >= 3 else 0.0
        ji[idx] = _fir_hilbert(i1, idx, scale)
        jq[idx] = _fir_hilbert(q1, idx, scale)

        raw_i2 = i1[idx] - jq[idx]
        raw_q2 = q1[idx] + ji[idx]
        i2[idx] = 0.2 * raw_i2 + 0.8 * (i2[idx - 1] if idx > 0 else 0.0)
        q2[idx] = 0.2 * raw_q2 + 0.8 * (q2[idx - 1] if idx > 0 else 0.0)

        raw_re = i2[idx] * (i2[idx - 1] if idx > 0 else 0.0) + q2[idx] * (q2[idx - 1] if idx > 0 else 0.0)
        raw_im = i2[idx] * (q2[idx - 1] if idx > 0 else 0.0) - q2[idx] * (i2[idx - 1] if idx > 0 else 0.0)
        re[idx] = 0.2 * raw_re + 0.8 * (re[idx - 1] if idx > 0 else 0.0)
        im[idx] = 0.2 * raw_im + 0.8 * (im[idx - 1] if idx > 0 else 0.0)

        current_period = previous_period
        angle = abs(np.arctan2(im[idx], re[idx])) if abs(re[idx]) > EPSILON or abs(im[idx]) > EPSILON else 0.0
        if angle > EPSILON:
            raw_period = 2.0 * np.pi / angle
            raw_period = min(raw_period, 1.5 * previous_period)
            raw_period = max(raw_period, 0.67 * previous_period)
            raw_period = min(max(raw_period, 6.0), 50.0)
            current_period = 0.2 * raw_period + 0.8 * previous_period

        current_smooth_period = 0.33 * current_period + 0.67 * previous_smooth_period
        current_phase = previous_phase
        if abs(i1[idx]) > EPSILON or abs(q1[idx]) > EPSILON:
            current_phase = float(np.degrees(np.arctan2(q1[idx], i1[idx])))
            if current_phase < 0.0:
                current_phase += 360.0

        current_delta_phase = previous_phase - current_phase
        if previous_phase < 90.0 and current_phase > 270.0:
            current_delta_phase = previous_phase + 360.0 - current_phase
        if current_delta_phase < 1.0:
            current_delta_phase = 1.0

        current_alpha = min(fast, max(slow, fast / current_delta_phase))
        current_mama = current_alpha * price + (1.0 - current_alpha) * previous_mama
        current_fama = 0.5 * current_alpha * current_mama + (1.0 - 0.5 * current_alpha) * previous_fama

        period[idx] = current_period
        smooth_period[idx] = current_smooth_period
        phase[idx] = current_phase
        delta_phase[idx] = current_delta_phase
        alpha[idx] = current_alpha
        mama[idx] = current_mama
        fama[idx] = current_fama

        previous_period = current_period
        previous_smooth_period = current_smooth_period
        previous_phase = current_phase
        previous_mama = current_mama
        previous_fama = current_fama

    return {
        "period": period,
        "smooth_period": smooth_period,
        "phase": phase,
        "delta_phase": delta_phase,
        "alpha": alpha,
        "mama": mama,
        "fama": fama,
    }


def compute_high_pass(values: np.ndarray, *, period: int) -> np.ndarray:
    period = validate_int(period, name="period", minimum=3)
    high_pass = np.full(values.size, np.nan, dtype=float)
    state = np.zeros(values.size, dtype=float)
    angle = 0.707 * 2.0 * np.pi / period
    alpha = (np.cos(angle) + np.sin(angle) - 1.0) / np.cos(angle)
    for idx in range(values.size):
        if not np.isfinite(values[idx]):
            continue
        if idx < 2:
            state[idx] = 0.0
            high_pass[idx] = 0.0
            continue
        sample = values[idx - 2 : idx + 1]
        if not np.isfinite(sample).all():
            continue
        state[idx] = (
            (1.0 - alpha / 2.0) ** 2 * (values[idx] - 2.0 * values[idx - 1] + values[idx - 2])
            + 2.0 * (1.0 - alpha) * state[idx - 1]
            - (1.0 - alpha) ** 2 * state[idx - 2]
        )
        high_pass[idx] = state[idx]
    return high_pass


def compute_decycler(values: np.ndarray, *, period: int) -> np.ndarray:
    high_pass = compute_high_pass(values, period=period)
    decycler = np.full(values.size, np.nan, dtype=float)
    valid = np.isfinite(values) & np.isfinite(high_pass)
    decycler[valid] = values[valid] - high_pass[valid]
    return decycler


def compute_supersmoother(values: np.ndarray, *, period: int) -> np.ndarray:
    period = validate_int(period, name="period", minimum=2)
    result = np.full(values.size, np.nan, dtype=float)
    if values.size == 0:
        return result
    a1 = np.exp(-np.sqrt(2.0) * np.pi / period)
    b1 = 2.0 * a1 * np.cos(np.sqrt(2.0) * np.pi / period)
    c2 = b1
    c3 = -(a1**2)
    c1 = 1.0 - c2 - c3
    state = np.zeros(values.size, dtype=float)
    if np.isfinite(values[0]):
        state[0] = values[0]
        result[0] = state[0]
    if values.size > 1 and np.isfinite(values[:2]).all():
        state[1] = (values[0] + values[1]) / 2.0
        result[1] = state[1]
    for idx in range(2, values.size):
        sample = values[idx - 1 : idx + 1]
        if not np.isfinite(sample).all():
            continue
        state[idx] = c1 * (values[idx] + values[idx - 1]) / 2.0 + c2 * state[idx - 1] + c3 * state[idx - 2]
        result[idx] = state[idx]
    return result


def rolling_min_max(values: np.ndarray, *, idx: int, window: int) -> tuple[float, float] | None:
    if idx + 1 < window:
        return None
    sample = values[idx - window + 1 : idx + 1]
    if not np.isfinite(sample).all():
        return None
    return float(np.min(sample)), float(np.max(sample))


def normalize_to_unit_interval(value: float, low: float, high: float) -> float:
    if abs(high - low) <= EPSILON:
        return 0.0
    return 2.0 * ((value - low) / (high - low) - 0.5)


__all__ = [
    "EPSILON",
    "as_float_array",
    "compute_decycler",
    "compute_high_pass",
    "compute_mesa_components",
    "compute_supersmoother",
    "compute_weighted_smooth",
    "ensure_unique_columns",
    "normalize_to_unit_interval",
    "require_columns",
    "resolve_named_col",
    "resolve_output_col",
    "rolling_min_max",
    "validate_bool",
    "validate_float",
    "validate_int",
    "validate_mama_limits",
]
