from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd
from scipy.signal import hilbert


def add_hilbert_transform(
    df: pd.DataFrame,
    price_col: str = "close",
    window: int = 64,
    amplitude_col: str | None = None,
    phase_col: str | None = None,
    instantaneous_frequency_col: str | None = None,
) -> pd.DataFrame:
    """Add rolling endpoint Hilbert transform features.

    This is a trailing-window FFT Hilbert approximation. It is causal because
    each row uses only the trailing window ending at that row, but endpoint
    phase/frequency estimates can have window-edge artifacts and should not be
    treated as full-sample analytic-signal values.
    """
    _validate_columns(df, [price_col])
    _validate_window(window)
    output_cols = _resolve_output_cols(
        amplitude_col or f"hilbert_amplitude_{window}",
        phase_col or f"hilbert_phase_{window}",
        instantaneous_frequency_col or f"hilbert_instantaneous_frequency_{window}",
    )

    out = df.copy()
    values = out[price_col].astype(float).to_numpy()
    amplitude = np.full(len(out), np.nan, dtype=float)
    phase = np.full(len(out), np.nan, dtype=float)
    frequency = np.full(len(out), np.nan, dtype=float)

    for idx in range(window - 1, len(out)):
        sample = values[idx - window + 1 : idx + 1]
        if not np.isfinite(sample).all():
            continue
        centered = sample - np.mean(sample)
        analytic = hilbert(centered)
        endpoint_phase = np.unwrap(np.angle(analytic))
        amplitude[idx] = float(np.abs(analytic[-1]))
        phase[idx] = float(endpoint_phase[-1])
        frequency[idx] = float((endpoint_phase[-1] - endpoint_phase[-2]) / (2.0 * np.pi))

    out[output_cols[0]] = amplitude
    out[output_cols[1]] = phase
    out[output_cols[2]] = frequency
    return out


def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for Hilbert transform: {missing}")


def _validate_window(window: int) -> None:
    if isinstance(window, bool) or not isinstance(window, Integral) or window < 4:
        raise ValueError("window must be an integer greater than or equal to 4.")


def _resolve_output_cols(*columns: str) -> tuple[str, str, str]:
    for column in columns:
        if not isinstance(column, str) or not column.strip():
            raise ValueError("Hilbert output columns must be non-empty strings.")
    if len(set(columns)) != len(columns):
        raise ValueError("Hilbert output columns must be unique.")
    return columns


__all__ = [
    "add_hilbert_transform",
]
