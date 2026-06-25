from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd


def add_roofing_filter(
    df: pd.DataFrame,
    price_col: str = "close",
    high_pass_period: int = 48,
    low_pass_period: int = 10,
    slope_bars: int = 3,
    output_col: str | None = None,
    slope_col: str | None = None,
    positive_col: str | None = None,
    negative_col: str | None = None,
    slope_positive_col: str | None = None,
    slope_negative_col: str | None = None,
    cross_up_zero_col: str | None = None,
    cross_down_zero_col: str | None = None,
    add_derived: bool = True,
) -> pd.DataFrame:
    """
    Add a causal Ehlers-style roofing filter.
    
    The implementation applies a two-pole high-pass filter followed by a
    SuperSmoother low-pass filter, using only current and prior samples.
    
    YAML declaration::
    
        features:
          - step: roofing_filter
            params: {}
    
    Required input columns
    ----------------------
    cross_down_zero_col:
        Required dataframe column read directly by this component.
    cross_up_zero_col:
        Required dataframe column read directly by this component.
    negative_col:
        Required dataframe column read directly by this component.
    positive_col:
        Required dataframe column read directly by this component.
    slope_col:
        Required dataframe column read directly by this component.
    slope_negative_col:
        Required dataframe column read directly by this component.
    slope_positive_col:
        Required dataframe column read directly by this component.
    price_col:
        Input column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column name consumed by the component. Default: ``close``.
    high_pass_period:
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``48``.
    low_pass_period:
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``10``.
    slope_bars:
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``3``.
    output_col:
        Output column name emitted by the component. Default: ``None``.
    slope_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    positive_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    negative_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    slope_positive_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    slope_negative_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    cross_up_zero_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    cross_down_zero_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    add_derived:
        Configuration value used by the registered component. Default: ``True``.
    """
    _validate_columns(df, [price_col])
    _validate_period(high_pass_period, name="high_pass_period")
    _validate_period(low_pass_period, name="low_pass_period")
    _validate_slope_bars(slope_bars)
    if not isinstance(add_derived, bool):
        raise ValueError("add_derived must be boolean.")
    if high_pass_period <= low_pass_period:
        raise ValueError("high_pass_period must be greater than low_pass_period.")
    col = _resolve_output_col(output_col, f"roofing_filter_{high_pass_period}_{low_pass_period}")
    derived_cols = _resolve_derived_cols(
        base_col=col,
        slope_col=slope_col,
        positive_col=positive_col,
        negative_col=negative_col,
        slope_positive_col=slope_positive_col,
        slope_negative_col=slope_negative_col,
        cross_up_zero_col=cross_up_zero_col,
        cross_down_zero_col=cross_down_zero_col,
    )

    out = df.copy()
    price = out[price_col].astype(float).to_numpy()
    out[col] = _compute_roofing_filter(price, high_pass_period=high_pass_period, low_pass_period=low_pass_period)
    if add_derived:
        roofing = out[col].astype(float)
        slope = roofing - roofing.shift(int(slope_bars))
        out[derived_cols["slope_col"]] = slope
        out[derived_cols["positive_col"]] = roofing.gt(0.0)
        out[derived_cols["negative_col"]] = roofing.lt(0.0)
        out[derived_cols["slope_positive_col"]] = slope.gt(0.0)
        out[derived_cols["slope_negative_col"]] = slope.lt(0.0)
        out[derived_cols["cross_up_zero_col"]] = roofing.shift(1).le(0.0) & roofing.gt(0.0)
        out[derived_cols["cross_down_zero_col"]] = roofing.shift(1).ge(0.0) & roofing.lt(0.0)
    return out


