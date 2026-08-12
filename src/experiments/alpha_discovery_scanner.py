from __future__ import annotations

"""Frozen-state conditional scanner for AR-0001.

This module measures preregistered conditional effects.  It does not optimize
thresholds, signals, stops, take-profits, or model parameters.
"""

from dataclasses import dataclass
from hashlib import sha256
import itertools
import json
import re
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from src.experiments.alpha_discovery_statistics import (
    AlphaDiscoveryStatisticsError,
    adjust_pvalues,
    newey_west_conditional_mean_summary,
    segmented_moving_block_bootstrap_summary,
    stable_hypothesis_seed,
)
from src.experiments.alpha_discovery_targets import (
    ALPHA_DISCOVERY_HORIZONS,
    target_eligibility_column,
)
from src.features.alpha_discovery_primitives import (
    CONTINUOUS_FEATURE_COLUMNS,
    GAP_SEGMENT_COLUMN,
    PATH_EFFICIENCY_WINDOWS,
    PRIMITIVE_FEATURE_COLUMNS,
    REALIZED_VOLATILITY_WINDOWS,
    feature_eligibility_column,
    primitive_feature_family,
)

QUINTILE_PROBABILITIES = (0.2, 0.4, 0.6, 0.8)
QUINTILE_LABELS = ("Q1", "Q2", "Q3", "Q4", "Q5")
MULTIPLE_TESTING_FAMILY_COLUMNS = (
    "feature_family",
    "horizon",
    "target",
    "direction",
    "preregistered_interaction",
)
PREREGISTERED_CONDITION_COUNT = 316
PREREGISTERED_EFFECT_COUNT = (
    PREREGISTERED_CONDITION_COUNT * len(ALPHA_DISCOVERY_HORIZONS) * 2
)


