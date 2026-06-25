from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd

try:
    from scipy.signal import hilbert as _scipy_hilbert
except ModuleNotFoundError:  # pragma: no cover - exercised only when SciPy is absent.
    _scipy_hilbert = None


def add_hilbert_transform(
    df: pd.DataFrame,
    price_col: str = "close",
    window: int = 64,
    amplitude_col: str | None = None,
    phase_col: str | None = None,
    instantaneous_frequency_col: str | None = None,
    dominant_cycle_col: str | None = None,
    cycle_ok_col: str | None = None,
    amplitude_rising_col: str | None = None,
    min_cycle: int = 10,
    max_cycle: int = 48,
    amplitude_slope_bars: int = 3,
    add_derived: bool = True,
) -> pd.DataFrame:
    """
    Add rolling endpoint Hilbert transform features.
    
    This is a trailing-window FFT Hilbert approximation. It is causal because
    each row uses only the trailing window ending at that row, but endpoint
    phase/frequency estimates can have window-edge artifacts and should not be
    treated as full-sample analytic-signal values.
    
    YAML declaration::
    
        features:
          - step: hilbert_transform
            params: {}
    
    Required input columns
    ----------------------
    price_col:
        Input column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column name consumed by the component. Default: ``close``.
    window:
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``64``.
    amplitude_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    phase_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    instantaneous_frequency_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    dominant_cycle_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    cycle_ok_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    amplitude_rising_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    min_cycle:
        Configuration value used by the registered component. Default: ``10``.
    max_cycle:
        Configuration value used by the registered component. Default: ``48``.
    amplitude_slope_bars:
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``3``.
    add_derived:
        Configuration value used by the registered component. Default: ``True``.
    """
    _validate_columns(df, [price_col])
    _validate_window(window)
    _validate_derived_params(
        min_cycle=min_cycle,
        max_cycle=max_cycle,
        amplitude_slope_bars=amplitude_slope_bars,
        add_derived=add_derived,
    )
    output_cols = _resolve_output_cols(
        amplitude_col or f"hilbert_amplitude_{window}",
        phase_col or f"hilbert_phase_{window}",
        instantaneous_frequency_col or f"hilbert_instantaneous_frequency_{window}",
    )
    derived_cols = _resolve_derived_output_cols(
        window=window,
        amplitude_col=output_cols[0],
        dominant_cycle_col=dominant_cycle_col,
        cycle_ok_col=cycle_ok_col,
        amplitude_rising_col=amplitude_rising_col,
    )

    out = df.copy()
    values = out[price_col].astype(float).to_numpy()
    amplitude = np.full(len(out), np.nan, dtype=float)
    phase = np.full(len(out), np.nan, dtype=float)
    frequency = np.full(len(out), np.nan, dtype=float)
    if _scipy_hilbert is None:
        raise ImportError("scipy is required for add_hilbert_transform. Install scipy to use the hilbert_transform feature.")

    for idx in range(window - 1, len(out)):
        sample = values[idx - window + 1 : idx + 1]
        if not np.isfinite(sample).all():
            continue
        centered = sample - np.mean(sample)
        analytic = _scipy_hilbert(centered)
        endpoint_phase = np.unwrap(np.angle(analytic))
        amplitude[idx] = float(np.abs(analytic[-1]))
        phase[idx] = float(endpoint_phase[-1])
        frequency[idx] = float((endpoint_phase[-1] - endpoint_phase[-2]) / (2.0 * np.pi))

    out[output_cols[0]] = amplitude
    out[output_cols[1]] = phase
    out[output_cols[2]] = frequency
    if add_derived:
        dominant_cycle = np.full(len(out), np.nan, dtype=float)
        valid_frequency = np.isfinite(frequency) & (np.abs(frequency) > 1e-12)
        dominant_cycle[valid_frequency] = 1.0 / np.abs(frequency[valid_frequency])
        out[derived_cols[0]] = dominant_cycle
        out[derived_cols[1]] = (
            pd.Series(dominant_cycle, index=out.index)
            .between(float(min_cycle), float(max_cycle), inclusive="both")
        )
        amplitude_series = pd.Series(amplitude, index=out.index)
        out[derived_cols[2]] = amplitude_series.gt(amplitude_series.shift(int(amplitude_slope_bars)))
    return out


def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for Hilbert transform: {missing}")


def _validate_window(window: int) -> None:
    if isinstance(window, bool) or not isinstance(window, Integral) or window < 4:
        raise ValueError("window must be an integer greater than or equal to 4.")


def _validate_derived_params(
    *,
    min_cycle: int,
    max_cycle: int,
    amplitude_slope_bars: int,
    add_derived: bool,
) -> None:
    if not isinstance(add_derived, bool):
        raise ValueError("add_derived must be boolean.")
    for name, value in (
        ("min_cycle", min_cycle),
        ("max_cycle", max_cycle),
        ("amplitude_slope_bars", amplitude_slope_bars),
    ):
        if isinstance(value, bool) or not isinstance(value, Integral) or int(value) <= 0:
            raise ValueError(f"{name} must be a positive integer.")
    if int(min_cycle) > int(max_cycle):
        raise ValueError("min_cycle must be <= max_cycle.")


def _resolve_output_cols(*columns: str) -> tuple[str, str, str]:
    for column in columns:
        if not isinstance(column, str) or not column.strip():
            raise ValueError("Hilbert output columns must be non-empty strings.")
    if len(set(columns)) != len(columns):
        raise ValueError("Hilbert output columns must be unique.")
    return columns


def _resolve_derived_output_cols(
    *,
    window: int,
    amplitude_col: str,
    dominant_cycle_col: str | None,
    cycle_ok_col: str | None,
    amplitude_rising_col: str | None,
) -> tuple[str, str, str]:
    exact_defaults = amplitude_col == "hilbert_amplitude"
    columns = (
        dominant_cycle_col or ("hilbert_dominant_cycle" if exact_defaults else f"hilbert_dominant_cycle_{window}"),
        cycle_ok_col or ("hilbert_cycle_ok" if exact_defaults else f"hilbert_cycle_ok_{window}"),
        amplitude_rising_col
        or ("hilbert_amplitude_rising" if exact_defaults else f"hilbert_amplitude_rising_{window}"),
    )
    for column in columns:
        if not isinstance(column, str) or not column.strip():
            raise ValueError("Hilbert derived output columns must be non-empty strings.")
    if amplitude_col in set(columns) or len(set(columns)) != len(columns):
        raise ValueError("Hilbert derived output columns must be unique and distinct from amplitude_col.")
    return columns


__all__ = [
    "add_hilbert_transform",
]
