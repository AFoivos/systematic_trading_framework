from __future__ import annotations

"""Validation for the frozen spread-aware AR-0002 discovery contract."""

import re
from typing import Any

from src.experiments.alpha_contracts import AvailableAt, MaterialSpecificationChange
from src.src_data.research_roles import EvidenceRole
from src.utils.alpha_discovery_config import (
    AlphaDiscoveryConfigError,
    AlphaDiscoveryStatus,
    _bool,
    _exact_keys,
    _mapping,
    _non_empty_string,
    _sha256,
    _timezone_aware_timestamp,
    _validate_data_eligibility,
    _validate_evidence_roles,
    _validate_execution_measurement,
    _validate_historical_partition,
    _validate_snapshot_reference,
    _validate_statistics,
    _validate_targets,
    compute_alpha_specification_hash,
)

AR0002_CONTINUOUS_FEATURES = (
    "log_return_48",
    "path_efficiency_48",
    "realized_volatility_48",
    "spread_fraction",
)
AR0002_INTERACTION_PAIRS = (
    ("log_return_48", "spread_fraction"),
    ("path_efficiency_48", "spread_fraction"),
    ("realized_volatility_48", "spread_fraction"),
    ("path_efficiency_48", "realized_volatility_48"),
)
AR0002_HORIZONS = (16, 32, 64)
AR0002_CONDITION_COUNT = 120
AR0002_EFFECT_COUNT = 720
AR0002_MINIMUM_MEAN_NET_RETURN = 0.001

_TOP_LEVEL_KEYS = {
    "schema_version",
    "pipeline",
    "research_id",
    "status",
    "specification_hash",
    "approval",
    "prior_research_context",
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
    "economic_gate",
    "execution_measurement",
    "statistics",
    "multiple_testing",
    "promotion_gates",
    "artifacts",
    "runtime",
    "blockers",
    "config_path",
}


def _validate_approval(cfg: dict[str, Any]) -> AlphaDiscoveryStatus:
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
    metadata = ("approved_by", "approved_at", "approved_specification_hash")
    if status is AlphaDiscoveryStatus.SPECIFICATION_ONLY:
        if approved or any(approval[name] is not None for name in metadata):
            raise AlphaDiscoveryConfigError(
                "AR-0002 SPECIFICATION_ONLY approval must remain false and null."
            )
    else:
        if not approved:
            raise AlphaDiscoveryConfigError(
                "AR-0002 APPROVED_TO_RUN requires approved_to_run=true."
            )
        for name in metadata:
            _non_empty_string(approval[name], field=f"approval.{name}")
        _timezone_aware_timestamp(approval["approved_at"], field="approval.approved_at")
    return status


def _validate_prior_research_context(payload: Any) -> None:
    context = _mapping(payload, field="prior_research_context")
    _exact_keys(
        context,
        {
            "source_research_id",
            "source_specification_hash",
            "source_artifact_sha256",
            "evidence_role",
            "use",
            "contamination_statement",
        },
        field="prior_research_context",
    )
    if context["source_research_id"] != "AR-0001":
        raise AlphaDiscoveryConfigError("AR-0002 must identify AR-0001 as its source.")
    if context["source_specification_hash"] != (
        "38547ee331f5efe7f3dabbe7f5895974b454bf52e4fde92a0b2b6908ab725c1c"
    ):
        raise AlphaDiscoveryConfigError("AR-0002 source specification hash drifted.")
    artifacts = _mapping(
        context["source_artifact_sha256"],
        field="prior_research_context.source_artifact_sha256",
    )
    _exact_keys(
        artifacts,
        {"conditional_effects", "inference_sensitivities", "temporal_stability"},
        field="prior_research_context.source_artifact_sha256",
    )
    expected_artifacts = {
        "conditional_effects": (
            "cb51b07cada37dec2e7f3efb8dad218fc570c6f40955d966c12e528a0b65f00a"
        ),
        "inference_sensitivities": (
            "945bf59fb63e0fcbe8f7f2e867783e555b9bd6947b8ba7ffd3db081358e74167"
        ),
        "temporal_stability": (
            "7434e2c2e74801b001a83003997b4b5cb16875945a795058681ff7f4ffebbdf6"
        ),
    }
    for name, value in artifacts.items():
        _sha256(value, field=f"prior_research_context.source_artifact_sha256.{name}")
    if artifacts != expected_artifacts:
        raise AlphaDiscoveryConfigError("AR-0002 source artifact hashes drifted.")
    if context["evidence_role"] != "DISCOVERY":
        raise AlphaDiscoveryConfigError("AR-0001 results remain DISCOVERY evidence.")
    if context["use"] != "POST_HOC_HYPOTHESIS_GENERATION_ONLY":
        raise AlphaDiscoveryConfigError(
            "Prior AR-0001 results may be used only for post-hoc hypothesis generation."
        )
    if context["contamination_statement"] != (
        "SAME_DISCOVERY_REUSED_NO_VALIDATION_OR_FINAL_CLAIM"
    ):
        raise AlphaDiscoveryConfigError(
            "AR-0002 must disclose reuse of already inspected discovery data."
        )


