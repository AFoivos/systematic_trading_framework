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
    add_derived: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``hilbert_transform`` feature transformation.

    This raw feature computes causal Hilbert endpoint amplitude, phase, and
    instantaneous frequency from a trailing price window. Derived cycle-period
    reciprocals, range flags, and amplitude-rising flags are intentionally not
    produced here; use feature helpers such as ``reciprocal``,
    ``between_flag``, and ``rising_flag`` for those columns.

    YAML declaration::

        features:
          - step: hilbert_transform
            params:
              price_col: close
              window: 64
              amplitude_col: hilbert_amplitude_64
              phase_col: hilbert_phase_64
              instantaneous_frequency_col: hilbert_instantaneous_frequency_64
              add_derived: false
            transforms:
              reciprocal:
                source_col: hilbert_instantaneous_frequency_64
                use_abs: true
                output_col: hilbert_dominant_cycle_64
              between_flag:
                source_col: hilbert_dominant_cycle_64
                lower: 10.0
                upper: 48.0
                output_col: hilbert_cycle_ok_64
              rising_flag:
                source_col: hilbert_amplitude_64
                periods: 3
                output_col: hilbert_amplitude_rising_64
            output_cols:
              - hilbert_amplitude_64
              - hilbert_phase_64
              - hilbert_instantaneous_frequency_64

    Required input columns
    ----------------------
    price_col:
        Price input column.

    Parameters
    ----------
    price_col:
        Price input column.
    window:
        Trailing window used for the Hilbert transform.
    amplitude_col:
        Output column for endpoint analytic-signal amplitude.
    phase_col:
        Output column for endpoint unwrapped phase.
    instantaneous_frequency_col:
        Output column for endpoint instantaneous frequency.
    dominant_cycle_col:
        Deprecated derived output. Use ``transforms.reciprocal`` on
        ``instantaneous_frequency_col`` with ``use_abs: true``.
    cycle_ok_col:
        Deprecated derived output. Use ``transforms.between_flag`` on the
        helper-produced dominant cycle column.
    amplitude_rising_col:
        Deprecated derived output. Use ``transforms.rising_flag`` on
        ``amplitude_col``.
    min_cycle:
        Deprecated helper parameter retained only for config validation.
    max_cycle:
        Deprecated helper parameter retained only for config validation.
    amplitude_slope_bars:
        Deprecated helper parameter retained only for config validation.
    add_derived:
        Deprecated switch. Must remain ``false``; derived outputs belong in
        helpers.
    """
    _validate_columns(df, [price_col])
    _validate_window(window)
    _validate_derived_params(
        min_cycle=min_cycle,
        max_cycle=max_cycle,
        amplitude_slope_bars=amplitude_slope_bars,
        add_derived=add_derived,
    )
    _reject_derived_outputs(
        add_derived=add_derived,
        dominant_cycle_col=dominant_cycle_col,
        cycle_ok_col=cycle_ok_col,
        amplitude_rising_col=amplitude_rising_col,
    )
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


def _reject_derived_outputs(
    *,
    add_derived: bool,
    dominant_cycle_col: str | None,
    cycle_ok_col: str | None,
    amplitude_rising_col: str | None,
) -> None:
    requested = {
        "add_derived": add_derived,
        "dominant_cycle_col": dominant_cycle_col,
        "cycle_ok_col": cycle_ok_col,
        "amplitude_rising_col": amplitude_rising_col,
    }
    enabled = [name for name, value in requested.items() if value not in (False, None)]
    if enabled:
        raise ValueError(
            "Hilbert derived outputs are no longer produced by hilbert_transform "
            f"({', '.join(enabled)} requested). Use transforms.reciprocal, "
            "transforms.between_flag, and transforms.rising_flag."
        )


__all__ = [
    "add_hilbert_transform",
]
