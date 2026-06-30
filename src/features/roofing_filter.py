from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd


def add_roofing_filter(
    df: pd.DataFrame,
    price_col: str = "close",
    high_pass_period: int = 48,
    low_pass_period: int = 10,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Apply the registered ``roofing_filter`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: roofing_filter
            params:
              price_col: close
              high_pass_period: 48
              low_pass_period: 10
              output_col: null
            output_cols:
              - configured by output_col
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    high_pass_period:
        Configuration parameter accepted by this feature. Default: ``48``.
    low_pass_period:
        Configuration parameter accepted by this feature. Default: ``10``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    """
    _validate_columns(df, [price_col])
    _validate_period(high_pass_period, name="high_pass_period")
    _validate_period(low_pass_period, name="low_pass_period")
    if high_pass_period <= low_pass_period:
        raise ValueError("high_pass_period must be greater than low_pass_period.")
    col = _resolve_output_col(output_col, f"roofing_filter_{high_pass_period}_{low_pass_period}")

    out = df.copy()
    price = out[price_col].astype(float).to_numpy()
    out[col] = _compute_roofing_filter(price, high_pass_period=high_pass_period, low_pass_period=low_pass_period)
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


def _resolve_output_col(output_col: str | None, default: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError("output_col must be a non-empty string.")
    return output_col

__all__ = [
    "add_roofing_filter",
]