def _validate_scientific_contract(payload: Any) -> None:
    contract = _mapping(payload, field="scientific_contract")
    _exact_keys(
        contract,
        {
            "role_assignment",
            "validation_contamination",
            "prospective_clock",
            "material_changes",
        },
        field="scientific_contract",
    )
    if contract["role_assignment"] != "IMMUTABLE_PER_SNAPSHOT":
        raise AlphaDiscoveryConfigError("AR-0002 role assignment must be immutable.")
    if contract["validation_contamination"] != (
        "MODIFICATION_AFTER_VIEW_REQUIRES_NEW_VALIDATION"
    ):
        raise AlphaDiscoveryConfigError("AR-0002 contamination contract drifted.")
    if contract["prospective_clock"] != "MATERIAL_CHANGE_RESTARTS_CLOCK":
        raise AlphaDiscoveryConfigError("AR-0002 prospective clock contract drifted.")
    expected = {change.value for change in MaterialSpecificationChange}
    observed = contract["material_changes"]
    if not isinstance(observed, list) or set(observed) != expected or len(observed) != len(expected):
        raise AlphaDiscoveryConfigError("AR-0002 material changes contract drifted.")


def _validate_features(payload: Any) -> None:
    expected = {
        "log_returns": [48],
        "path_efficiency": [48],
        "realized_volatility": [48],
        "spread_fraction": [],
    }
    if not isinstance(payload, list) or len(payload) != len(expected):
        raise AlphaDiscoveryConfigError(
            "AR-0002 must enumerate exactly four approved feature families."
        )
    observed: dict[str, list[int]] = {}
    for index, raw in enumerate(payload):
        feature = _mapping(raw, field=f"features[{index}]")
        _exact_keys(feature, {"name", "windows", "available_at"}, field=f"features[{index}]")
        name = _non_empty_string(feature["name"], field=f"features[{index}].name")
        windows = feature["windows"]
        if not isinstance(windows, list) or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in windows
        ):
            raise AlphaDiscoveryConfigError(
                f"features[{index}].windows must contain positive integers."
            )
        if AvailableAt.from_dict(feature["available_at"]) != AvailableAt(0, "CLOSE"):
            raise AlphaDiscoveryConfigError(
                f"features[{index}].available_at must be close[t]."
            )
        if name in observed:
            raise AlphaDiscoveryConfigError(f"Duplicate AR-0002 feature family: {name}.")
        observed[name] = windows
    if observed != expected:
        raise AlphaDiscoveryConfigError(
            f"AR-0002 feature contract mismatch; expected {expected}, found {observed}."
        )


def _validate_conditional_analysis(payload: Any) -> None:
    conditional = _mapping(payload, field="conditional_analysis")
    _exact_keys(
        conditional,
        {
            "bins",
            "freeze_bin_edges",
            "one_dimensional_feature_columns",
            "two_dimensional_interactions",
            "allow_3d",
        },
        field="conditional_analysis",
    )
    expected = {
        "bins": "DISCOVERY_FITTED_QUINTILES",
        "freeze_bin_edges": True,
        "one_dimensional_feature_columns": list(AR0002_CONTINUOUS_FEATURES),
        "two_dimensional_interactions": [
            list(pair) for pair in AR0002_INTERACTION_PAIRS
        ],
        "allow_3d": False,
    }
    if conditional != expected:
        raise AlphaDiscoveryConfigError(
            "AR-0002 conditional universe must remain the frozen 120-state family."
        )


