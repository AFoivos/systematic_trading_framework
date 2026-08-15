from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from src.experiments.alpha_contracts import AvailableAt, MaterialSpecificationChange
from src.src_data.research_roles import (
    EvidenceRole,
    LegacyDataClassification,
    SourceClassification,
)
from src.utils.run_metadata import compute_config_hash


class AlphaDiscoveryConfigError(ValueError):
    """Raised when the standalone alpha-discovery specification is invalid."""


class AlphaDiscoveryStatus(str, Enum):
    SPECIFICATION_ONLY = "SPECIFICATION_ONLY"
    APPROVED_TO_RUN = "APPROVED_TO_RUN"


_TOP_LEVEL_KEYS = {
    "schema_version",
    "pipeline",
    "research_id",
    "status",
    "specification_hash",
    "approval",
    "scientific_contract",
    "data_eligibility",
    "historical_partition",
    "snapshot_reference",
    "historical_pseudo_oos_reference",
    "evidence_roles",
    "features",
    "horizons",
    "targets_planned",
    "conditional_analysis",
    "execution_measurement",
    "statistics",
    "multiple_testing",
    "promotion_gates",
    "artifacts",
    "runtime",
    "blockers",
    "config_path",
}
_HASH_EXCLUDED_KEYS = {
    "config_path",
    "specification_hash",
    "approval",
    "status",
    "blockers",
}
_EXPECTED_FEATURE_WINDOWS = {
    "log_returns": [1, 4, 16, 48],
    "path_efficiency": [8, 16, 48],
    "realized_volatility": [16, 48, 192],
    "normalized_range": [],
    "close_location": [],
    "utc_hour": [],
    "weekday": [],
}
_EXPECTED_TARGETS = {
    "mid_close_to_close",
    "next_open_to_future_open",
    "executable_long",
    "executable_short",
    "future_realized_volatility",
    "mfe",
    "mae",
}
_EXPECTED_TARGET_AVAILABILITY = {
    "mid_close_to_close": AvailableAt(0, "CLOSE"),
    "next_open_to_future_open": AvailableAt(1, "OPEN"),
    "executable_long": AvailableAt(1, "OPEN"),
    "executable_short": AvailableAt(1, "OPEN"),
    "future_realized_volatility": AvailableAt(0, "CLOSE"),
    "mfe": AvailableAt(1, "OPEN"),
    "mae": AvailableAt(1, "OPEN"),
}
_EXPECTED_MULTIPLE_TESTING_FAMILY = [
    "feature_family",
    "horizon",
    "target",
    "direction",
    "preregistered_interaction",
]
_EXPECTED_PROMOTION_GATES = {
    "coverage",
    "effect_size",
    "temporal_stability",
    "execution_realism",
    "multiple_testing",
    "prospective_confirmation",
}
_EXPECTED_ROLE_ACCESS = {
    EvidenceRole.DISCOVERY: "DISCOVERY_INTERFACE_ONLY",
    EvidenceRole.VALIDATION: "VALIDATION_INTERFACE_ONLY",
    EvidenceRole.HISTORICAL_PSEUDO_OOS: "HISTORICAL_DIAGNOSTIC_ONLY",
    EvidenceRole.PROSPECTIVE_FINAL: "SEPARATE_EXPLICIT_ONLY",
}