class AlphaDiscoveryScannerError(ValueError):
    """Raised when scanner inputs violate the preregistered family."""


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        dict(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FrozenBinEdges:
    schema_version: int
    snapshot_id: str
    specification_hash: str
    fitted_start: str
    fitted_end: str
    probabilities: tuple[float, ...]
    edges: dict[str, tuple[float, ...]]
    finite_counts: dict[str, int]
    edge_hash: str

    def _hash_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "specification_hash": self.specification_hash,
            "fitted_start": self.fitted_start,
            "fitted_end": self.fitted_end,
            "probabilities": list(self.probabilities),
            "edges": {key: list(value) for key, value in sorted(self.edges.items())},
            "finite_counts": dict(sorted(self.finite_counts.items())),
        }

    def validate(self) -> None:
        if self.schema_version != 1:
            raise AlphaDiscoveryScannerError("Frozen bin schema_version must be 1.")
        if not self.snapshot_id:
            raise AlphaDiscoveryScannerError("Frozen bins require a snapshot_id.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.specification_hash):
            raise AlphaDiscoveryScannerError(
                "Frozen bins require a lowercase specification SHA-256."
            )
        if tuple(self.probabilities) != QUINTILE_PROBABILITIES:
            raise AlphaDiscoveryScannerError(
                "Frozen bins must use the preregistered quintile probabilities."
            )
        if set(self.edges) != set(CONTINUOUS_FEATURE_COLUMNS):
            raise AlphaDiscoveryScannerError(
                "Frozen bins must contain exactly the approved continuous features."
            )
        if set(self.finite_counts) != set(CONTINUOUS_FEATURE_COLUMNS):
            raise AlphaDiscoveryScannerError(
                "Frozen bin finite counts must match the approved continuous features."
            )
        for feature, cuts in self.edges.items():
            if len(cuts) != 4 or not np.isfinite(np.asarray(cuts, dtype=float)).all():
                raise AlphaDiscoveryScannerError(
                    f"{feature} must have four finite internal quintile edges."
                )
            if not np.all(np.diff(np.asarray(cuts, dtype=float)) > 0.0):
                raise AlphaDiscoveryScannerError(
                    f"{feature} quintile edges must be strictly increasing."
                )
            if self.finite_counts[feature] < 5:
                raise AlphaDiscoveryScannerError(
                    f"{feature} needs at least five finite discovery observations."
                )
        if _canonical_hash(self._hash_payload()) != self.edge_hash:
            raise AlphaDiscoveryScannerError("Frozen bin edge_hash mismatch.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {**self._hash_payload(), "edge_hash": self.edge_hash}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> FrozenBinEdges:
        required = {
            "schema_version",
            "snapshot_id",
            "specification_hash",
            "fitted_start",
            "fitted_end",
            "probabilities",
            "edges",
            "finite_counts",
            "edge_hash",
        }
        missing = sorted(required.difference(payload))
        unexpected = sorted(set(payload).difference(required))
        if missing or unexpected:
            raise AlphaDiscoveryScannerError(
                f"Frozen bin schema mismatch; missing={missing}, unexpected={unexpected}."
            )
        instance = cls(
            schema_version=int(payload["schema_version"]),
            snapshot_id=str(payload["snapshot_id"]),
            specification_hash=str(payload["specification_hash"]),
            fitted_start=str(payload["fitted_start"]),
            fitted_end=str(payload["fitted_end"]),
            probabilities=tuple(float(value) for value in payload["probabilities"]),
            edges={
                str(feature): tuple(float(value) for value in values)
                for feature, values in dict(payload["edges"]).items()
            },
            finite_counts={
                str(feature): int(value)
                for feature, value in dict(payload["finite_counts"]).items()
            },
            edge_hash=str(payload["edge_hash"]),
        )
        instance.validate()
        return instance


def fit_discovery_quintiles(
    features: pd.DataFrame,
    *,
    snapshot_id: str,
    specification_hash: str,
) -> FrozenBinEdges:
    """Fit quintile edges once on discovery data and bind them to its snapshot."""

    missing = sorted(
        {"timestamp", *CONTINUOUS_FEATURE_COLUMNS}.difference(features.columns)
    )
    if missing:
        raise AlphaDiscoveryScannerError(f"Missing bin-fit features: {missing}.")
    timestamps = pd.to_datetime(features["timestamp"], utc=True, errors="coerce")
    if timestamps.isna().any() or timestamps.duplicated().any():
        raise AlphaDiscoveryScannerError("Bin-fit timestamps must be valid and unique.")
    if not timestamps.is_monotonic_increasing:
        raise AlphaDiscoveryScannerError("Bin-fit timestamps must be sorted.")
    edges: dict[str, tuple[float, ...]] = {}
    finite_counts: dict[str, int] = {}
    for feature in CONTINUOUS_FEATURE_COLUMNS:
        values = pd.to_numeric(features[feature], errors="coerce").to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        if len(finite) < 5:
            raise AlphaDiscoveryScannerError(
                f"{feature} has fewer than five finite discovery observations."
            )
        cuts = np.quantile(finite, QUINTILE_PROBABILITIES, method="linear")
        if not np.all(np.diff(cuts) > 0.0):
            raise AlphaDiscoveryScannerError(
                f"{feature} cannot form five distinct discovery quintiles."
            )
        edges[feature] = tuple(float(value) for value in cuts)
        finite_counts[feature] = int(len(finite))
    payload = {
        "schema_version": 1,
        "snapshot_id": str(snapshot_id),
        "specification_hash": str(specification_hash),
        "fitted_start": timestamps.iloc[0].isoformat(),
        "fitted_end": timestamps.iloc[-1].isoformat(),
        "probabilities": list(QUINTILE_PROBABILITIES),
        "edges": {key: list(value) for key, value in sorted(edges.items())},
        "finite_counts": dict(sorted(finite_counts.items())),
    }
    frozen = FrozenBinEdges(
        schema_version=1,
        snapshot_id=str(snapshot_id),
        specification_hash=str(specification_hash),
        fitted_start=timestamps.iloc[0].isoformat(),
        fitted_end=timestamps.iloc[-1].isoformat(),
        probabilities=QUINTILE_PROBABILITIES,
        edges=edges,
        finite_counts=finite_counts,
        edge_hash=_canonical_hash(payload),
    )
    frozen.validate()
    return frozen


def apply_frozen_states(
    features: pd.DataFrame,
    frozen: FrozenBinEdges,
) -> pd.DataFrame:
    """Apply existing edges; this function has no fitting path by construction."""

    frozen.validate()
    missing = sorted(
        {"timestamp", *PRIMITIVE_FEATURE_COLUMNS}.difference(features.columns)
    )
    if missing:
        raise AlphaDiscoveryScannerError(f"Missing state features: {missing}.")
    timestamps = pd.to_datetime(features["timestamp"], utc=True, errors="raise")
    if timestamps.duplicated().any() or not timestamps.is_monotonic_increasing:
        raise AlphaDiscoveryScannerError(
            "State timestamps must be unique and monotonically increasing."
        )
    states = pd.DataFrame({"timestamp": timestamps})
    for feature in CONTINUOUS_FEATURE_COLUMNS:
        values = pd.to_numeric(features[feature], errors="coerce").to_numpy(dtype=float)
        cuts = np.asarray(frozen.edges[feature], dtype=float)
        labels = np.full(len(values), None, dtype=object)
        finite = np.isfinite(values)
        bin_numbers = np.searchsorted(cuts, values[finite], side="left")
        labels[finite] = np.asarray(QUINTILE_LABELS, dtype=object)[bin_numbers]
        states[f"{feature}_state"] = labels

    utc_hour = pd.to_numeric(features["utc_hour"], errors="coerce")
    weekday = pd.to_numeric(features["weekday"], errors="coerce")
    finite_hour = utc_hour.notna()
    finite_weekday = weekday.notna()
    if (
        (utc_hour[finite_hour] % 1 != 0).any()
        or (~utc_hour[finite_hour].between(0, 23)).any()
    ):
        raise AlphaDiscoveryScannerError("utc_hour states must be integers in [0, 23].")
    if (
        (weekday[finite_weekday] % 1 != 0).any()
        or (~weekday[finite_weekday].between(0, 6)).any()
    ):
        raise AlphaDiscoveryScannerError("weekday states must be integers in [0, 6].")
    hour_labels = np.full(len(utc_hour), None, dtype=object)
    weekday_labels = np.full(len(weekday), None, dtype=object)
    hour_values = utc_hour.to_numpy(dtype=float, na_value=np.nan)
    weekday_values = weekday.to_numpy(dtype=float, na_value=np.nan)
    hour_labels[finite_hour.to_numpy(dtype=bool)] = [
        f"H{int(value):02d}" for value in hour_values[np.isfinite(hour_values)]
    ]
    weekday_labels[finite_weekday.to_numpy(dtype=bool)] = [
        f"D{int(value)}" for value in weekday_values[np.isfinite(weekday_values)]
    ]
    states["utc_hour_state"] = hour_labels
    states["weekday_state"] = weekday_labels
    return states


def preregistered_interaction_pairs() -> tuple[tuple[str, str], ...]:
    return tuple(
        itertools.product(
            tuple(f"path_efficiency_{window}" for window in PATH_EFFICIENCY_WINDOWS),
            tuple(
                f"realized_volatility_{window}"
                for window in REALIZED_VOLATILITY_WINDOWS
            ),
        )
    )


@dataclass(frozen=True)
class ChronologicalPeriod:
    name: str
    start_inclusive: str
    end_exclusive: str

    def bounds(self) -> tuple[pd.Timestamp, pd.Timestamp]:
        start = pd.Timestamp(self.start_inclusive)
        end = pd.Timestamp(self.end_exclusive)
        if start.tzinfo is None or end.tzinfo is None:
            raise AlphaDiscoveryScannerError(
                f"Chronological period {self.name!r} must use timezone-aware bounds."
            )
        start = start.tz_convert("UTC")
        end = end.tz_convert("UTC")
        if start >= end:
            raise AlphaDiscoveryScannerError(
                f"Chronological period {self.name!r} has invalid bounds."
            )
        return start, end


DEFAULT_STABILITY_PERIODS = (
    ChronologicalPeriod("Y2020", "2020-01-01T00:00:00Z", "2021-01-01T00:00:00Z"),
    ChronologicalPeriod("Y2021", "2021-01-01T00:00:00Z", "2022-01-01T00:00:00Z"),
    ChronologicalPeriod("Y2022", "2022-01-01T00:00:00Z", "2023-01-01T00:00:00Z"),
    ChronologicalPeriod("Y2023", "2023-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
    ChronologicalPeriod("Y2024", "2024-01-01T00:00:00Z", "2025-01-01T00:00:00Z"),
    ChronologicalPeriod("Y2025H1", "2025-01-01T00:00:00Z", "2025-07-01T00:00:00Z"),
)


@dataclass(frozen=True)
class ScannerSettings:
    primary_block_length_bars: int = 48
    sensitivity_block_lengths_bars: tuple[int, ...] = (96, 192)
    bootstrap_resamples: int = 2_000
    confidence_level: float = 0.95
    minimum_valid_resample_fraction: float = 0.99
    seed: int = 7
    minimum_observations: int = 200
    minimum_coverage_fraction: float = 0.50
    minimum_occupied_primary_blocks: int = 20
    hac_estimator: str = "CONDITIONAL_MEAN_RATIO"
    hac_kernel: str = "BARTLETT"
    hac_primary_lag_bars: int = 48
    hac_sensitivity_lags_bars: tuple[int, ...] = (96, 192)
    stability_periods: tuple[ChronologicalPeriod, ...] = DEFAULT_STABILITY_PERIODS
    minimum_period_observations: int = 30
    required_stability_periods: int = 6
    global_family_size: int = PREREGISTERED_EFFECT_COUNT
    global_fdr_alpha: float = 0.05
    local_fdr_alpha: float = 0.05

    @classmethod
    def from_config(
        cls,
        statistics_payload: Mapping[str, Any],
        multiple_testing_payload: Mapping[str, Any],
    ) -> ScannerSettings:
        """Resolve only already-validated, explicitly frozen settings."""

        bootstrap = statistics_payload["block_bootstrap"]
        hac = statistics_payload["hac"]
        chronological = statistics_payload["chronological_stability"]
        periods = tuple(
            ChronologicalPeriod(
                name=str(period["name"]),
                start_inclusive=str(period["start_inclusive"]),
                end_exclusive=str(period["end_exclusive"]),
            )
            for period in chronological["periods"]
        )
        settings = cls(
            primary_block_length_bars=int(bootstrap["primary_block_length_bars"]),
            sensitivity_block_lengths_bars=tuple(
                int(value) for value in bootstrap["sensitivity_block_lengths_bars"]
            ),
            bootstrap_resamples=int(bootstrap["resamples"]),
            confidence_level=float(bootstrap["confidence_level"]),
            minimum_valid_resample_fraction=float(
                bootstrap["minimum_valid_resample_fraction"]
            ),
            seed=int(bootstrap["seed"]),
            minimum_observations=int(statistics_payload["minimum_observations"]),
            minimum_coverage_fraction=float(
                statistics_payload["minimum_coverage_fraction"]
            ),
            minimum_occupied_primary_blocks=int(
                statistics_payload["minimum_occupied_primary_blocks"]
            ),
            hac_estimator=str(hac["estimator"]),
            hac_kernel=str(hac["kernel"]),
            hac_primary_lag_bars=int(hac["primary_lag_bars"]),
            hac_sensitivity_lags_bars=tuple(
                int(value) for value in hac["sensitivity_lags_bars"]
            ),
            stability_periods=periods,
            minimum_period_observations=int(
                chronological["minimum_observations_per_period"]
            ),
            required_stability_periods=int(chronological["required_periods"]),
            global_family_size=int(multiple_testing_payload["global_family_size"]),
            global_fdr_alpha=float(multiple_testing_payload["primary_fdr_alpha"]),
            local_fdr_alpha=float(multiple_testing_payload["local_fdr_alpha"]),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        integer_fields = (
            "primary_block_length_bars",
            "bootstrap_resamples",
            "minimum_observations",
            "minimum_occupied_primary_blocks",
            "hac_primary_lag_bars",
            "minimum_period_observations",
            "required_stability_periods",
            "global_family_size",
        )
        for name in integer_fields:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise AlphaDiscoveryScannerError(f"{name} must be a positive integer.")
        for name, values in (
            ("sensitivity_block_lengths_bars", self.sensitivity_block_lengths_bars),
            ("hac_sensitivity_lags_bars", self.hac_sensitivity_lags_bars),
        ):
            if not values or any(
                isinstance(value, bool) or not isinstance(value, int) or value <= 0
                for value in values
            ):
                raise AlphaDiscoveryScannerError(
                    f"{name} must contain positive integers."
                )
            if len(set(values)) != len(values):
                raise AlphaDiscoveryScannerError(f"{name} cannot contain duplicates.")
        if self.primary_block_length_bars in self.sensitivity_block_lengths_bars:
            raise AlphaDiscoveryScannerError(
                "Primary bootstrap block length cannot repeat as a sensitivity."
            )
        if self.hac_primary_lag_bars in self.hac_sensitivity_lags_bars:
            raise AlphaDiscoveryScannerError(
                "Primary HAC lag cannot repeat as a sensitivity."
            )
        if self.hac_estimator != "CONDITIONAL_MEAN_RATIO":
            raise AlphaDiscoveryScannerError(
                "HAC estimator must be CONDITIONAL_MEAN_RATIO."
            )
        if self.hac_kernel != "BARTLETT":
            raise AlphaDiscoveryScannerError("HAC kernel must be BARTLETT.")
        for name in (
            "minimum_valid_resample_fraction",
            "minimum_coverage_fraction",
            "global_fdr_alpha",
            "local_fdr_alpha",
        ):
            value = float(getattr(self, name))
            if not 0.0 < value <= 1.0:
                raise AlphaDiscoveryScannerError(f"{name} must lie in (0, 1].")
        if not 0.0 < float(self.confidence_level) < 1.0:
            raise AlphaDiscoveryScannerError(
                "confidence_level must lie strictly in (0, 1)."
            )
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise AlphaDiscoveryScannerError("seed must be an integer.")
        if self.global_family_size != PREREGISTERED_EFFECT_COUNT:
            raise AlphaDiscoveryScannerError(
                f"Global family size must remain {PREREGISTERED_EFFECT_COUNT}."
            )
        if self.required_stability_periods != len(self.stability_periods):
            raise AlphaDiscoveryScannerError(
                "Every frozen stability period must be required."
            )
        previous_end: pd.Timestamp | None = None
        names: set[str] = set()
        for period in self.stability_periods:
            if not period.name or period.name in names:
                raise AlphaDiscoveryScannerError(
                    "Stability-period names must be non-empty and unique."
                )
            names.add(period.name)
            start, end = period.bounds()
            if previous_end is not None and start != previous_end:
                raise AlphaDiscoveryScannerError(
                    "Frozen stability periods must be adjacent and chronological."
                )
            previous_end = end


@dataclass(frozen=True)
class ConditionalScanResult:
    effects: pd.DataFrame
    temporal_stability: pd.DataFrame
    inference_sensitivities: pd.DataFrame
    frozen_bins: FrozenBinEdges


def _condition_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for feature in PRIMITIVE_FEATURE_COLUMNS:
        states = (
            QUINTILE_LABELS
            if feature in CONTINUOUS_FEATURE_COLUMNS
            else (
                tuple(f"H{hour:02d}" for hour in range(24))
                if feature == "utc_hour"
                else tuple(f"D{day}" for day in range(7))
            )
        )
        for state in states:
            specs.append(
                {
                    "dimension": 1,
                    "feature_family": primitive_feature_family(feature),
                    "feature_columns": feature,
                    "preregistered_interaction": "ONE_DIMENSIONAL",
                    "state": f"{feature}={state}",
                    "requirements": ((f"{feature}_state", state),),
                    "eligibility_columns": (feature_eligibility_column(feature),),
                }
            )
    for path_feature, volatility_feature in preregistered_interaction_pairs():
        interaction = f"{path_feature}_x_{volatility_feature}"
        for path_state, volatility_state in itertools.product(
            QUINTILE_LABELS, QUINTILE_LABELS
        ):
            specs.append(
                {
                    "dimension": 2,
                    "feature_family": "path_efficiency_x_realized_volatility",
                    "feature_columns": f"{path_feature}|{volatility_feature}",
                    "preregistered_interaction": interaction,
                    "state": (
                        f"{path_feature}={path_state}|"
                        f"{volatility_feature}={volatility_state}"
                    ),
                    "requirements": (
                        (f"{path_feature}_state", path_state),
                        (f"{volatility_feature}_state", volatility_state),
                    ),
                    "eligibility_columns": (
                        feature_eligibility_column(path_feature),
                        feature_eligibility_column(volatility_feature),
                    ),
                }
            )
    if len(specs) != PREREGISTERED_CONDITION_COUNT:
        raise AlphaDiscoveryScannerError(
            "Preregistered condition universe drifted: "
            f"expected={PREREGISTERED_CONDITION_COUNT}, observed={len(specs)}."
        )
    return specs


def _calendar_strata(
    timestamps: pd.Series,
    periods: Sequence[ChronologicalPeriod],
) -> tuple[np.ndarray, tuple[tuple[pd.Timestamp, pd.Timestamp], ...]]:
    strata = np.full(len(timestamps), -1, dtype=np.int64)
    bounds: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for period_id, period in enumerate(periods):
        start, end = period.bounds()
        bounds.append((start, end))
        mask = timestamps.ge(start).to_numpy(dtype=bool) & timestamps.lt(end).to_numpy(
            dtype=bool
        )
        if (strata[mask] != -1).any():
            raise AlphaDiscoveryScannerError(
                "Frozen chronological periods overlap on scanner timestamps."
            )
        strata[mask] = period_id
    if (strata < 0).any():
        first_unassigned = timestamps.iloc[int(np.flatnonzero(strata < 0)[0])]
        raise AlphaDiscoveryScannerError(
            "Every discovery timestamp must belong to exactly one frozen calendar "
            f"period; first unassigned timestamp={first_unassigned.isoformat()}."
        )
    return strata, tuple(bounds)


def _utc_block_ids(timestamps: pd.Series, *, block_length_bars: int) -> np.ndarray:
    cadence_ns = int(pd.Timedelta(minutes=30).value)
    block_ns = cadence_ns * int(block_length_bars)
    return timestamps.astype("int64").to_numpy(dtype=np.int64) // block_ns


def _adjust_families(
    effects: pd.DataFrame,
    *,
    settings: ScannerSettings,
) -> pd.DataFrame:
    output = effects.copy()
    if len(output) > settings.global_family_size:
        raise AlphaDiscoveryScannerError(
            "Observed effects exceed the frozen global multiple-testing universe."
        )
    if output["p_value"].isna().any():
        raise AlphaDiscoveryScannerError(
            "Every preregistered effect must enter correction with a finite p-value."
        )
    p_values = output["p_value"].to_numpy(dtype=float)
    if ((p_values < 0.0) | (p_values > 1.0) | ~np.isfinite(p_values)).any():
        raise AlphaDiscoveryScannerError(
            "Every preregistered effect p-value must lie in [0, 1]."
        )
    output["p_value_local_bh"] = np.nan
    output["p_value_local_by"] = np.nan
    output["local_family_size"] = 0
    grouped = output.groupby(
        list(MULTIPLE_TESTING_FAMILY_COLUMNS),
        sort=False,
        dropna=False,
    ).groups
    for indices in grouped.values():
        positions = list(indices)
        p_values = output.loc[positions, "p_value"].to_numpy(dtype=float)
        output.loc[positions, "p_value_local_bh"] = adjust_pvalues(
            p_values, method="BH"
        )
        output.loc[positions, "p_value_local_by"] = adjust_pvalues(
            p_values, method="BY"
        )
        output.loc[positions, "local_family_size"] = len(positions)
    output["p_value_global_bh"] = adjust_pvalues(
        output["p_value"].to_numpy(dtype=float),
        method="BH",
        total_hypotheses=settings.global_family_size,
        missing_hypothesis_p_value=1.0,
    )
    output["p_value_global_by"] = adjust_pvalues(
        output["p_value"].to_numpy(dtype=float),
        method="BY",
        total_hypotheses=settings.global_family_size,
        missing_hypothesis_p_value=1.0,
    )
    output["global_family_size"] = settings.global_family_size
    output["global_missing_hypotheses_as_p1"] = (
        settings.global_family_size - len(output)
    )
    output["global_by_gate_status"] = np.where(
        (output["inference_status"] == "ELIGIBLE")
        & (output["p_value_global_by"] <= settings.global_fdr_alpha),
        "PASS",
        "FAIL",
    )
    output["bootstrap_ci_gate_status"] = np.where(
        (output["inference_status"] == "ELIGIBLE")
        & (
            (output["confidence_lower"] > 0.0)
            | (output["confidence_upper"] < 0.0)
        ),
        "PASS",
        "FAIL",
    )
    output["statistical_screen_status"] = np.where(
        (output["global_by_gate_status"] == "PASS")
        & (output["bootstrap_ci_gate_status"] == "PASS")
        & (output["temporal_stability_status"] == "STABLE"),
        "PASS",
        "FAIL",
    )
    # Compatibility aliases remain local diagnostics; the binding field is
    # explicitly p_value_global_by/global_by_gate_status.
    output["p_value_bh"] = output["p_value_local_bh"]
    output["p_value_by"] = output["p_value_local_by"]
    output["multiple_testing_family_size"] = output["local_family_size"]
    return output


def scan_conditional_effects(
    features: pd.DataFrame,
    targets: pd.DataFrame,
    *,
    frozen_bins: FrozenBinEdges,
    settings: ScannerSettings = ScannerSettings(),
    horizons: Sequence[int] = ALPHA_DISCOVERY_HORIZONS,
) -> ConditionalScanResult:
    """Measure only approved 1D states and PE x RV 2D interactions."""

    settings.validate()
    frozen_bins.validate()
    if len(features) != len(targets):
        raise AlphaDiscoveryScannerError("Features and targets must have equal rows.")
    feature_timestamps = pd.to_datetime(features["timestamp"], utc=True, errors="raise")
    target_timestamps = pd.to_datetime(targets["timestamp"], utc=True, errors="raise")
    if not feature_timestamps.equals(target_timestamps):
        raise AlphaDiscoveryScannerError(
            "Features and targets must have identical timestamp alignment."
        )
    resolved_horizons = tuple(
        int(value)
        for value in horizons
        if not isinstance(value, bool) and int(value) == value
    )
    if len(resolved_horizons) != len(horizons):
        raise AlphaDiscoveryScannerError(
            "Scanner horizons must be preregistered integer horizons."
        )
    if any(value not in ALPHA_DISCOVERY_HORIZONS for value in resolved_horizons):
        raise AlphaDiscoveryScannerError(
            "Scanner horizons must be a subset of the preregistered horizons."
        )
    if len(set(resolved_horizons)) != len(resolved_horizons):
        raise AlphaDiscoveryScannerError("Scanner horizons cannot repeat.")
    required_feature_metadata = {
        GAP_SEGMENT_COLUMN,
        *(feature_eligibility_column(feature) for feature in PRIMITIVE_FEATURE_COLUMNS),
    }
    missing_feature_metadata = sorted(
        required_feature_metadata.difference(features.columns)
    )
    if missing_feature_metadata:
        raise AlphaDiscoveryScannerError(
            "Scanner features are missing frozen eligibility metadata: "
            f"{missing_feature_metadata}."
        )
    required_targets = {
        column
        for horizon in resolved_horizons
        for column in (
            f"mid_close_to_close_h{horizon}",
            f"next_open_to_future_open_h{horizon}",
            f"executable_long_h{horizon}",
            f"executable_short_h{horizon}",
            f"future_realized_volatility_h{horizon}",
            f"long_mfe_h{horizon}",
            f"long_mae_h{horizon}",
            f"short_mfe_h{horizon}",
            f"short_mae_h{horizon}",
        )
    }
    missing_targets = sorted(required_targets.difference(targets.columns))
    if missing_targets:
        raise AlphaDiscoveryScannerError(
            f"Scanner targets are missing required columns: {missing_targets}."
        )
    required_target_metadata = {
        GAP_SEGMENT_COLUMN,
        *(target_eligibility_column(horizon) for horizon in resolved_horizons),
    }
    missing_target_metadata = sorted(
        required_target_metadata.difference(targets.columns)
    )
    if missing_target_metadata:
        raise AlphaDiscoveryScannerError(
            "Scanner targets are missing frozen eligibility metadata: "
            f"{missing_target_metadata}."
        )

    states = apply_frozen_states(features, frozen_bins)
    timestamps = feature_timestamps.reset_index(drop=True)
    temporal_ids, period_bounds = _calendar_strata(
        timestamps,
        settings.stability_periods,
    )
    feature_gap_ids = pd.to_numeric(
        features[GAP_SEGMENT_COLUMN], errors="coerce"
    ).to_numpy(dtype=float)
    target_gap_ids = pd.to_numeric(
        targets[GAP_SEGMENT_COLUMN], errors="coerce"
    ).to_numpy(dtype=float)
    if (
        not np.isfinite(feature_gap_ids).all()
        or not np.isfinite(target_gap_ids).all()
        or not np.array_equal(feature_gap_ids, target_gap_ids)
    ):
        raise AlphaDiscoveryScannerError(
            "Feature and target gap-segment identities must be finite and identical."
        )
    gap_ids = feature_gap_ids.astype(np.int64)
    continuity_ids = gap_ids * len(settings.stability_periods) + temporal_ids
    primary_time_blocks = _utc_block_ids(
        timestamps,
        block_length_bars=settings.primary_block_length_bars,
    )
    effects: list[dict[str, Any]] = []
    stability: list[dict[str, Any]] = []
    sensitivities: list[dict[str, Any]] = []
    specifications = _condition_specs()

    for spec in specifications:
        condition = np.ones(len(states), dtype=bool)
        for column, state in spec["requirements"]:
            condition &= states[column].to_numpy(dtype=object) == state
        for eligibility_column in spec["eligibility_columns"]:
            eligibility_values = features[eligibility_column]
            if eligibility_values.dtype != bool:
                eligibility_values = eligibility_values.astype(bool)
            condition &= eligibility_values.to_numpy(dtype=bool)
        condition_count = int(condition.sum())
        for horizon in resolved_horizons:
            raw_base = pd.to_numeric(
                targets[f"next_open_to_future_open_h{horizon}"], errors="coerce"
            ).to_numpy(dtype=float)
            mid_base = pd.to_numeric(
                targets[f"mid_close_to_close_h{horizon}"], errors="coerce"
            ).to_numpy(dtype=float)
            future_rv = pd.to_numeric(
                targets[f"future_realized_volatility_h{horizon}"], errors="coerce"
            ).to_numpy(dtype=float)
            for direction, sign in (("LONG", 1.0), ("SHORT", -1.0)):
                direction_key = direction.lower()
                net = pd.to_numeric(
                    targets[f"executable_{direction_key}_h{horizon}"],
                    errors="coerce",
                ).to_numpy(dtype=float)
                mfe = pd.to_numeric(
                    targets[f"{direction_key}_mfe_h{horizon}"], errors="coerce"
                ).to_numpy(dtype=float)
                mae = pd.to_numeric(
                    targets[f"{direction_key}_mae_h{horizon}"], errors="coerce"
                ).to_numpy(dtype=float)
                raw = sign * raw_base
                mid_directional = sign * mid_base
                target_eligible = targets[
                    target_eligibility_column(horizon)
                ].to_numpy(dtype=bool)
                common_finite = np.isfinite(raw) & np.isfinite(net)
                common_finite &= np.isfinite(mfe) & np.isfinite(mae)
                common_finite &= np.isfinite(future_rv) & np.isfinite(mid_directional)
                inference_eligible = target_eligible & common_finite
                valid = condition & inference_eligible
                n = int(valid.sum())
                coverage_fraction = (
                    n / float(condition_count) if condition_count else 0.0
                )
                occupied_primary_blocks = int(
                    len(np.unique(primary_time_blocks[valid]))
                )
                net_values = net[valid]
                effect_identity = (
                    f"{spec['feature_columns']}:{spec['state']}:{horizon}:{direction}:"
                    "executable_return"
                )
                row: dict[str, Any] = {
                    "effect_id": "CE-"
                    + sha256(effect_identity.encode()).hexdigest()[:16],
                    "dimension": spec["dimension"],
                    "feature_family": spec["feature_family"],
                    "feature_columns": spec["feature_columns"],
                    "state": spec["state"],
                    "horizon": horizon,
                    "target": "executable_return",
                    "direction": direction,
                    "preregistered_interaction": spec["preregistered_interaction"],
                    "n": n,
                    "mean_raw_return": (
                        float(np.mean(raw[valid])) if n else float("nan")
                    ),
                    "median_raw_return": (
                        float(np.median(raw[valid])) if n else float("nan")
                    ),
                    "mean_executable_return": (
                        float(np.mean(net_values)) if n else float("nan")
                    ),
                    "median_executable_return": (
                        float(np.median(net_values)) if n else float("nan")
                    ),
                    "mean_net_return": (
                        float(np.mean(net_values)) if n else float("nan")
                    ),
                    "median_net_return": (
                        float(np.median(net_values)) if n else float("nan")
                    ),
                    "standard_error": float("nan"),
                    "hit_rate": (
                        float(np.mean(net_values > 0.0)) if n else float("nan")
                    ),
                    "effect_size": float("nan"),
                    "confidence_lower": float("nan"),
                    "confidence_upper": float("nan"),
                    "p_value": 1.0,
                    "mean_mfe": float(np.mean(mfe[valid])) if n else float("nan"),
                    "median_mfe": (float(np.median(mfe[valid])) if n else float("nan")),
                    "mean_mae": float(np.mean(mae[valid])) if n else float("nan"),
                    "median_mae": (float(np.median(mae[valid])) if n else float("nan")),
                    "mean_directional_mid_close_return": (
                        float(np.mean(mid_directional[valid])) if n else float("nan")
                    ),
                    "mean_future_realized_volatility": (
                        float(np.mean(future_rv[valid])) if n else float("nan")
                    ),
                    "condition_state_n": condition_count,
                    "coverage_fraction": coverage_fraction,
                    "occupied_primary_blocks": occupied_primary_blocks,
                    "minimum_observations_required": settings.minimum_observations,
                    "minimum_coverage_fraction_required": (
                        settings.minimum_coverage_fraction
                    ),
                    "minimum_occupied_primary_blocks_required": (
                        settings.minimum_occupied_primary_blocks
                    ),
                    "inference_status": "AUTOMATIC_FAIL",
                    "automatic_fail": True,
                    "automatic_fail_reasons": "",
                    "net_cost_scope": "OBSERVED_BID_ASK_SPREAD_ONLY",
                    "hac_estimator": settings.hac_estimator,
                    "hac_kernel": settings.hac_kernel,
                    "hac_lag_bars": settings.hac_primary_lag_bars,
                    "hac_statistic": float("nan"),
                    "block_length": settings.primary_block_length_bars,
                    "bootstrap_method": "STRATIFIED_SEGMENTED_MOVING_BLOCK",
                    "bootstrap_resamples": settings.bootstrap_resamples,
                    "bootstrap_resamples_valid": 0,
                    "bootstrap_valid_resample_fraction": 0.0,
                    "bin_edge_hash": frozen_bins.edge_hash,
                }
                failure_reasons: list[str] = []
                if condition_count == 0:
                    failure_reasons.append("NO_ELIGIBLE_STATE_OBSERVATIONS")
                if n < settings.minimum_observations:
                    failure_reasons.append("INSUFFICIENT_N")
                if coverage_fraction < settings.minimum_coverage_fraction:
                    failure_reasons.append("INSUFFICIENT_COVERAGE")
                if occupied_primary_blocks < settings.minimum_occupied_primary_blocks:
                    failure_reasons.append("INSUFFICIENT_PRIMARY_BLOCK_COVERAGE")

                period_means: list[float] = []
                period_counts: list[int] = []
                for block_id, period in enumerate(settings.stability_periods):
                    block_mask = valid & (temporal_ids == block_id)
                    block_n = int(block_mask.sum())
                    block_mean = (
                        float(np.mean(net[block_mask]))
                        if block_n
                        else float("nan")
                    )
                    period_counts.append(block_n)
                    period_means.append(block_mean)
                    period_start, period_end = period_bounds[block_id]
                    stability.append(
                        {
                            "effect_id": row["effect_id"],
                            "feature_family": spec["feature_family"],
                            "feature_columns": spec["feature_columns"],
                            "state": spec["state"],
                            "horizon": horizon,
                            "direction": direction,
                            "chronological_block": block_id,
                            "period_name": period.name,
                            "block_start_inclusive": period_start.isoformat(),
                            "block_end_exclusive": period_end.isoformat(),
                            "n": block_n,
                            "mean_raw_return": (
                                float(np.mean(raw[block_mask]))
                                if block_n
                                else float("nan")
                            ),
                            "mean_net_return": block_mean,
                            "hit_rate": (
                                float(np.mean(net[block_mask] > 0.0))
                                if block_n
                                else float("nan")
                            ),
                        }
                    )

                full_mean = row["mean_net_return"]
                stable = (
                    np.isfinite(full_mean)
                    and full_mean != 0.0
                    and all(
                        count >= settings.minimum_period_observations
                        for count in period_counts
                    )
                    and all(
                        np.isfinite(value)
                        and value != 0.0
                        and np.sign(value) == np.sign(full_mean)
                        for value in period_means
                    )
                )
                row["temporal_stability_status"] = (
                    "STABLE" if stable else "UNSTABLE"
                )
                row["required_stability_periods"] = settings.required_stability_periods
                row["minimum_period_observations"] = (
                    settings.minimum_period_observations
                )

                if not failure_reasons:
                    try:
                        hac = newey_west_conditional_mean_summary(
                            net,
                            condition=condition,
                            eligible=inference_eligible,
                            continuity_segment_ids=continuity_ids,
                            stratum_ids=temporal_ids,
                            lag_bars=settings.hac_primary_lag_bars,
                            estimator=settings.hac_estimator,
                            kernel=settings.hac_kernel,
                        )
                        bootstrap = segmented_moving_block_bootstrap_summary(
                            net,
                            condition=condition,
                            eligible=inference_eligible,
                            continuity_segment_ids=continuity_ids,
                            stratum_ids=temporal_ids,
                            block_length_bars=settings.primary_block_length_bars,
                            resamples=settings.bootstrap_resamples,
                            confidence_level=settings.confidence_level,
                            minimum_valid_resample_fraction=(
                                settings.minimum_valid_resample_fraction
                            ),
                            seed=stable_hypothesis_seed(
                                settings.seed,
                                effect_identity + ":BOOTSTRAP_PRIMARY",
                            ),
                        )
                    except AlphaDiscoveryStatisticsError as exc:
                        failure_reasons.append(
                            "PRIMARY_INFERENCE_ERROR:"
                            + re.sub(r"\s+", "_", str(exc).strip())
                        )
                    else:
                        sample_std = float(np.std(net_values, ddof=1))
                        effect_size = (
                            float(np.mean(net_values) / sample_std)
                            if sample_std > 0.0
                            else float("nan")
                        )
                        row.update(
                            {
                                "standard_error": hac.standard_error,
                                "effect_size": effect_size,
                                "confidence_lower": bootstrap.confidence_lower,
                                "confidence_upper": bootstrap.confidence_upper,
                                "p_value": hac.p_value,
                                "hac_statistic": hac.statistic,
                                "bootstrap_resamples_valid": (
                                    bootstrap.resamples_valid
                                ),
                                "bootstrap_valid_resample_fraction": (
                                    bootstrap.valid_resample_fraction
                                ),
                                "inference_status": "ELIGIBLE",
                                "automatic_fail": False,
                            }
                        )

                        for sensitivity_lag in settings.hac_sensitivity_lags_bars:
                            sensitivity_record = {
                                "effect_id": row["effect_id"],
                                "method_family": "HAC",
                                "parameter_bars": sensitivity_lag,
                                "status": "PASS",
                                "estimate": float("nan"),
                                "standard_error": float("nan"),
                                "statistic": float("nan"),
                                "p_value": float("nan"),
                                "confidence_lower": float("nan"),
                                "confidence_upper": float("nan"),
                                "resamples_valid": 0,
                                "error": "",
                            }
                            try:
                                diagnostic = newey_west_conditional_mean_summary(
                                    net,
                                    condition=condition,
                                    eligible=inference_eligible,
                                    continuity_segment_ids=continuity_ids,
                                    stratum_ids=temporal_ids,
                                    lag_bars=sensitivity_lag,
                                    estimator=settings.hac_estimator,
                                    kernel=settings.hac_kernel,
                                )
                            except AlphaDiscoveryStatisticsError as exc:
                                sensitivity_record["status"] = "FAIL"
                                sensitivity_record["error"] = str(exc)
                            else:
                                sensitivity_record.update(
                                    {
                                        "estimate": diagnostic.mean,
                                        "standard_error": diagnostic.standard_error,
                                        "statistic": diagnostic.statistic,
                                        "p_value": diagnostic.p_value,
                                    }
                                )
                            sensitivities.append(sensitivity_record)

                        for sensitivity_block in settings.sensitivity_block_lengths_bars:
                            sensitivity_record = {
                                "effect_id": row["effect_id"],
                                "method_family": "BOOTSTRAP",
                                "parameter_bars": sensitivity_block,
                                "status": "PASS",
                                "estimate": float("nan"),
                                "standard_error": float("nan"),
                                "statistic": float("nan"),
                                "p_value": float("nan"),
                                "confidence_lower": float("nan"),
                                "confidence_upper": float("nan"),
                                "resamples_valid": 0,
                                "error": "",
                            }
                            try:
                                diagnostic = segmented_moving_block_bootstrap_summary(
                                    net,
                                    condition=condition,
                                    eligible=inference_eligible,
                                    continuity_segment_ids=continuity_ids,
                                    stratum_ids=temporal_ids,
                                    block_length_bars=sensitivity_block,
                                    resamples=settings.bootstrap_resamples,
                                    confidence_level=settings.confidence_level,
                                    minimum_valid_resample_fraction=(
                                        settings.minimum_valid_resample_fraction
                                    ),
                                    seed=stable_hypothesis_seed(
                                        settings.seed,
                                        effect_identity
                                        + f":BOOTSTRAP_SENSITIVITY:{sensitivity_block}",
                                    ),
                                )
                            except AlphaDiscoveryStatisticsError as exc:
                                sensitivity_record["status"] = "FAIL"
                                sensitivity_record["error"] = str(exc)
                            else:
                                sensitivity_record.update(
                                    {
                                        "estimate": diagnostic.mean,
                                        "standard_error": diagnostic.standard_error,
                                        "confidence_lower": (
                                            diagnostic.confidence_lower
                                        ),
                                        "confidence_upper": (
                                            diagnostic.confidence_upper
                                        ),
                                        "resamples_valid": (
                                            diagnostic.resamples_valid
                                        ),
                                    }
                                )
                            sensitivities.append(sensitivity_record)

                row["automatic_fail_reasons"] = ";".join(failure_reasons)
                if failure_reasons:
                    row["p_value"] = 1.0
                    row["inference_status"] = "AUTOMATIC_FAIL"
                    row["automatic_fail"] = True
                effects.append(row)

    expected_effects = PREREGISTERED_CONDITION_COUNT * len(resolved_horizons) * 2
    if len(effects) != expected_effects:
        raise AlphaDiscoveryScannerError(
            "Scanner did not retain the full requested preregistered effect universe: "
            f"expected={expected_effects}, observed={len(effects)}."
        )
    effects_frame = _adjust_families(
        pd.DataFrame(effects),
        settings=settings,
    )
    effects_frame = effects_frame.sort_values(
        [
            "dimension",
            "feature_family",
            "feature_columns",
            "state",
            "horizon",
            "direction",
        ],
        kind="mergesort",
    ).reset_index(drop=True)
    stability_frame = (
        pd.DataFrame(stability)
        .sort_values(["effect_id", "chronological_block"], kind="mergesort")
        .reset_index(drop=True)
    )
    sensitivity_columns = [
        "effect_id",
        "method_family",
        "parameter_bars",
        "status",
        "estimate",
        "standard_error",
        "statistic",
        "p_value",
        "confidence_lower",
        "confidence_upper",
        "resamples_valid",
        "error",
    ]
    sensitivity_frame = pd.DataFrame(sensitivities, columns=sensitivity_columns)
    if not sensitivity_frame.empty:
        sensitivity_frame = sensitivity_frame.sort_values(
            ["effect_id", "method_family", "parameter_bars"],
            kind="mergesort",
        ).reset_index(drop=True)
    return ConditionalScanResult(
        effects=effects_frame,
        temporal_stability=stability_frame,
        inference_sensitivities=sensitivity_frame,
        frozen_bins=frozen_bins,
    )


__all__ = [
    "AlphaDiscoveryScannerError",
    "ConditionalScanResult",
    "ChronologicalPeriod",
    "FrozenBinEdges",
    "MULTIPLE_TESTING_FAMILY_COLUMNS",
    "QUINTILE_LABELS",
    "QUINTILE_PROBABILITIES",
    "PREREGISTERED_CONDITION_COUNT",
    "PREREGISTERED_EFFECT_COUNT",
    "ScannerSettings",
    "apply_frozen_states",
    "fit_discovery_quintiles",
    "preregistered_interaction_pairs",
    "scan_conditional_effects",
]