def _compute_roofing_filter(values: np.ndarray, *, high_pass_period: int, low_pass_period: int) -> np.ndarray:
    filt = np.full(values.size, np.nan, dtype=float)
    angle_hp = 0.707 * 2.0 * np.pi / high_pass_period
    alpha = (np.cos(angle_hp) + np.sin(angle_hp) - 1.0) / np.cos(angle_hp)
    a1 = np.exp(-np.sqrt(2.0) * np.pi / low_pass_period)
    b1 = 2.0 * a1 * np.cos(np.sqrt(2.0) * np.pi / low_pass_period)
    c2 = b1
    c3 = -(a1**2)
    c1 = 1.0 - c2 - c3

    hp_state = np.zeros(values.size, dtype=float)
    filt_state = np.zeros(values.size, dtype=float)
    for idx in range(2, values.size):
        sample = values[idx - 2 : idx + 1]
        if not np.isfinite(sample).all():
            continue
        hp_state[idx] = (
            (1.0 - alpha / 2.0) ** 2 * (values[idx] - 2.0 * values[idx - 1] + values[idx - 2])
            + 2.0 * (1.0 - alpha) * hp_state[idx - 1]
            - (1.0 - alpha) ** 2 * hp_state[idx - 2]
        )
        filt_state[idx] = c1 * (hp_state[idx] + hp_state[idx - 1]) / 2.0 + c2 * filt_state[idx - 1] + c3 * filt_state[idx - 2]
        filt[idx] = filt_state[idx]
    return filt


def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for roofing filter: {missing}")


def _validate_period(period: int, *, name: str) -> None:
    if isinstance(period, bool) or not isinstance(period, Integral) or period <= 1:
        raise ValueError(f"{name} must be an integer greater than 1.")


def _validate_slope_bars(slope_bars: int) -> None:
    if isinstance(slope_bars, bool) or not isinstance(slope_bars, Integral) or int(slope_bars) <= 0:
        raise ValueError("slope_bars must be a positive integer.")


def _resolve_output_col(output_col: str | None, default: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError("output_col must be a non-empty string.")
    return output_col


def _resolve_derived_cols(
    *,
    base_col: str,
    slope_col: str | None,
    positive_col: str | None,
    negative_col: str | None,
    slope_positive_col: str | None,
    slope_negative_col: str | None,
    cross_up_zero_col: str | None,
    cross_down_zero_col: str | None,
) -> dict[str, str]:
    exact_defaults = base_col == "roofing_filter"
    defaults = {
        "slope_col": "roofing_slope" if exact_defaults else f"{base_col}_slope",
        "positive_col": "roofing_positive" if exact_defaults else f"{base_col}_positive",
        "negative_col": "roofing_negative" if exact_defaults else f"{base_col}_negative",
        "slope_positive_col": "roofing_slope_positive" if exact_defaults else f"{base_col}_slope_positive",
        "slope_negative_col": "roofing_slope_negative" if exact_defaults else f"{base_col}_slope_negative",
        "cross_up_zero_col": "roofing_cross_up_zero" if exact_defaults else f"{base_col}_cross_up_zero",
        "cross_down_zero_col": "roofing_cross_down_zero" if exact_defaults else f"{base_col}_cross_down_zero",
    }
    resolved = {
        "slope_col": _resolve_output_col(slope_col, defaults["slope_col"]),
        "positive_col": _resolve_output_col(positive_col, defaults["positive_col"]),
        "negative_col": _resolve_output_col(negative_col, defaults["negative_col"]),
        "slope_positive_col": _resolve_output_col(slope_positive_col, defaults["slope_positive_col"]),
        "slope_negative_col": _resolve_output_col(slope_negative_col, defaults["slope_negative_col"]),
        "cross_up_zero_col": _resolve_output_col(cross_up_zero_col, defaults["cross_up_zero_col"]),
        "cross_down_zero_col": _resolve_output_col(cross_down_zero_col, defaults["cross_down_zero_col"]),
    }
    if base_col in set(resolved.values()) or len(set(resolved.values())) != len(resolved):
        raise ValueError("Roofing derived output columns must be unique and distinct from output_col.")
    return resolved


__all__ = [
    "add_roofing_filter",
]
