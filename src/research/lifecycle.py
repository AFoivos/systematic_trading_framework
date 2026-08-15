"""Guarded candidate transitions driven by evidence completeness."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from types import MappingProxyType

from .candidate import CandidateStatus, ResearchCandidate
from .contracts import ResearchContractError, _require_sha256
from .decisions import DecisionKind, PromotionDecision
from .evidence import (
    CanonicalValidationRecord,
    CheckStatus,
    EvidenceRecord,
    require_usable_final_holdout,
)
from .robustness import MinimumEvidencePolicy, RobustnessRecord


_ALLOWED_TRANSITIONS: Mapping[CandidateStatus, frozenset[CandidateStatus]] = (
    MappingProxyType(
        {
            CandidateStatus.SCREENED: frozenset(
                {
                    CandidateStatus.PENDING_CANONICAL_VALIDATION,
                    CandidateStatus.REJECTED,
                    CandidateStatus.RETIRED,
                }
            ),
            CandidateStatus.PENDING_CANONICAL_VALIDATION: frozenset(
                {CandidateStatus.CANONICALLY_VALIDATED, CandidateStatus.REJECTED}
            ),
            CandidateStatus.CANONICALLY_VALIDATED: frozenset(
                {
                    CandidateStatus.ROBUSTNESS_PENDING,
                    CandidateStatus.FINAL_HOLDOUT_PENDING,
                    CandidateStatus.VALIDATED,
                    CandidateStatus.REJECTED,
                }
            ),
            CandidateStatus.ROBUSTNESS_PENDING: frozenset(
                {CandidateStatus.ROBUSTNESS_PASSED, CandidateStatus.REJECTED}
            ),
            CandidateStatus.ROBUSTNESS_PASSED: frozenset(
                {
                    CandidateStatus.FINAL_HOLDOUT_PENDING,
                    CandidateStatus.VALIDATED,
                    CandidateStatus.REJECTED,
                }
            ),
            CandidateStatus.FINAL_HOLDOUT_PENDING: frozenset(
                {CandidateStatus.FINAL_HOLDOUT_PASSED, CandidateStatus.REJECTED}
            ),
            CandidateStatus.FINAL_HOLDOUT_PASSED: frozenset(
                {CandidateStatus.VALIDATED, CandidateStatus.REJECTED}
            ),
            CandidateStatus.VALIDATED: frozenset({CandidateStatus.RETIRED}),
            CandidateStatus.REJECTED: frozenset({CandidateStatus.RETIRED}),
            CandidateStatus.RETIRED: frozenset(),
            CandidateStatus.PROMOTED: frozenset({CandidateStatus.RETIRED}),
        }
    )
)


def require_transition_allowed(
    current: CandidateStatus | str,
    target: CandidateStatus | str,
) -> None:
    try:
        current_status = CandidateStatus(current)
        target_status = CandidateStatus(target)
    except (TypeError, ValueError) as exc:
        raise ResearchContractError(str(exc)) from exc
    if target_status not in _ALLOWED_TRANSITIONS[current_status]:
        raise ResearchContractError(
            f"Invalid candidate transition {current_status.value} -> "
            f"{target_status.value}."
        )


def _unique_records(records: Iterable[object], *, id_field: str) -> tuple[object, ...]:
    values = tuple(records)
    ids = tuple(getattr(item, id_field, None) for item in values)
    if any(value is None for value in ids) or len(set(ids)) != len(ids):
        raise ResearchContractError(f"{id_field} values must be present and unique.")
    return values


def _passing_validation(
    candidate_id: str,
    *,
    validations: Iterable[CanonicalValidationRecord],
    current_specification_hash: str,
) -> CanonicalValidationRecord:
    records = _unique_records(validations, id_field="validation_id")
    if any(not isinstance(item, CanonicalValidationRecord) for item in records):
        raise ResearchContractError(
            "validations must contain CanonicalValidationRecord values."
        )
    matches = tuple(
        item
        for item in records
        if item.candidate_id == candidate_id
        and item.status is CheckStatus.PASS
        and item.specification_hash == current_specification_hash
    )
    if not matches:
        raise ResearchContractError(
            "A passing canonical OOS validation for the current specification is required."
        )
    return matches[-1]


def _passing_robustness(
    candidate_id: str,
    *,
    validation: CanonicalValidationRecord,
    records: Iterable[RobustnessRecord],
    policy: MinimumEvidencePolicy,
) -> RobustnessRecord:
    values = _unique_records(records, id_field="robustness_id")
    if any(not isinstance(item, RobustnessRecord) for item in values):
        raise ResearchContractError(
            "robustness_records must contain RobustnessRecord values."
        )
    matches = tuple(
        item
        for item in values
        if item.candidate_id == candidate_id
        and item.validation_id == validation.validation_id
        and item.status is CheckStatus.PASS
    )
    for record in reversed(matches):
        if all(
            (check := record.check_by_name(name)) is not None
            and check.status is CheckStatus.PASS
            for name in policy.required_robustness_checks
        ):
            return record
    raise ResearchContractError(
        "A passing robustness record with all policy-required checks is required."
    )


def _passing_final_holdout(
    candidate_id: str,
    *,
    evidence_records: Iterable[EvidenceRecord],
    current_specification_hash: str,
    material_changes_after_evaluation: Iterable[str],
) -> EvidenceRecord:
    records = _unique_records(evidence_records, id_field="evidence_id")
    if any(not isinstance(item, EvidenceRecord) for item in records):
        raise ResearchContractError(
            "evidence_records must contain EvidenceRecord values."
        )
    failures: list[str] = []
    for evidence in reversed(records):
        if evidence.candidate_id != candidate_id:
            continue
        try:
            require_usable_final_holdout(
                evidence,
                current_specification_hash=current_specification_hash,
                material_changes_after_evaluation=material_changes_after_evaluation,
            )
        except ResearchContractError as exc:
            failures.append(str(exc))
            continue
        if any(
            status in {CheckStatus.FAIL, CheckStatus.NOT_RUN}
            for status in evidence.validation_checks.values()
        ):
            failures.append("Final-holdout validation checks did not pass.")
            continue
        return evidence
    suffix = f" Last refusal: {failures[-1]}" if failures else ""
    raise ResearchContractError(
        "Usable prospective final-holdout evidence is required." + suffix
    )


def transition_candidate(
    candidate: ResearchCandidate,
    target_status: CandidateStatus | str,
    *,
    policy: MinimumEvidencePolicy | None = None,
    validations: Iterable[CanonicalValidationRecord] = (),
    robustness_records: Iterable[RobustnessRecord] = (),
    evidence_records: Iterable[EvidenceRecord] = (),
    current_specification_hash: str | None = None,
    material_changes_after_final: Iterable[str] = (),
) -> ResearchCandidate:
    """Return a new candidate snapshot only when the requested stage is supported."""

    if not isinstance(candidate, ResearchCandidate):
        raise ResearchContractError("candidate must be a ResearchCandidate.")
    target = CandidateStatus(target_status)
    require_transition_allowed(candidate.status, target)
    evidence_gated = {
        CandidateStatus.CANONICALLY_VALIDATED,
        CandidateStatus.ROBUSTNESS_PASSED,
        CandidateStatus.FINAL_HOLDOUT_PASSED,
        CandidateStatus.VALIDATED,
    }
    spec_hash: str | None = None
    if target in evidence_gated:
        spec_hash = _require_sha256(
            current_specification_hash,
            field_name="current_specification_hash",
        )
    active_policy = policy or MinimumEvidencePolicy()
    validation: CanonicalValidationRecord | None = None
    if target in {
        CandidateStatus.CANONICALLY_VALIDATED,
        CandidateStatus.ROBUSTNESS_PASSED,
        CandidateStatus.VALIDATED,
    }:
        validation = _passing_validation(
            candidate.candidate_id,
            validations=validations,
            current_specification_hash=spec_hash,
        )
    if target is CandidateStatus.ROBUSTNESS_PASSED:
        _passing_robustness(
            candidate.candidate_id,
            validation=validation,
            records=robustness_records,
            policy=active_policy,
        )
    if target is CandidateStatus.FINAL_HOLDOUT_PASSED:
        _passing_final_holdout(
            candidate.candidate_id,
            evidence_records=evidence_records,
            current_specification_hash=spec_hash,
            material_changes_after_evaluation=material_changes_after_final,
        )
    if target is CandidateStatus.VALIDATED:
        if active_policy.require_robustness:
            _passing_robustness(
                candidate.candidate_id,
                validation=validation,
                records=robustness_records,
                policy=active_policy,
            )
        if active_policy.require_final_holdout:
            _passing_final_holdout(
                candidate.candidate_id,
                evidence_records=evidence_records,
                current_specification_hash=spec_hash,
                material_changes_after_evaluation=material_changes_after_final,
            )
    return replace(candidate, status=target)


def apply_promotion_decision(
    candidate: ResearchCandidate,
    decision: PromotionDecision,
    **transition_context: object,
) -> ResearchCandidate:
    """Apply a recorded decision through the same evidence-gated transition path."""

    if not isinstance(decision, PromotionDecision):
        raise ResearchContractError("decision must be a PromotionDecision.")
    if decision.candidate_id != candidate.candidate_id:
        raise ResearchContractError("Decision candidate_id does not match candidate.")
    if decision.from_status is not candidate.status:
        raise ResearchContractError("Decision from_status does not match candidate status.")
    if decision.decision is DecisionKind.HOLD:
        return candidate
    updated = transition_candidate(
        candidate,
        decision.to_status,
        **transition_context,
    )
    validation_ids = {
        item.validation_id
        for item in transition_context.get("validations", ())
        if isinstance(item, CanonicalValidationRecord)
    }
    robustness_ids = {
        item.robustness_id
        for item in transition_context.get("robustness_records", ())
        if isinstance(item, RobustnessRecord)
    }
    evidence_ids = {
        item.evidence_id
        for item in transition_context.get("evidence_records", ())
        if isinstance(item, EvidenceRecord)
    }
    referenced = set(decision.evidence_references)
    unknown = referenced.difference(validation_ids | robustness_ids | evidence_ids)
    if unknown:
        raise ResearchContractError(
            f"Decision references unknown evidence record ids: {sorted(unknown)}."
        )
    target = decision.to_status
    if target is CandidateStatus.CANONICALLY_VALIDATED and not referenced.intersection(
        validation_ids
    ):
        raise ResearchContractError(
            "Canonical-validation promotion decision must reference a validation record."
        )
    if target is CandidateStatus.ROBUSTNESS_PASSED and (
        not referenced.intersection(validation_ids)
        or not referenced.intersection(robustness_ids)
    ):
        raise ResearchContractError(
            "Robustness promotion decision must reference validation and robustness records."
        )
    if target is CandidateStatus.FINAL_HOLDOUT_PASSED and not referenced.intersection(
        evidence_ids
    ):
        raise ResearchContractError(
            "Final-holdout promotion decision must reference a final evidence record."
        )
    if target is CandidateStatus.VALIDATED:
        active_policy = transition_context.get("policy") or MinimumEvidencePolicy()
        if not isinstance(active_policy, MinimumEvidencePolicy):
            raise ResearchContractError("policy must be a MinimumEvidencePolicy.")
        if not referenced.intersection(validation_ids):
            raise ResearchContractError(
                "Validation decision must reference canonical validation evidence."
            )
        if active_policy.require_robustness and not referenced.intersection(
            robustness_ids
        ):
            raise ResearchContractError(
                "Validation decision must reference policy-required robustness evidence."
            )
        if active_policy.require_final_holdout and not referenced.intersection(
            evidence_ids
        ):
            raise ResearchContractError(
                "Validation decision must reference policy-required final evidence."
            )
    return updated


def candidate_lifecycle_schema() -> dict[str, object]:
    return {
        "statuses": [status.value for status in CandidateStatus],
        "allowed_transitions": {
            status.value: sorted(target.value for target in targets)
            for status, targets in _ALLOWED_TRANSITIONS.items()
        },
        "legacy_statuses": [CandidateStatus.PROMOTED.value],
    }


__all__ = [
    "apply_promotion_decision",
    "candidate_lifecycle_schema",
    "require_transition_allowed",
    "transition_candidate",
]
