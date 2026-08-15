"""Canonical-validation request boundary for selected discovery candidates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from src.src_data.research_roles import EvidenceRole

from ..candidate import CandidateStatus, ResearchCandidate
from ..contracts import (
    EvidenceStage,
    ResearchContractError,
    _freeze_json_mapping,
    _require_exact_keys,
    _require_identifier,
    _require_non_empty,
    _require_sha256,
    _require_timestamp,
)
from ..lifecycle import transition_candidate
from .contracts import DiscoverySpecification


@dataclass(frozen=True)
class CanonicalValidationRequest:
    """Portable request for replay by the existing canonical experiment pipeline.

    The request intentionally does not contain or load validation data. The
    orchestration owner must resolve a role-bound ``VALIDATION`` snapshot after
    the candidate has been frozen. This prevents discovery/ranking code from
    receiving validation or prospective-final samples.
    """

    request_id: str
    candidate_id: str
    hypothesis_id: str
    research_run_id: str
    discovery_specification_hash: str
    experiment_config_reference: str
    config_hash: str
    validation_method: str
    required_evidence_stage: EvidenceStage
    required_evidence_role: EvidenceRole
    candidate_parameters: Mapping[str, Any]
    discovery_dataset_fingerprint: Mapping[str, Any]
    cost_assumptions: Mapping[str, Any]
    created_at: str

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "candidate_id",
            "hypothesis_id",
            "research_run_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_identifier(getattr(self, field_name), field_name=field_name),
            )
        object.__setattr__(
            self,
            "discovery_specification_hash",
            _require_sha256(
                self.discovery_specification_hash,
                field_name="discovery_specification_hash",
            ),
        )
        object.__setattr__(
            self,
            "experiment_config_reference",
            _require_non_empty(
                self.experiment_config_reference,
                field_name="experiment_config_reference",
            ),
        )
        object.__setattr__(
            self,
            "config_hash",
            _require_sha256(self.config_hash, field_name="config_hash"),
        )
        method = _require_non_empty(
            self.validation_method, field_name="validation_method"
        )
        if method != "canonical_experiment":
            raise ResearchContractError(
                "Canonical validation requests must target canonical_experiment."
            )
        object.__setattr__(self, "validation_method", method)
        try:
            stage = EvidenceStage(self.required_evidence_stage)
            role = EvidenceRole(self.required_evidence_role)
        except (TypeError, ValueError) as exc:
            raise ResearchContractError(str(exc)) from exc
        if stage is not EvidenceStage.VALIDATION or role is not EvidenceRole.VALIDATION:
            raise ResearchContractError(
                "Canonical validation requests require validation/VALIDATION evidence."
            )
        object.__setattr__(self, "required_evidence_stage", stage)
        object.__setattr__(self, "required_evidence_role", role)
        object.__setattr__(
            self,
            "candidate_parameters",
            _freeze_json_mapping(
                self.candidate_parameters, field_name="candidate_parameters"
            ),
        )
        fingerprint = _freeze_json_mapping(
            self.discovery_dataset_fingerprint,
            field_name="discovery_dataset_fingerprint",
        )
        _require_sha256(
            fingerprint.get("sha256"),
            field_name="discovery_dataset_fingerprint.sha256",
        )
        object.__setattr__(self, "discovery_dataset_fingerprint", fingerprint)
        object.__setattr__(
            self,
            "cost_assumptions",
            _freeze_json_mapping(
                self.cost_assumptions, field_name="cost_assumptions"
            ),
        )
        object.__setattr__(
            self,
            "created_at",
            _require_timestamp(self.created_at, field_name="created_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "candidate_id": self.candidate_id,
            "hypothesis_id": self.hypothesis_id,
            "research_run_id": self.research_run_id,
            "discovery_specification_hash": self.discovery_specification_hash,
            "experiment_config_reference": self.experiment_config_reference,
            "config_hash": self.config_hash,
            "validation_method": self.validation_method,
            "required_evidence_stage": self.required_evidence_stage.value,
            "required_evidence_role": self.required_evidence_role.value,
            "candidate_parameters": dict(self.candidate_parameters),
            "discovery_dataset_fingerprint": dict(
                self.discovery_dataset_fingerprint
            ),
            "cost_assumptions": dict(self.cost_assumptions),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CanonicalValidationRequest:
        expected = {
            "request_id",
            "candidate_id",
            "hypothesis_id",
            "research_run_id",
            "discovery_specification_hash",
            "experiment_config_reference",
            "config_hash",
            "validation_method",
            "required_evidence_stage",
            "required_evidence_role",
            "candidate_parameters",
            "discovery_dataset_fingerprint",
            "cost_assumptions",
            "created_at",
        }
        _require_exact_keys(
            payload,
            expected=expected,
            field_name="Canonical validation request",
        )
        return cls(
            request_id=payload["request_id"],
            candidate_id=payload["candidate_id"],
            hypothesis_id=payload["hypothesis_id"],
            research_run_id=payload["research_run_id"],
            discovery_specification_hash=payload["discovery_specification_hash"],
            experiment_config_reference=payload["experiment_config_reference"],
            config_hash=payload["config_hash"],
            validation_method=payload["validation_method"],
            required_evidence_stage=EvidenceStage(
                payload["required_evidence_stage"]
            ),
            required_evidence_role=EvidenceRole(
                payload["required_evidence_role"]
            ),
            candidate_parameters=payload["candidate_parameters"],
            discovery_dataset_fingerprint=payload[
                "discovery_dataset_fingerprint"
            ],
            cost_assumptions=payload["cost_assumptions"],
            created_at=payload["created_at"],
        )


def prepare_canonical_validation(
    candidate: ResearchCandidate,
    *,
    specification: DiscoverySpecification,
    request_id: str,
    candidate_parameters: Mapping[str, Any],
    created_at: str,
) -> tuple[ResearchCandidate, CanonicalValidationRequest]:
    """Freeze a selected candidate at the canonical-validation boundary."""

    if not isinstance(candidate, ResearchCandidate):
        raise ResearchContractError("candidate must be a ResearchCandidate.")
    if not isinstance(specification, DiscoverySpecification):
        raise ResearchContractError(
            "specification must be a DiscoverySpecification."
        )
    if candidate.status is not CandidateStatus.SCREENED:
        raise ResearchContractError(
            "Only SCREENED candidates can enter canonical validation."
        )
    if candidate.hypothesis_id != specification.hypothesis_id:
        raise ResearchContractError(
            "Candidate hypothesis_id differs from discovery specification."
        )
    if candidate.config_reference != specification.config_reference:
        raise ResearchContractError(
            "Candidate config reference differs from discovery specification."
        )
    if candidate.sample_reference != specification.dataset_reference:
        raise ResearchContractError(
            "Candidate sample reference differs from discovery specification."
        )
    if candidate.assets != specification.assets or candidate.timeframe != specification.timeframe:
        raise ResearchContractError(
            "Candidate asset/timeframe context differs from discovery specification."
        )
    if dict(candidate.cost_assumptions) != dict(specification.cost_assumptions):
        raise ResearchContractError(
            "Candidate cost assumptions differ from discovery specification."
        )
    if candidate.research_run_id is None:
        raise ResearchContractError(
            "Selected candidate must reference its research run."
        )
    request = CanonicalValidationRequest(
        request_id=request_id,
        candidate_id=candidate.candidate_id,
        hypothesis_id=specification.hypothesis_id,
        research_run_id=candidate.research_run_id,
        discovery_specification_hash=specification.specification_hash,
        experiment_config_reference=specification.config_reference,
        config_hash=specification.config_hash,
        validation_method=specification.validation_method,
        required_evidence_stage=EvidenceStage.VALIDATION,
        required_evidence_role=EvidenceRole.VALIDATION,
        candidate_parameters=candidate_parameters,
        discovery_dataset_fingerprint=specification.dataset_fingerprint,
        cost_assumptions=specification.cost_assumptions,
        created_at=created_at,
    )
    pending = transition_candidate(
        candidate, CandidateStatus.PENDING_CANONICAL_VALIDATION
    )
    return pending, request


__all__ = ["CanonicalValidationRequest", "prepare_canonical_validation"]
