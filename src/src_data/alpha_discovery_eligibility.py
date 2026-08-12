from __future__ import annotations

"""Fail-closed bar eligibility for the frozen AR-0001 measurement contract.

The canonical V1 snapshot intentionally preserves incomplete provider bars and
timestamp gaps.  This module does not repair either condition.  It derives
point-in-time dependency masks on the original row timeline so feature and
target builders can invalidate any calculation that would cross one of them.
"""

from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd


EXPECTED_CADENCE: Final[pd.Timedelta] = pd.Timedelta(minutes=30)
REQUIRED_OBSERVED_MINUTES: Final[int] = 30


class AlphaDiscoveryEligibilityError(ValueError):
    """Raised when canonical bars cannot satisfy the frozen eligibility contract."""


@dataclass(frozen=True)
class BarEligibility:
    """Immutable masks derived without dropping or inserting timeline rows."""

    timestamps: pd.Series
    full_bar: np.ndarray
    exact_from_previous: np.ndarray
    gap_segment_id: np.ndarray

    def trailing_window(self, lookback_bars: int) -> np.ndarray:
        """Require ``t-lookback_bars .. t`` to be full and exactly contiguous."""

        resolved = _positive_integer(lookback_bars, field="lookback_bars")
        full = pd.Series(self.full_bar, dtype="int8")
        transitions = pd.Series(self.exact_from_previous, dtype="int8")
        full_ok = (
            full.rolling(resolved + 1, min_periods=resolved + 1).sum()
            == resolved + 1
        )
        transition_ok = (
            transitions.rolling(resolved, min_periods=resolved).sum() == resolved
        )
        return (full_ok & transition_ok).to_numpy(dtype=bool)

    def forward_window(self, forward_transitions: int) -> np.ndarray:
        """Require ``t .. t+forward_transitions`` to be full and contiguous."""

        resolved = _positive_integer(
            forward_transitions,
            field="forward_transitions",
        )
        full = pd.Series(self.full_bar, dtype="int8")
        next_transition = pd.Series(
            np.concatenate(
                [self.exact_from_previous[1:], np.asarray([False], dtype=bool)]
            ),
            dtype="int8",
        )
        full_ok = (
            full.iloc[::-1]
            .rolling(resolved + 1, min_periods=resolved + 1)
            .sum()
            .iloc[::-1]
            == resolved + 1
        )
        transition_ok = (
            next_transition.iloc[::-1]
            .rolling(resolved, min_periods=resolved)
            .sum()
            .iloc[::-1]
            == resolved
        )
        return (full_ok & transition_ok).to_numpy(dtype=bool)


def _positive_integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise AlphaDiscoveryEligibilityError(f"{field} must be a positive integer.")
    resolved = int(value)
    if resolved <= 0:
        raise AlphaDiscoveryEligibilityError(f"{field} must be a positive integer.")
    return resolved


def build_bar_eligibility(
    frame: pd.DataFrame,
    *,
    expected_cadence: pd.Timedelta = EXPECTED_CADENCE,
    required_observed_minutes: int = REQUIRED_OBSERVED_MINUTES,
) -> BarEligibility:
    """Derive strict FULL_30_OF_30 masks without mutating canonical data."""

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame.")
    required = {"timestamp", "observed_minute_count"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise AlphaDiscoveryEligibilityError(
            f"Eligibility input is missing canonical columns: {missing}."
        )
    cadence = pd.Timedelta(expected_cadence)
    if cadence != EXPECTED_CADENCE:
        raise AlphaDiscoveryEligibilityError(
            "AR-0001 eligibility requires the frozen 30-minute cadence."
        )
    observed_required = _positive_integer(
        required_observed_minutes,
        field="required_observed_minutes",
    )
    if observed_required != REQUIRED_OBSERVED_MINUTES:
        raise AlphaDiscoveryEligibilityError(
            "Canonical V1 requires FULL_30_OF_30_OBSERVED_MINUTES."
        )

    timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    if timestamps.isna().any():
        raise AlphaDiscoveryEligibilityError("Eligibility timestamps must be valid UTC.")
    if timestamps.duplicated().any() or not timestamps.is_monotonic_increasing:
        raise AlphaDiscoveryEligibilityError(
            "Eligibility timestamps must be unique and monotonically increasing."
        )
    observed = pd.to_numeric(frame["observed_minute_count"], errors="coerce")
    if observed.isna().any() or (~np.isfinite(observed.to_numpy(dtype=float))).any():
        raise AlphaDiscoveryEligibilityError(
            "observed_minute_count must be finite and non-missing."
        )
    if (observed % 1 != 0).any() or (~observed.between(1, 30)).any():
        raise AlphaDiscoveryEligibilityError(
            "observed_minute_count must contain integers in [1, 30]."
        )

    full_bar = observed.eq(observed_required).to_numpy(dtype=bool)
    exact_from_previous = timestamps.diff().eq(cadence).to_numpy(dtype=bool)
    if len(exact_from_previous):
        exact_from_previous[0] = False
    gap_start = ~exact_from_previous
    if len(gap_start):
        gap_start[0] = True
    gap_segment_id = np.cumsum(gap_start, dtype=np.int64) - 1
    return BarEligibility(
        timestamps=timestamps.reset_index(drop=True),
        full_bar=full_bar,
        exact_from_previous=exact_from_previous,
        gap_segment_id=gap_segment_id,
    )


__all__ = [
    "AlphaDiscoveryEligibilityError",
    "BarEligibility",
    "EXPECTED_CADENCE",
    "REQUIRED_OBSERVED_MINUTES",
    "build_bar_eligibility",
]