def _mapping(payload: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise AlphaDiscoveryConfigError(f"{field} must be a mapping.")
    return dict(payload)


def _exact_keys(payload: Mapping[str, Any], expected: set[str], *, field: str) -> None:
    missing = sorted(expected.difference(payload))
    unexpected = sorted(set(payload).difference(expected))
    if missing or unexpected:
        raise AlphaDiscoveryConfigError(
            f"{field} keys mismatch; missing={missing}, unexpected={unexpected}."
        )


def _non_empty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AlphaDiscoveryConfigError(f"{field} must be a non-empty string.")
    return value


def _sha256(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise AlphaDiscoveryConfigError(
            f"{field} must be a lowercase 64-character SHA-256."
        )
    return value


def _bool(value: Any, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise AlphaDiscoveryConfigError(f"{field} must be boolean.")
    return value


def _timezone_aware_timestamp(value: Any, *, field: str) -> str:
    resolved = _non_empty_string(value, field=field)
    try:
        parsed = datetime.fromisoformat(resolved.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AlphaDiscoveryConfigError(
            f"{field} must be an ISO-8601 timestamp."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AlphaDiscoveryConfigError(f"{field} must include a timezone.")
    return resolved


def compute_alpha_specification_hash(cfg: Mapping[str, Any]) -> str:
    """Hash material specification fields, excluding workflow approval metadata."""

    payload = deepcopy(dict(cfg))
    for key in _HASH_EXCLUDED_KEYS:
        payload.pop(key, None)
    runtime = payload.get("runtime")
    if isinstance(runtime, Mapping):
        runtime_payload = dict(runtime)
        runtime_payload.pop("perform_alpha_calculation", None)
        payload["runtime"] = runtime_payload
    digest, _ = compute_config_hash(payload)
    return digest


def _validate_snapshot_reference(
    payload: Any,
    *,
    expected_role: EvidenceRole,
    expected_start_inclusive: str,
    expected_end_exclusive: str,
) -> None:
    field = (
        "snapshot_reference"
        if expected_role is EvidenceRole.DISCOVERY
        else "historical_pseudo_oos_reference"
    )
    reference = _mapping(payload, field=field)
    expected_keys = {
        "snapshot_id",
        "manifest_path",
        "source_path",
        "expected_sha256",
        "evidence_role",
        "source_classification",
        "legacy_classifications",
        "readiness",
        "parent_snapshot_id",
        "parent_sha256",
        "partition_start_inclusive",
        "partition_end_exclusive",
        "expected_row_count",
        "expected_first_timestamp",
        "expected_last_timestamp",
    }
    _exact_keys(reference, expected_keys, field=field)
    _non_empty_string(reference["snapshot_id"], field=f"{field}.snapshot_id")
    _non_empty_string(reference["source_path"], field=f"{field}.source_path")
    _non_empty_string(reference["manifest_path"], field=f"{field}.manifest_path")
    _sha256(reference["expected_sha256"], field=f"{field}.expected_sha256")
    role = EvidenceRole(reference["evidence_role"])
    if role is not expected_role:
        raise AlphaDiscoveryConfigError(
            f"{field} must have evidence_role={expected_role.value}."
        )
    classification = SourceClassification(reference["source_classification"])
    legacy = reference["legacy_classifications"]
    if not isinstance(legacy, list):
        raise AlphaDiscoveryConfigError(
            f"{field}.legacy_classifications must be a list."
        )
    for item in legacy:
        LegacyDataClassification(item)
    if len(set(legacy)) != len(legacy):
        raise AlphaDiscoveryConfigError(
            f"{field}.legacy_classifications cannot contain duplicates."
        )
    readiness = _non_empty_string(
        reference["readiness"], field=f"{field}.readiness"
    )
    if classification is not SourceClassification.VALIDATED_MARKET_DATA:
        raise AlphaDiscoveryConfigError(
            f"{field} requires source_classification=VALIDATED_MARKET_DATA."
        )
    if readiness != "ELIGIBLE":
        raise AlphaDiscoveryConfigError(f"{field}.readiness must be ELIGIBLE.")
    if legacy:
        raise AlphaDiscoveryConfigError(
            f"{field} cannot retain legacy dataset classifications."
        )
    if reference["parent_snapshot_id"] != "ETHUSD-30M-CANONICAL-V1":
        raise AlphaDiscoveryConfigError(
            f"{field}.parent_snapshot_id must bind ETHUSD-30M-CANONICAL-V1."
        )
    if (
        _sha256(reference["parent_sha256"], field=f"{field}.parent_sha256")
        != "83d182c98ccbb225220eac02b1bae57917e3b2d2feee5929c53d57c8abaf4202"
    ):
        raise AlphaDiscoveryConfigError(f"{field}.parent_sha256 drifted.")
    start = _timezone_aware_timestamp(
        reference["partition_start_inclusive"],
        field=f"{field}.partition_start_inclusive",
    )
    end = _timezone_aware_timestamp(
        reference["partition_end_exclusive"],
        field=f"{field}.partition_end_exclusive",
    )
    if start != expected_start_inclusive or end != expected_end_exclusive:
        raise AlphaDiscoveryConfigError(
            f"{field} partition bounds must be [{expected_start_inclusive}, "
            f"{expected_end_exclusive})."
        )
    _positive_integer(reference["expected_row_count"], field=f"{field}.expected_row_count")
    first = _timezone_aware_timestamp(
        reference["expected_first_timestamp"], field=f"{field}.expected_first_timestamp"
    )
    last = _timezone_aware_timestamp(
        reference["expected_last_timestamp"], field=f"{field}.expected_last_timestamp"
    )
    if datetime.fromisoformat(first.replace("Z", "+00:00")) >= datetime.fromisoformat(
        last.replace("Z", "+00:00")
    ):
        raise AlphaDiscoveryConfigError(
            f"{field} expected timestamp range must be strictly increasing."
        )


def _validate_data_eligibility(payload: Any) -> None:
    contract = _mapping(payload, field="data_eligibility")
    expected = {
        "canonical_bar_policy",
        "observed_minute_count_column",
        "required_observed_minutes",
        "timestamp_gap_policy",
        "feature_window_policy",
        "target_window_policy",
        "partial_bar_repair",
        "gap_imputation",
    }
    _exact_keys(contract, expected, field="data_eligibility")
    frozen = {
        "canonical_bar_policy": "FULL_30_OF_30_OBSERVED_MINUTES",
        "observed_minute_count_column": "observed_minute_count",
        "required_observed_minutes": 30,
        "timestamp_gap_policy": "PRESERVE_TIMELINE_INVALIDATE_DEPENDENCY_WINDOWS",
        "feature_window_policy": "FULL_CONTIGUOUS_T_MINUS_W_THROUGH_T",
        "target_window_policy": "FULL_CONTIGUOUS_T_THROUGH_T_PLUS_H_PLUS_1",
        "partial_bar_repair": "FORBIDDEN",
        "gap_imputation": "FORBIDDEN",
    }
    if contract != frozen:
        raise AlphaDiscoveryConfigError(
            "data_eligibility violates FULL_30_OF_30 and gap-aware dependency rules."
        )


def _validate_historical_partition(payload: Any) -> None:
    contract = _mapping(payload, field="historical_partition")
    expected = {
        "parent_snapshot_id",
        "parent_manifest_path",
        "parent_expected_sha256",
        "cutoff_utc",
        "assignment_rule",
        "child_snapshot_write_mode",
    }
    _exact_keys(contract, expected, field="historical_partition")
    frozen = {
        "parent_snapshot_id": "ETHUSD-30M-CANONICAL-V1",
        "parent_manifest_path": (
            "data/research_snapshots/ETHUSD-30M-CANONICAL-V1/manifest.json"
        ),
        "parent_expected_sha256": (
            "83d182c98ccbb225220eac02b1bae57917e3b2d2feee5929c53d57c8abaf4202"
        ),
        "cutoff_utc": "2025-07-01T00:00:00Z",
        "assignment_rule": "TIMESTAMP_LT_CUTOFF_DISCOVERY_ELSE_HISTORICAL_PSEUDO_OOS",
        "child_snapshot_write_mode": "IMMUTABLE_WRITE_ONCE",
    }
    if contract != frozen:
        raise AlphaDiscoveryConfigError(
            "historical_partition must remain bound to the frozen parent and cutoff."
        )


def _validate_evidence_roles(payload: Any) -> None:
    roles = _mapping(payload, field="evidence_roles")
    expected = {role.value for role in EvidenceRole}
    _exact_keys(roles, expected, field="evidence_roles")
    for role in EvidenceRole:
        contract = _mapping(roles[role.value], field=f"evidence_roles.{role.value}")
        _exact_keys(
            contract, {"purpose", "access"}, field=f"evidence_roles.{role.value}"
        )
        _non_empty_string(
            contract["purpose"], field=f"evidence_roles.{role.value}.purpose"
        )
        _non_empty_string(
            contract["access"], field=f"evidence_roles.{role.value}.access"
        )
        if contract["access"] != _EXPECTED_ROLE_ACCESS[role]:
            raise AlphaDiscoveryConfigError(
                f"{role.value} access must be {_EXPECTED_ROLE_ACCESS[role]}."
            )


def _validate_features(payload: Any) -> None:
    if not isinstance(payload, list) or len(payload) != len(_EXPECTED_FEATURE_WINDOWS):
        raise AlphaDiscoveryConfigError(
            "features must enumerate exactly the seven approved feature families."
        )
    observed: dict[str, list[int]] = {}
    for index, raw_feature in enumerate(payload):
        feature = _mapping(raw_feature, field=f"features[{index}]")
        _exact_keys(
            feature, {"name", "windows", "available_at"}, field=f"features[{index}]"
        )
        name = _non_empty_string(feature["name"], field=f"features[{index}].name")
        windows = feature["windows"]
        if not isinstance(windows, list) or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in windows
        ):
            raise AlphaDiscoveryConfigError(
                f"features[{index}].windows must contain positive integers."
            )
        available_at = AvailableAt.from_dict(feature["available_at"])
        if available_at != AvailableAt(0, "CLOSE"):
            raise AlphaDiscoveryConfigError(
                f"features[{index}].available_at must be close[t]."
            )
        if name in observed:
            raise AlphaDiscoveryConfigError(f"Duplicate feature family: {name}.")
        observed[name] = windows
    if observed != _EXPECTED_FEATURE_WINDOWS:
        raise AlphaDiscoveryConfigError(
            f"Approved feature contract mismatch; expected {_EXPECTED_FEATURE_WINDOWS}, found {observed}."
        )


def _validate_targets(payload: Any) -> None:
    if not isinstance(payload, list):
        raise AlphaDiscoveryConfigError("targets_planned must be a list.")
    names: set[str] = set()
    for index, raw_target in enumerate(payload):
        target = _mapping(raw_target, field=f"targets_planned[{index}]")
        _exact_keys(
            target,
            {"name", "status", "entry_available_at"},
            field=f"targets_planned[{index}]",
        )
        name = _non_empty_string(target["name"], field=f"targets_planned[{index}].name")
        if name not in _EXPECTED_TARGET_AVAILABILITY:
            raise AlphaDiscoveryConfigError(f"Unknown planned target contract: {name}.")
        if target["status"] != "IMPLEMENTED_PHASE_3":
            raise AlphaDiscoveryConfigError(
                f"targets_planned[{index}].status must be IMPLEMENTED_PHASE_3."
            )
        entry_available_at = AvailableAt.from_dict(target["entry_available_at"])
        if entry_available_at != _EXPECTED_TARGET_AVAILABILITY[name]:
            raise AlphaDiscoveryConfigError(
                f"targets_planned[{index}].entry_available_at violates the frozen "
                f"point-in-time contract for {name}."
            )
        names.add(name)
    if names != _EXPECTED_TARGETS or len(names) != len(payload):
        raise AlphaDiscoveryConfigError(
            f"Planned target contract mismatch; expected {sorted(_EXPECTED_TARGETS)}."
        )


def _positive_integer(value: Any, *, field: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise AlphaDiscoveryConfigError(f"{field} must be an integer >= {minimum}.")
    return value


def _validate_execution_measurement(payload: Any) -> None:
    execution = _mapping(payload, field="execution_measurement")
    expected = {
        "state_available_at",
        "entry",
        "exit",
        "quote_source",
        "net_cost_scope",
        "additional_costs",
    }
    _exact_keys(execution, expected, field="execution_measurement")
    if execution["state_available_at"] != "CLOSE_T":
        raise AlphaDiscoveryConfigError(
            "execution_measurement.state_available_at must be CLOSE_T."
        )
    if execution["entry"] != "OPEN_T_PLUS_1":
        raise AlphaDiscoveryConfigError(
            "execution_measurement.entry must be OPEN_T_PLUS_1."
        )
    if execution["exit"] != "OPEN_T_PLUS_H_PLUS_1":
        raise AlphaDiscoveryConfigError(
            "execution_measurement.exit must be OPEN_T_PLUS_H_PLUS_1."
        )
    if execution["quote_source"] != "ACTUAL_DUKASCOPY_BID_ASK":
        raise AlphaDiscoveryConfigError(
            "execution_measurement.quote_source must be ACTUAL_DUKASCOPY_BID_ASK."
        )
    if execution["net_cost_scope"] != "OBSERVED_BID_ASK_SPREAD_ONLY":
        raise AlphaDiscoveryConfigError(
            "execution_measurement.net_cost_scope must be "
            "OBSERVED_BID_ASK_SPREAD_ONLY."
        )
    additional = _mapping(
        execution["additional_costs"],
        field="execution_measurement.additional_costs",
    )
    _exact_keys(
        additional,
        {"commission", "slippage", "swap"},
        field="execution_measurement.additional_costs",
    )
    expected_unavailable = "NOT_INCLUDED_NO_FROZEN_ASSUMPTION"
    if any(value != expected_unavailable for value in additional.values()):
        raise AlphaDiscoveryConfigError(
            "Commission, slippage, and swap must remain explicitly unmodeled until "
            "a separate frozen assumption is approved."
        )


def _validate_statistics(payload: Any) -> None:
    statistics = _mapping(payload, field="statistics")
    expected = {
        "inference_target",
        "net_cost_scope",
        "minimum_observations",
        "minimum_coverage_fraction",
        "minimum_occupied_primary_blocks",
        "hac",
        "block_bootstrap",
        "chronological_stability",
    }
    _exact_keys(statistics, expected, field="statistics")
    if statistics["inference_target"] != "EXECUTABLE_RETURN":
        raise AlphaDiscoveryConfigError(
            "statistics.inference_target must be EXECUTABLE_RETURN."
        )
    if statistics["net_cost_scope"] != "OBSERVED_BID_ASK_SPREAD_ONLY":
        raise AlphaDiscoveryConfigError(
            "statistics.net_cost_scope must be OBSERVED_BID_ASK_SPREAD_ONLY."
        )
    minimum_observations = _positive_integer(
        statistics["minimum_observations"],
        field="statistics.minimum_observations",
        minimum=2,
    )
    if minimum_observations != 200:
        raise AlphaDiscoveryConfigError(
            "statistics.minimum_observations must remain frozen at 200."
        )
    coverage = statistics["minimum_coverage_fraction"]
    if isinstance(coverage, bool) or not isinstance(coverage, (int, float)):
        raise AlphaDiscoveryConfigError(
            "statistics.minimum_coverage_fraction must be numeric."
        )
    if float(coverage) != 0.50:
        raise AlphaDiscoveryConfigError(
            "statistics.minimum_coverage_fraction must remain frozen at 0.50."
        )
    occupied_blocks = _positive_integer(
        statistics["minimum_occupied_primary_blocks"],
        field="statistics.minimum_occupied_primary_blocks",
    )
    if occupied_blocks != 20:
        raise AlphaDiscoveryConfigError(
            "statistics.minimum_occupied_primary_blocks must remain frozen at 20."
        )
    hac = _mapping(statistics["hac"], field="statistics.hac")
    _exact_keys(
        hac,
        {
            "estimator",
            "kernel",
            "primary_lag_rule",
            "primary_lag_bars",
            "sensitivity_lags_bars",
            "sensitivity_role",
        },
        field="statistics.hac",
    )
    expected_hac = {
        "estimator": "CONDITIONAL_MEAN_RATIO",
        "kernel": "BARTLETT",
        "primary_lag_rule": "FIXED_BARS",
        "primary_lag_bars": 48,
        "sensitivity_lags_bars": [96, 192],
        "sensitivity_role": "DIAGNOSTIC_ONLY_NON_BINDING",
    }
    if hac != expected_hac:
        raise AlphaDiscoveryConfigError(
            "statistics.hac must retain the frozen Newey-West/Bartlett lag contract."
        )
    bootstrap = _mapping(
        statistics["block_bootstrap"], field="statistics.block_bootstrap"
    )
    _exact_keys(
        bootstrap,
        {
            "method",
            "timeline",
            "strata",
            "gap_handling",
            "primary_block_length_bars",
            "sensitivity_block_lengths_bars",
            "sensitivity_role",
            "resamples",
            "confidence_level",
            "minimum_valid_resample_fraction",
            "seed",
        },
        field="statistics.block_bootstrap",
    )
    if bootstrap["method"] != "STRATIFIED_SEGMENTED_MOVING_BLOCK":
        raise AlphaDiscoveryConfigError(
            "statistics.block_bootstrap.method must be "
            "STRATIFIED_SEGMENTED_MOVING_BLOCK."
        )
    if bootstrap["timeline"] != "FULL_UNCOMPRESSED_CANONICAL_ROWS":
        raise AlphaDiscoveryConfigError(
            "Bootstrap must operate on the full uncompressed canonical timeline."
        )
    if bootstrap["strata"] != "FROZEN_CALENDAR_PERIODS":
        raise AlphaDiscoveryConfigError(
            "Bootstrap strata must be the frozen calendar periods."
        )
    if bootstrap["gap_handling"] != "NO_BLOCK_CROSSES_GAP":
        raise AlphaDiscoveryConfigError(
            "Bootstrap blocks must not cross timestamp gaps."
        )
    if bootstrap["primary_block_length_bars"] != 48:
        raise AlphaDiscoveryConfigError(
            "Primary bootstrap block length must remain frozen at 48 bars."
        )
    if bootstrap["sensitivity_block_lengths_bars"] != [96, 192]:
        raise AlphaDiscoveryConfigError(
            "Bootstrap sensitivity block lengths must remain [96, 192]."
        )
    if bootstrap["sensitivity_role"] != "DIAGNOSTIC_ONLY_NON_BINDING":
        raise AlphaDiscoveryConfigError(
            "Bootstrap sensitivities must remain diagnostic and non-binding."
        )
    _positive_integer(
        bootstrap["resamples"],
        field="statistics.block_bootstrap.resamples",
    )
    confidence = bootstrap["confidence_level"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise AlphaDiscoveryConfigError(
            "statistics.block_bootstrap.confidence_level must be numeric."
        )
    if not 0.0 < float(confidence) < 1.0:
        raise AlphaDiscoveryConfigError(
            "statistics.block_bootstrap.confidence_level must lie in (0, 1)."
        )
    valid_fraction = bootstrap["minimum_valid_resample_fraction"]
    if isinstance(valid_fraction, bool) or not isinstance(
        valid_fraction, (int, float)
    ):
        raise AlphaDiscoveryConfigError(
            "statistics.block_bootstrap.minimum_valid_resample_fraction must be numeric."
        )
    if float(valid_fraction) != 0.99:
        raise AlphaDiscoveryConfigError(
            "Minimum valid bootstrap resample fraction must remain frozen at 0.99."
        )
    if isinstance(bootstrap["seed"], bool) or not isinstance(bootstrap["seed"], int):
        raise AlphaDiscoveryConfigError(
            "statistics.block_bootstrap.seed must be an integer."
        )
    chronological = _mapping(
        statistics["chronological_stability"],
        field="statistics.chronological_stability",
    )
    _exact_keys(
        chronological,
        {
            "partition",
            "periods",
            "minimum_observations_per_period",
            "required_periods",
            "direction_rule",
        },
        field="statistics.chronological_stability",
    )
    if chronological["partition"] != "FROZEN_CALENDAR_PERIODS":
        raise AlphaDiscoveryConfigError(
            "statistics.chronological_stability.partition must use frozen calendar periods."
        )
    expected_periods = [
        {"name": "Y2020", "start_inclusive": "2020-01-01T00:00:00Z", "end_exclusive": "2021-01-01T00:00:00Z"},
        {"name": "Y2021", "start_inclusive": "2021-01-01T00:00:00Z", "end_exclusive": "2022-01-01T00:00:00Z"},
        {"name": "Y2022", "start_inclusive": "2022-01-01T00:00:00Z", "end_exclusive": "2023-01-01T00:00:00Z"},
        {"name": "Y2023", "start_inclusive": "2023-01-01T00:00:00Z", "end_exclusive": "2024-01-01T00:00:00Z"},
        {"name": "Y2024", "start_inclusive": "2024-01-01T00:00:00Z", "end_exclusive": "2025-01-01T00:00:00Z"},
        {"name": "Y2025H1", "start_inclusive": "2025-01-01T00:00:00Z", "end_exclusive": "2025-07-01T00:00:00Z"},
    ]
    if chronological["periods"] != expected_periods:
        raise AlphaDiscoveryConfigError(
            "Chronological stability periods must remain the six frozen calendar periods."
        )
    if chronological["minimum_observations_per_period"] != 30:
        raise AlphaDiscoveryConfigError(
            "Minimum observations per stability period must remain 30."
        )
    if chronological["required_periods"] != 6:
        raise AlphaDiscoveryConfigError("All six stability periods must be required.")
    if chronological["direction_rule"] != "SAME_NONZERO_SIGN_IN_ALL_REQUIRED_PERIODS":
        raise AlphaDiscoveryConfigError(
            "Chronological direction rule must remain frozen."
        )


def validate_alpha_discovery_config(cfg: dict[str, Any]) -> None:
    """Validate the standalone pre-signal config without canonical defaults."""

    if not isinstance(cfg, dict):
        raise AlphaDiscoveryConfigError("Alpha-discovery config must be a mapping.")
    missing = sorted((_TOP_LEVEL_KEYS - {"config_path"}).difference(cfg))
    unexpected = sorted(set(cfg).difference(_TOP_LEVEL_KEYS))
    if missing or unexpected:
        raise AlphaDiscoveryConfigError(
            f"Alpha-discovery top-level keys mismatch; missing={missing}, unexpected={unexpected}."
        )
    if isinstance(cfg["schema_version"], bool) or cfg["schema_version"] != 2:
        raise AlphaDiscoveryConfigError("schema_version must be 2.")
    pipeline = _mapping(cfg["pipeline"], field="pipeline")
    _exact_keys(pipeline, {"kind", "stage"}, field="pipeline")
    if pipeline != {"kind": "alpha_discovery_v1", "stage": "PRE_SIGNAL_RESEARCH"}:
        raise AlphaDiscoveryConfigError(
            "pipeline must be alpha_discovery_v1 at PRE_SIGNAL_RESEARCH stage."
        )
    research_id = _non_empty_string(cfg["research_id"], field="research_id")
    if not re.fullmatch(r"AR-[0-9]{4}", research_id):
        raise AlphaDiscoveryConfigError("research_id must match AR-0000.")
    status = AlphaDiscoveryStatus(cfg["status"])

    approval = _mapping(cfg["approval"], field="approval")
    _exact_keys(
        approval,
        {
            "approved_to_run",
            "approved_by",
            "approved_at",
            "approved_specification_hash",
        },
        field="approval",
    )
    approved = _bool(approval["approved_to_run"], field="approval.approved_to_run")
    if status is AlphaDiscoveryStatus.SPECIFICATION_ONLY and approved:
        raise AlphaDiscoveryConfigError(
            "SPECIFICATION_ONLY cannot set approval.approved_to_run=true."
        )
    if status is AlphaDiscoveryStatus.SPECIFICATION_ONLY and any(
        approval[name] is not None
        for name in ("approved_by", "approved_at", "approved_specification_hash")
    ):
        raise AlphaDiscoveryConfigError(
            "SPECIFICATION_ONLY approval metadata must remain null."
        )
    if status is AlphaDiscoveryStatus.APPROVED_TO_RUN:
        if not approved:
            raise AlphaDiscoveryConfigError(
                "APPROVED_TO_RUN requires approval.approved_to_run=true."
            )
        for name in ("approved_by", "approved_at", "approved_specification_hash"):
            _non_empty_string(approval[name], field=f"approval.{name}")
        _timezone_aware_timestamp(approval["approved_at"], field="approval.approved_at")

    scientific = _mapping(cfg["scientific_contract"], field="scientific_contract")
    _exact_keys(
        scientific,
        {
            "role_assignment",
            "validation_contamination",
            "prospective_clock",
            "material_changes",
        },
        field="scientific_contract",
    )
    if scientific["role_assignment"] != "IMMUTABLE_PER_SNAPSHOT":
        raise AlphaDiscoveryConfigError(
            "scientific_contract.role_assignment must be IMMUTABLE_PER_SNAPSHOT."
        )
    if (
        scientific["validation_contamination"]
        != "MODIFICATION_AFTER_VIEW_REQUIRES_NEW_VALIDATION"
    ):
        raise AlphaDiscoveryConfigError(
            "scientific_contract.validation_contamination violates the formal contract."
        )
    if scientific["prospective_clock"] != "MATERIAL_CHANGE_RESTARTS_CLOCK":
        raise AlphaDiscoveryConfigError(
            "scientific_contract.prospective_clock violates the formal contract."
        )
    if not isinstance(scientific["material_changes"], list):
        raise AlphaDiscoveryConfigError(
            "scientific_contract.material_changes must be a list."
        )
    expected_changes = {item.value for item in MaterialSpecificationChange}
    actual_changes = set(scientific["material_changes"])
    if actual_changes != expected_changes or len(scientific["material_changes"]) != len(
        expected_changes
    ):
        raise AlphaDiscoveryConfigError(
            "scientific_contract.material_changes does not match the formal contract."
        )

    _validate_data_eligibility(cfg["data_eligibility"])
    _validate_historical_partition(cfg["historical_partition"])
    _validate_snapshot_reference(
        cfg["snapshot_reference"],
        expected_role=EvidenceRole.DISCOVERY,
        expected_start_inclusive="2020-01-01T00:00:00Z",
        expected_end_exclusive="2025-07-01T00:00:00Z",
    )
    _validate_snapshot_reference(
        cfg["historical_pseudo_oos_reference"],
        expected_role=EvidenceRole.HISTORICAL_PSEUDO_OOS,
        expected_start_inclusive="2025-07-01T00:00:00Z",
        expected_end_exclusive="2026-06-10T00:00:00Z",
    )
    _validate_evidence_roles(cfg["evidence_roles"])
    _validate_features(cfg["features"])
    horizons = cfg["horizons"]
    if horizons != [1, 2, 4, 8, 16, 32]:
        raise AlphaDiscoveryConfigError("horizons must be [1, 2, 4, 8, 16, 32].")
    _validate_targets(cfg["targets_planned"])

    conditional = _mapping(cfg["conditional_analysis"], field="conditional_analysis")
    _exact_keys(
        conditional,
        {
            "bins",
            "freeze_bin_edges",
            "one_dimensional_states",
            "two_dimensional_interactions",
            "allow_3d",
        },
        field="conditional_analysis",
    )
    if conditional["bins"] != "DISCOVERY_FITTED_QUINTILES":
        raise AlphaDiscoveryConfigError(
            "conditional_analysis bins must be discovery-fitted quintiles."
        )
    if (
        conditional["freeze_bin_edges"] is not True
        or conditional["one_dimensional_states"] is not True
    ):
        raise AlphaDiscoveryConfigError(
            "Conditional bins and 1D-state contract must remain enabled."
        )
    if conditional["two_dimensional_interactions"] != [
        ["path_efficiency", "realized_volatility"]
    ]:
        raise AlphaDiscoveryConfigError(
            "Only the preregistered path_efficiency x realized_volatility interaction is allowed."
        )
    if conditional["allow_3d"] is not False:
        raise AlphaDiscoveryConfigError("3D conditional search is prohibited.")

    _validate_execution_measurement(cfg["execution_measurement"])
    _validate_statistics(cfg["statistics"])

    multiple = _mapping(cfg["multiple_testing"], field="multiple_testing")
    _exact_keys(
        multiple,
        {
            "family_definition",
            "methods",
            "global_family_scope",
            "global_family_size",
            "failed_hypothesis_p_value",
            "retain_failed_in_denominator",
            "binding_method",
            "primary_fdr_alpha",
            "local_fdr_alpha",
            "local_methods_role",
            "status",
        },
        field="multiple_testing",
    )
    if multiple["family_definition"] != _EXPECTED_MULTIPLE_TESTING_FAMILY:
        raise AlphaDiscoveryConfigError(
            "multiple_testing.family_definition violates the frozen hierarchy."
        )
    expected_multiple = {
        "family_definition": _EXPECTED_MULTIPLE_TESTING_FAMILY,
        "methods": ["BH", "BY"],
        "global_family_scope": "ALL_PREREGISTERED_EFFECTS",
        "global_family_size": 3792,
        "failed_hypothesis_p_value": 1.0,
        "retain_failed_in_denominator": True,
        "binding_method": "GLOBAL_BY",
        "primary_fdr_alpha": 0.05,
        "local_fdr_alpha": 0.05,
        "local_methods_role": "DIAGNOSTIC_ONLY_NON_BINDING",
        "status": "IMPLEMENTED_FROZEN_CONTRACT",
    }
    if multiple != expected_multiple:
        raise AlphaDiscoveryConfigError(
            "Multiple-testing contract must retain the 3,792-effect global BY family."
        )

    gates = _mapping(cfg["promotion_gates"], field="promotion_gates")
    if set(gates) != _EXPECTED_PROMOTION_GATES:
        raise AlphaDiscoveryConfigError(
            "promotion_gates must contain the six frozen gate contracts."
        )
    for name, gate in gates.items():
        gate_payload = _mapping(gate, field=f"promotion_gates.{name}")
        _exact_keys(
            gate_payload, {"contract", "status"}, field=f"promotion_gates.{name}"
        )
        _non_empty_string(
            gate_payload["contract"], field=f"promotion_gates.{name}.contract"
        )
        if gate_payload["status"] != "NOT_EVALUATED":
            raise AlphaDiscoveryConfigError(
                f"promotion_gates.{name}.status must be NOT_EVALUATED."
            )

    artifacts = _mapping(cfg["artifacts"], field="artifacts")
    _exact_keys(
        artifacts,
        {"output_root", "layout_version", "write_mode"},
        field="artifacts",
    )
    output_root = _non_empty_string(
        artifacts["output_root"], field="artifacts.output_root"
    )
    if output_root != "logs/experiments/alpha_discovery":
        raise AlphaDiscoveryConfigError(
            "artifacts.output_root must remain under the approved experiment infrastructure."
        )
    if (
        isinstance(artifacts["layout_version"], bool)
        or artifacts["layout_version"] != 2
        or artifacts["write_mode"] != "IMMUTABLE_RUN_DIRECTORY"
    ):
        raise AlphaDiscoveryConfigError("Artifact layout must be immutable version 2.")

    runtime = _mapping(cfg["runtime"], field="runtime")
    _exact_keys(
        runtime,
        {"perform_alpha_calculation", "run_backtests", "access_prospective_final"},
        field="runtime",
    )
    for name, value in runtime.items():
        _bool(value, field=f"runtime.{name}")
    if runtime["run_backtests"]:
        raise AlphaDiscoveryConfigError(
            "Alpha discovery cannot enable runtime.run_backtests."
        )
    if runtime["access_prospective_final"]:
        raise AlphaDiscoveryConfigError(
            "Alpha discovery cannot enable runtime.access_prospective_final."
        )
    if (
        status is AlphaDiscoveryStatus.SPECIFICATION_ONLY
        and runtime["perform_alpha_calculation"]
    ):
        raise AlphaDiscoveryConfigError(
            "SPECIFICATION_ONLY requires runtime.perform_alpha_calculation=false."
        )
    if (
        status is AlphaDiscoveryStatus.APPROVED_TO_RUN
        and not runtime["perform_alpha_calculation"]
    ):
        raise AlphaDiscoveryConfigError(
            "APPROVED_TO_RUN requires runtime.perform_alpha_calculation=true."
        )
    if not isinstance(cfg["blockers"], list):
        raise AlphaDiscoveryConfigError("blockers must be a list.")
    if any(
        not isinstance(blocker, str) or not blocker.strip()
        for blocker in cfg["blockers"]
    ):
        raise AlphaDiscoveryConfigError("blockers must contain only non-empty strings.")
    if status is AlphaDiscoveryStatus.SPECIFICATION_ONLY and not cfg["blockers"]:
        raise AlphaDiscoveryConfigError("SPECIFICATION_ONLY must state its blockers.")
    if status is AlphaDiscoveryStatus.APPROVED_TO_RUN and cfg["blockers"]:
        raise AlphaDiscoveryConfigError(
            "APPROVED_TO_RUN cannot retain unresolved blockers."
        )

    declared_hash = _sha256(cfg["specification_hash"], field="specification_hash")
    computed_hash = compute_alpha_specification_hash(cfg)
    if declared_hash != computed_hash:
        raise AlphaDiscoveryConfigError(
            f"specification_hash mismatch: declared={declared_hash}, computed={computed_hash}."
        )
    if status is AlphaDiscoveryStatus.APPROVED_TO_RUN:
        approved_hash = _sha256(
            approval["approved_specification_hash"],
            field="approval.approved_specification_hash",
        )
        if approved_hash != computed_hash:
            raise AlphaDiscoveryConfigError(
                "Approval is for a different specification hash."
            )


def validate_alpha_discovery_any_config(cfg: dict[str, Any]) -> None:
    """Dispatch to the exact frozen validator declared by the pipeline kind."""

    if not isinstance(cfg, dict):
        raise AlphaDiscoveryConfigError("Alpha-discovery config must be a mapping.")
    pipeline = cfg.get("pipeline")
    if not isinstance(pipeline, Mapping):
        raise AlphaDiscoveryConfigError("Alpha-discovery pipeline must be a mapping.")
    kind = pipeline.get("kind")
    if kind == "alpha_discovery_v1":
        validate_alpha_discovery_config(cfg)
        return
    if kind == "alpha_discovery_v2":
        from src.utils.alpha_discovery_v2_config import (
            validate_alpha_discovery_v2_config,
        )

        validate_alpha_discovery_v2_config(cfg)
        return
    if kind == "alpha_discovery_v3":
        from src.utils.alpha_discovery_v3_config import (
            validate_alpha_discovery_v3_config,
        )

        validate_alpha_discovery_v3_config(cfg)
        return
    if kind == "alpha_discovery_v4":
        from src.utils.alpha_discovery_v4_config import (
            validate_alpha_discovery_v4_config,
        )

        validate_alpha_discovery_v4_config(cfg)
        return
    raise AlphaDiscoveryConfigError(
        f"Unsupported alpha-discovery pipeline kind: {kind!r}."
    )


__all__ = [
    "AlphaDiscoveryConfigError",
    "AlphaDiscoveryStatus",
    "compute_alpha_specification_hash",
    "validate_alpha_discovery_any_config",
    "validate_alpha_discovery_config",
]
