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
    adjust_pvalues,
    chronological_block_ids,
    moving_block_bootstrap_summary,
    stable_hypothesis_seed,
)
from src.experiments.alpha_discovery_targets import ALPHA_DISCOVERY_HORIZONS
from src.features.alpha_discovery_primitives import (
    CONTINUOUS_FEATURE_COLUMNS,
    PATH_EFFICIENCY_WINDOWS,
    PRIMITIVE_FEATURE_COLUMNS,
    REALIZED_VOLATILITY_WINDOWS,
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
    if (
        utc_hour.isna().any()
        or (utc_hour % 1 != 0).any()
        or (~utc_hour.between(0, 23)).any()
    ):
        raise AlphaDiscoveryScannerError("utc_hour states must be integers in [0, 23].")
    if (
        weekday.isna().any()
        or (weekday % 1 != 0).any()
        or (~weekday.between(0, 6)).any()
    ):
        raise AlphaDiscoveryScannerError("weekday states must be integers in [0, 6].")
    states["utc_hour_state"] = utc_hour.astype(int).map(lambda value: f"H{value:02d}")
    states["weekday_state"] = weekday.astype(int).map(lambda value: f"D{value}")
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
class ScannerSettings:
    block_length_bars: int = 48
    bootstrap_resamples: int = 2_000
    confidence_level: float = 0.95
    seed: int = 7
    minimum_observations: int = 30
    chronological_blocks: int = 6

    @classmethod
    def from_config(cls, payload: Mapping[str, Any]) -> ScannerSettings:
        """Resolve the explicit Phase-3 inference contract from configuration."""

        if not isinstance(payload, Mapping):
            raise AlphaDiscoveryScannerError("statistics must be a mapping.")
        expected = {
            "inference_target",
            "net_cost_scope",
            "minimum_observations",
            "block_bootstrap",
            "chronological_stability",
        }
        missing = sorted(expected.difference(payload))
        unexpected = sorted(set(payload).difference(expected))
        if missing or unexpected:
            raise AlphaDiscoveryScannerError(
                "statistics keys mismatch; "
                f"missing={missing}, unexpected={unexpected}."
            )
        if payload["inference_target"] != "EXECUTABLE_RETURN":
            raise AlphaDiscoveryScannerError(
                "statistics.inference_target must be EXECUTABLE_RETURN."
            )
        if payload["net_cost_scope"] != "OBSERVED_BID_ASK_SPREAD_ONLY":
            raise AlphaDiscoveryScannerError(
                "statistics.net_cost_scope must be OBSERVED_BID_ASK_SPREAD_ONLY."
            )
        bootstrap = payload["block_bootstrap"]
        chronological = payload["chronological_stability"]
        if not isinstance(bootstrap, Mapping) or not isinstance(chronological, Mapping):
            raise AlphaDiscoveryScannerError(
                "Block-bootstrap and chronological-stability settings must be mappings."
            )
        if set(bootstrap) != {
            "method",
            "block_length_bars",
            "resamples",
            "confidence_level",
            "seed",
        }:
            raise AlphaDiscoveryScannerError(
                "statistics.block_bootstrap keys violate the frozen contract."
            )
        if bootstrap["method"] != "CIRCULAR_MOVING_BLOCK":
            raise AlphaDiscoveryScannerError(
                "statistics.block_bootstrap.method must be CIRCULAR_MOVING_BLOCK."
            )
        if set(chronological) != {"partition", "block_count"}:
            raise AlphaDiscoveryScannerError(
                "statistics.chronological_stability keys violate the frozen contract."
            )
        if chronological["partition"] != "EQUAL_OBSERVATION_COUNT":
            raise AlphaDiscoveryScannerError(
                "statistics.chronological_stability.partition must be "
                "EQUAL_OBSERVATION_COUNT."
            )
        settings = cls(
            block_length_bars=bootstrap["block_length_bars"],
            bootstrap_resamples=bootstrap["resamples"],
            confidence_level=bootstrap["confidence_level"],
            seed=bootstrap["seed"],
            minimum_observations=payload["minimum_observations"],
            chronological_blocks=chronological["block_count"],
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        for name in (
            "block_length_bars",
            "bootstrap_resamples",
            "minimum_observations",
            "chronological_blocks",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise AlphaDiscoveryScannerError(f"{name} must be a positive integer.")
        if self.chronological_blocks < 2:
            raise AlphaDiscoveryScannerError("chronological_blocks must be >= 2.")
        if not 0.0 < float(self.confidence_level) < 1.0:
            raise AlphaDiscoveryScannerError("confidence_level must lie in (0, 1).")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise AlphaDiscoveryScannerError("seed must be an integer.")


@dataclass(frozen=True)
class ConditionalScanResult:
    effects: pd.DataFrame
    temporal_stability: pd.DataFrame
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
                }
            )
    return specs


def _adjust_families(effects: pd.DataFrame) -> pd.DataFrame:
    output = effects.copy()
    output["p_value_bh"] = np.nan
    output["p_value_by"] = np.nan
    output["multiple_testing_family_size"] = 0
    grouped = output.groupby(
        list(MULTIPLE_TESTING_FAMILY_COLUMNS),
        sort=False,
        dropna=False,
    ).groups
    for indices in grouped.values():
        positions = list(indices)
        p_values = output.loc[positions, "p_value"].to_numpy(dtype=float)
        output.loc[positions, "p_value_bh"] = adjust_pvalues(p_values, method="BH")
        output.loc[positions, "p_value_by"] = adjust_pvalues(p_values, method="BY")
        output.loc[positions, "multiple_testing_family_size"] = int(
            np.isfinite(p_values).sum()
        )
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
    if len(features) < settings.chronological_blocks:
        raise AlphaDiscoveryScannerError(
            "Not enough rows for the preregistered chronological blocks."
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

    states = apply_frozen_states(features, frozen_bins)
    temporal_ids = chronological_block_ids(
        len(features), block_count=settings.chronological_blocks
    )
    effects: list[dict[str, Any]] = []
    stability: list[dict[str, Any]] = []
    timestamps = feature_timestamps.reset_index(drop=True)
    specifications = _condition_specs()

    for spec in specifications:
        condition = np.ones(len(states), dtype=bool)
        for column, state in spec["requirements"]:
            condition &= states[column].to_numpy(dtype=object) == state
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
                valid = condition & np.isfinite(raw) & np.isfinite(net)
                valid &= np.isfinite(mfe) & np.isfinite(mae) & np.isfinite(future_rv)
                valid &= np.isfinite(mid_directional)
                n = int(valid.sum())
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
                    "p_value": float("nan"),
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
                    "inference_status": (
                        "ELIGIBLE"
                        if n >= settings.minimum_observations
                        else "INSUFFICIENT_N"
                    ),
                    "net_cost_scope": "OBSERVED_BID_ASK_SPREAD_ONLY",
                    "block_length": float("nan"),
                    "bootstrap_resamples": settings.bootstrap_resamples,
                    "bin_edge_hash": frozen_bins.edge_hash,
                }
                if n >= settings.minimum_observations:
                    summary = moving_block_bootstrap_summary(
                        net_values,
                        block_length=settings.block_length_bars,
                        resamples=settings.bootstrap_resamples,
                        confidence_level=settings.confidence_level,
                        seed=stable_hypothesis_seed(
                            settings.seed,
                            effect_identity,
                        ),
                    )
                    row.update(
                        {
                            "median_net_return": summary.median,
                            "standard_error": summary.standard_error,
                            "hit_rate": summary.hit_rate,
                            "effect_size": summary.effect_size,
                            "confidence_lower": summary.confidence_lower,
                            "confidence_upper": summary.confidence_upper,
                            "p_value": summary.p_value,
                            "block_length": summary.block_length,
                        }
                    )
                effects.append(row)

                for block_id in range(settings.chronological_blocks):
                    block_mask = valid & (temporal_ids == block_id)
                    block_n = int(block_mask.sum())
                    positional = np.flatnonzero(temporal_ids == block_id)
                    stability.append(
                        {
                            "effect_id": row["effect_id"],
                            "feature_family": spec["feature_family"],
                            "feature_columns": spec["feature_columns"],
                            "state": spec["state"],
                            "horizon": horizon,
                            "direction": direction,
                            "chronological_block": block_id,
                            "block_start": timestamps.iloc[positional[0]].isoformat(),
                            "block_end": timestamps.iloc[positional[-1]].isoformat(),
                            "n": block_n,
                            "mean_raw_return": (
                                float(np.mean(raw[block_mask]))
                                if block_n
                                else float("nan")
                            ),
                            "mean_net_return": (
                                float(np.mean(net[block_mask]))
                                if block_n
                                else float("nan")
                            ),
                            "hit_rate": (
                                float(np.mean(net[block_mask] > 0.0))
                                if block_n
                                else float("nan")
                            ),
                        }
                    )

    effects_frame = _adjust_families(pd.DataFrame(effects))
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
    return ConditionalScanResult(
        effects=effects_frame,
        temporal_stability=stability_frame,
        frozen_bins=frozen_bins,
    )


__all__ = [
    "AlphaDiscoveryScannerError",
    "ConditionalScanResult",
    "FrozenBinEdges",
    "MULTIPLE_TESTING_FAMILY_COLUMNS",
    "QUINTILE_LABELS",
    "QUINTILE_PROBABILITIES",
    "ScannerSettings",
    "apply_frozen_states",
    "fit_discovery_quintiles",
    "preregistered_interaction_pairs",
    "scan_conditional_effects",
]
