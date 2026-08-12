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
    "snapshot_reference",
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
    status: AlphaDiscoveryStatus,
) -> None:
    reference = _mapping(payload, field="snapshot_reference")
    expected_keys = {
        "snapshot_id",
        "manifest_path",
        "source_path",
        "expected_sha256",
        "evidence_role",
        "source_classification",
        "legacy_classifications",
        "readiness",
    }
    _exact_keys(reference, expected_keys, field="snapshot_reference")
    _non_empty_string(reference["snapshot_id"], field="snapshot_reference.snapshot_id")
    _non_empty_string(reference["source_path"], field="snapshot_reference.source_path")
    _sha256(reference["expected_sha256"], field="snapshot_reference.expected_sha256")
    role = EvidenceRole(reference["evidence_role"])
    if role is not EvidenceRole.DISCOVERY:
        raise AlphaDiscoveryConfigError(
            "AR discovery source must have evidence_role=DISCOVERY."
        )
    classification = SourceClassification(reference["source_classification"])
    legacy = reference["legacy_classifications"]
    if not isinstance(legacy, list):
        raise AlphaDiscoveryConfigError(
            "snapshot_reference.legacy_classifications must be a list."
        )
    for item in legacy:
        LegacyDataClassification(item)
    if len(set(legacy)) != len(legacy):
        raise AlphaDiscoveryConfigError(
            "snapshot_reference.legacy_classifications cannot contain duplicates."
        )
    readiness = _non_empty_string(
        reference["readiness"], field="snapshot_reference.readiness"
    )
    manifest_path = reference["manifest_path"]
    if manifest_path is not None:
        _non_empty_string(manifest_path, field="snapshot_reference.manifest_path")
    if status is AlphaDiscoveryStatus.APPROVED_TO_RUN:
        if manifest_path is None:
            raise AlphaDiscoveryConfigError(
                "APPROVED_TO_RUN requires a frozen snapshot manifest_path."
            )
        if classification is not SourceClassification.VALIDATED_MARKET_DATA:
            raise AlphaDiscoveryConfigError(
                "APPROVED_TO_RUN requires source_classification=VALIDATED_MARKET_DATA."
            )
        if readiness != "ELIGIBLE":
            raise AlphaDiscoveryConfigError(
                "APPROVED_TO_RUN requires readiness=ELIGIBLE."
            )
        if legacy:
            raise AlphaDiscoveryConfigError(
                "APPROVED_TO_RUN cannot retain legacy dataset classifications."
            )
    if readiness == "ELIGIBLE":
        if manifest_path is None:
            raise AlphaDiscoveryConfigError(
                "ELIGIBLE snapshot_reference requires a manifest_path."
            )
        if classification is not SourceClassification.VALIDATED_MARKET_DATA:
            raise AlphaDiscoveryConfigError(
                "ELIGIBLE snapshot_reference requires VALIDATED_MARKET_DATA."
            )
        if legacy:
            raise AlphaDiscoveryConfigError(
                "ELIGIBLE snapshot_reference cannot retain legacy classifications."
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
    _positive_integer(
        statistics["minimum_observations"],
        field="statistics.minimum_observations",
        minimum=2,
    )
    bootstrap = _mapping(
        statistics["block_bootstrap"], field="statistics.block_bootstrap"
    )
    _exact_keys(
        bootstrap,
        {"method", "block_length_bars", "resamples", "confidence_level", "seed"},
        field="statistics.block_bootstrap",
    )
    if bootstrap["method"] != "CIRCULAR_MOVING_BLOCK":
        raise AlphaDiscoveryConfigError(
            "statistics.block_bootstrap.method must be CIRCULAR_MOVING_BLOCK."
        )
    _positive_integer(
        bootstrap["block_length_bars"],
        field="statistics.block_bootstrap.block_length_bars",
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
        {"partition", "block_count"},
        field="statistics.chronological_stability",
    )
    if chronological["partition"] != "EQUAL_OBSERVATION_COUNT":
        raise AlphaDiscoveryConfigError(
            "statistics.chronological_stability.partition must be "
            "EQUAL_OBSERVATION_COUNT."
        )
    _positive_integer(
        chronological["block_count"],
        field="statistics.chronological_stability.block_count",
        minimum=2,
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
    if isinstance(cfg["schema_version"], bool) or cfg["schema_version"] != 1:
        raise AlphaDiscoveryConfigError("schema_version must be 1.")
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

    _validate_snapshot_reference(cfg["snapshot_reference"], status=status)
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
        multiple, {"family_definition", "methods", "status"}, field="multiple_testing"
    )
    if multiple["family_definition"] != _EXPECTED_MULTIPLE_TESTING_FAMILY:
        raise AlphaDiscoveryConfigError(
            "multiple_testing.family_definition violates the frozen hierarchy."
        )
    if (
        multiple["methods"] != ["BH", "BY"]
        or multiple["status"] != "IMPLEMENTED_PHASE_3"
    ):
        raise AlphaDiscoveryConfigError(
            "Multiple-testing methods must be the implemented Phase-3 BH/BY contract."
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
        or artifacts["layout_version"] != 1
        or artifacts["write_mode"] != "IMMUTABLE_RUN_DIRECTORY"
    ):
        raise AlphaDiscoveryConfigError("Artifact layout must be immutable version 1.")

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


__all__ = [
    "AlphaDiscoveryConfigError",
    "AlphaDiscoveryStatus",
    "compute_alpha_specification_hash",
    "validate_alpha_discovery_config",
]
