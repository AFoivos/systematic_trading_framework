from __future__ import annotations

from collections.abc import Sequence
from numbers import Real

import numpy as np
import pandas as pd

from src.features.helpers.common import positive_int, require_columns
from src.features.systems.common import compute_gap_diagnostics, validate_bar_minutes


def add_efficiency_ratio_features(
    df: pd.DataFrame,
    *,
    source_col: str = "close",
    windows: Sequence[int] = (24, 48, 96),
    epsilon: float = 1e-12,
    bar_minutes: float = 1.0,
    inplace: bool = False,
) -> pd.DataFrame:
    """Add causal Kaufman-style efficiency ratios for arbitrary windows.

    For each window ``w``, the helper computes
    ``abs(x[t] - x[t-w]) / max(sum(abs(diff(x)), w), epsilon)`` and its
    signed counterpart, whose sign is ``sign(x[t] - x[t-w])``. The unsigned
    output range is ``[0, 1]`` and the signed output range is ``[-1, 1]``.

    Both outputs are NaN until ``w + 1`` contiguous observations are present.
    A timestamp gap resets that warmup, matching LMDS window invalidation.
    Only the current and past rows are used, so both outputs are strictly
    causal. A zero path length safely produces zero.

    YAML declaration::

        normalizations:
          efficiency_ratio:
            params:
              source_col: close
              windows: [24, 48, 96]
              epsilon: 1.0e-12
              bar_minutes: 1.0
    """
    require_columns(df, [source_col], owner="efficiency-ratio normalization")
    if isinstance(windows, (str, bytes)) or not isinstance(windows, Sequence) or not windows:
        raise ValueError("windows must be a non-empty sequence of positive integers.")
    resolved_windows = tuple(positive_int(window, field="windows entry") for window in windows)
    if len(set(resolved_windows)) != len(resolved_windows):
        raise ValueError("windows must not contain duplicates.")
    if isinstance(epsilon, bool) or not isinstance(epsilon, Real):
        raise ValueError("epsilon must be a finite number > 0.")
    resolved_epsilon = float(epsilon)
    if not np.isfinite(resolved_epsilon) or resolved_epsilon <= 0.0:
        raise ValueError("epsilon must be a finite number > 0.")

    resolved_bar_minutes = validate_bar_minutes(bar_minutes)
    gaps = compute_gap_diagnostics(df.index, expected_bar_minutes=resolved_bar_minutes)
    source = pd.to_numeric(df[source_col], errors="coerce").astype("float64")
    invalid = source.isna() & ~df[source_col].isna()
    if bool(invalid.any()) or bool(np.isinf(source.to_numpy(dtype=float)).any()):
        raise ValueError(f"{source_col} must contain only finite numeric values or NaN.")

    out = df if inplace else df.copy()
    absolute_step = source.diff().abs()
    for window in resolved_windows:
        change = source - source.shift(window)
        path_length = absolute_step.rolling(window, min_periods=window).sum()
        denominator = path_length.clip(lower=resolved_epsilon)
        efficiency = (change.abs() / denominator).clip(lower=0.0, upper=1.0)
        efficiency = efficiency.where(gaps.contiguous_bars >= window + 1)
        signed = (np.sign(change) * efficiency).clip(lower=-1.0, upper=1.0)
        out[f"efficiency_ratio_{window}"] = efficiency.astype("float64")
        out[f"signed_efficiency_ratio_{window}"] = signed.astype("float64")
    return out


__all__ = ["add_efficiency_ratio_features"]