def _validate_economic_gate(payload: Any) -> None:
    gate = _mapping(payload, field="economic_gate")
    expected = {
        "direction": "POSITIVE_NET_RETURN_ONLY",
        "minimum_mean_net_return": AR0002_MINIMUM_MEAN_NET_RETURN,
        "cost_scope": "OBSERVED_BID_ASK_SPREAD_ONLY",
        "role": "BINDING_CANDIDATE_SCREEN_GATE",
    }
    if gate != expected:
        raise AlphaDiscoveryConfigError(
            "AR-0002 economic gate must remain positive and at least 10 bps net."
        )


def _validate_multiple_testing(payload: Any) -> None:
    multiple = _mapping(payload, field="multiple_testing")
    expected = {
        "family_definition": [
            "feature_family",
            "horizon",
            "target",
            "direction",
            "preregistered_interaction",
        ],
        "methods": ["BH", "BY"],
        "global_family_scope": "ALL_PREREGISTERED_EFFECTS",
        "global_family_size": AR0002_EFFECT_COUNT,
        "failed_hypothesis_p_value": 1.0,
        "retain_failed_in_denominator": True,
        "binding_method": "GLOBAL_BY",
        "primary_fdr_alpha": 0.05,
        "local_fdr_alpha": 0.05,
        "local_methods_role": "DIAGNOSTIC_ONLY_NON_BINDING",
        "status": "IMPLEMENTED_FROZEN_CONTRACT",
    }
    if multiple != expected:
        raise AlphaDiscoveryConfigError(
            "AR-0002 must retain global BY over all 720 preregistered effects."
        )


def _validate_operational_sections(
    cfg: dict[str, Any], status: AlphaDiscoveryStatus
) -> None:
    gates = _mapping(cfg["promotion_gates"], field="promotion_gates")
    expected_gate_names = {
        "coverage",
        "effect_size",
        "temporal_stability",
        "execution_realism",
        "multiple_testing",
        "prospective_confirmation",
    }
    if set(gates) != expected_gate_names:
        raise AlphaDiscoveryConfigError("AR-0002 promotion gate family drifted.")
    for name, raw_gate in gates.items():
        gate = _mapping(raw_gate, field=f"promotion_gates.{name}")
        _exact_keys(gate, {"contract", "status"}, field=f"promotion_gates.{name}")
        _non_empty_string(gate["contract"], field=f"promotion_gates.{name}.contract")
        if gate["status"] != "NOT_EVALUATED":
            raise AlphaDiscoveryConfigError(
                f"promotion_gates.{name}.status must be NOT_EVALUATED."
            )

    artifacts = _mapping(cfg["artifacts"], field="artifacts")
    if artifacts != {
        "output_root": "logs/experiments/alpha_discovery",
        "layout_version": 2,
        "write_mode": "IMMUTABLE_RUN_DIRECTORY",
    }:
        raise AlphaDiscoveryConfigError("AR-0002 artifact layout contract drifted.")

    runtime = _mapping(cfg["runtime"], field="runtime")
    _exact_keys(
        runtime,
        {"perform_alpha_calculation", "run_backtests", "access_prospective_final"},
        field="runtime",
    )
    for name, value in runtime.items():
        _bool(value, field=f"runtime.{name}")
    if runtime["run_backtests"] or runtime["access_prospective_final"]:
        raise AlphaDiscoveryConfigError(
            "AR-0002 cannot run backtests or access prospective-final data."
        )
    if status is AlphaDiscoveryStatus.SPECIFICATION_ONLY:
        if runtime["perform_alpha_calculation"]:
            raise AlphaDiscoveryConfigError(
                "AR-0002 SPECIFICATION_ONLY cannot perform alpha calculation."
            )
    elif not runtime["perform_alpha_calculation"]:
        raise AlphaDiscoveryConfigError(
            "AR-0002 APPROVED_TO_RUN must perform alpha calculation."
        )

    blockers = cfg["blockers"]
    if not isinstance(blockers, list) or any(
        not isinstance(value, str) or not value.strip() for value in blockers
    ):
        raise AlphaDiscoveryConfigError("AR-0002 blockers must be non-empty strings.")
    if status is AlphaDiscoveryStatus.SPECIFICATION_ONLY and not blockers:
        raise AlphaDiscoveryConfigError("AR-0002 SPECIFICATION_ONLY needs a blocker.")
    if status is AlphaDiscoveryStatus.APPROVED_TO_RUN and blockers:
        raise AlphaDiscoveryConfigError("Approved AR-0002 cannot retain blockers.")


def validate_alpha_discovery_v2_config(cfg: dict[str, Any]) -> None:
    """Validate AR-0002 without weakening the frozen alpha_discovery_v1 path."""

    if not isinstance(cfg, dict):
        raise AlphaDiscoveryConfigError("AR-0002 config must be a mapping.")
    missing = sorted((_TOP_LEVEL_KEYS - {"config_path"}).difference(cfg))
    unexpected = sorted(set(cfg).difference(_TOP_LEVEL_KEYS))
    if missing or unexpected:
        raise AlphaDiscoveryConfigError(
            f"AR-0002 top-level keys mismatch; missing={missing}, unexpected={unexpected}."
        )
    if cfg["schema_version"] != 3 or isinstance(cfg["schema_version"], bool):
        raise AlphaDiscoveryConfigError("AR-0002 schema_version must be 3.")
    pipeline = _mapping(cfg["pipeline"], field="pipeline")
    if pipeline != {"kind": "alpha_discovery_v2", "stage": "PRE_SIGNAL_RESEARCH"}:
        raise AlphaDiscoveryConfigError(
            "AR-0002 pipeline must be alpha_discovery_v2 at PRE_SIGNAL_RESEARCH."
        )
    if not re.fullmatch(r"AR-[0-9]{4}", str(cfg["research_id"])):
        raise AlphaDiscoveryConfigError("research_id must match AR-0000.")
    if cfg["research_id"] != "AR-0002":
        raise AlphaDiscoveryConfigError("alpha_discovery_v2 is frozen for AR-0002.")

    status = _validate_approval(cfg)
    _validate_prior_research_context(cfg["prior_research_context"])
    _validate_scientific_contract(cfg["scientific_contract"])
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
    if cfg["horizons"] != list(AR0002_HORIZONS):
        raise AlphaDiscoveryConfigError("AR-0002 horizons must remain [16, 32, 64].")
    _validate_targets(cfg["targets_planned"])
    _validate_conditional_analysis(cfg["conditional_analysis"])
    _validate_economic_gate(cfg["economic_gate"])
    _validate_execution_measurement(cfg["execution_measurement"])
    _validate_statistics(cfg["statistics"])
    if cfg["statistics"]["block_bootstrap"]["resamples"] != 2000:
        raise AlphaDiscoveryConfigError("AR-0002 bootstrap resamples must remain 2000.")
    if cfg["statistics"]["block_bootstrap"]["seed"] != 29:
        raise AlphaDiscoveryConfigError("AR-0002 bootstrap seed must remain 29.")
    _validate_multiple_testing(cfg["multiple_testing"])
    _validate_operational_sections(cfg, status)

    declared_hash = _sha256(cfg["specification_hash"], field="specification_hash")
    computed_hash = compute_alpha_specification_hash(cfg)
    if declared_hash != computed_hash:
        raise AlphaDiscoveryConfigError(
            f"specification_hash mismatch: declared={declared_hash}, computed={computed_hash}."
        )
    if status is AlphaDiscoveryStatus.APPROVED_TO_RUN:
        approved_hash = _sha256(
            cfg["approval"]["approved_specification_hash"],
            field="approval.approved_specification_hash",
        )
        if approved_hash != computed_hash:
            raise AlphaDiscoveryConfigError(
                "AR-0002 approval is bound to a different specification hash."
            )


__all__ = [
    "AR0002_CONDITION_COUNT",
    "AR0002_CONTINUOUS_FEATURES",
    "AR0002_EFFECT_COUNT",
    "AR0002_HORIZONS",
    "AR0002_INTERACTION_PAIRS",
    "AR0002_MINIMUM_MEAN_NET_RETURN",
    "validate_alpha_discovery_v2_config",
]
