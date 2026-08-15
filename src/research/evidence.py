"""Framework-owned evidence and canonical-validation records."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from math import isclose
from types import MappingProxyType
from typing import Any

from .candidate import _freeze_metrics
from .contracts import (
    EvidenceReference,
    EvidenceStage,
    ResearchContractError,
    _freeze_json_mapping,
    _require_exact_keys,
    _require_identifier,
    _require_json_array,
    _require_non_empty,
    _require_sha256,
    _require_timestamp,
    _require_unique_strings,
)


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    NOT_RUN = "not_run"


def _freeze_check_mapping(
    checks: Mapping[str, CheckStatus | str],
    *,
    field_name: str,
) -> Mapping[str, CheckStatus]:
    if not isinstance(checks, Mapping):
        raise ResearchContractError(f"{field_name} must be a mapping.")
    normalized: dict[str, CheckStatus] = {}
    for name, raw_status in checks.items():
        clean_name = _require_non_empty(name, field_name=f"{field_name} key")
        try:
            normalized[clean_name] = CheckStatus(raw_status)
        except (TypeError, ValueError) as exc:
            raise ResearchContractError(str(exc)) from exc
    return MappingProxyType(normalized)


@dataclass(frozen=True)
class EvidenceRecord:
    """One immutable evidence observation for a candidate and frozen sample."""

    evidence_id: str
    candidate_id: str
    evidence_reference: EvidenceReference
    metrics: Mapping[str, int | float | None]
    specification_hash: str
    recorded_at: str
    artifact_references: tuple[str, ...] = ()
    cost_assumptions: Mapping[str, Any] = field(default_factory=dict)
    timing_assumptions: Mapping[str, Any] = field(default_factory=dict)
    validation_checks: Mapping[str, CheckStatus | str] = field(default_factory=dict)
    used_for_tuning: bool = False

    def __post_init__(self) -> None:
        for field_name in ("evidence_id", "candidate_id"):
            object.__setattr__(
                self,
                field_name,
                _require_identifier(getattr(self, field_name), field_name=field_name),
            )
        if not isinstance(self.evidence_reference, EvidenceReference):
            raise ResearchContractError(
                "evidence_reference must be an EvidenceReference value."
            )
        object.__setattr__(self, "metrics", _freeze_metrics(self.metrics))
        object.__setattr__(
            self,
            "specification_hash",
            _require_sha256(self.specification_hash, field_name="specification_hash"),
        )
        object.__setattr__(
            self,
            "recorded_at",
            _require_timestamp(self.recorded_at, field_name="recorded_at"),
        )
        object.__setattr__(
            self,
            "artifact_references",
            _require_unique_strings(
                self.artifact_references,
                field_name="artifact_references",
            ),
        )
        object.__setattr__(
            self,
            "cost_assumptions",
            _freeze_json_mapping(self.cost_assumptions, field_name="cost_assumptions"),
        )
        object.__setattr__(
            self,
            "timing_assumptions",
            _freeze_json_mapping(
                self.timing_assumptions,
                field_name="timing_assumptions",
            ),
        )
        object.__setattr__(
            self,
            "validation_checks",
            _freeze_check_mapping(
                self.validation_checks,
                field_name="validation_checks",
            ),
        )
        if not isinstance(self.used_for_tuning, bool):
            raise ResearchContractError("used_for_tuning must be boolean.")
        if (
            self.evidence_reference.stage is EvidenceStage.FINAL_HOLDOUT
            and self.used_for_tuning
        ):
            raise ResearchContractError(
                "Final-holdout evidence cannot be marked as used_for_tuning."
            )

    @property
    def stage(self) -> EvidenceStage:
        return self.evidence_reference.stage

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "candidate_id": self.candidate_id,
            "evidence_reference": self.evidence_reference.to_dict(),
            "metrics": dict(self.metrics),
            "specification_hash": self.specification_hash,
            "recorded_at": self.recorded_at,
            "artifact_references": list(self.artifact_references),
            "cost_assumptions": dict(self.cost_assumptions),
            "timing_assumptions": dict(self.timing_assumptions),
            "validation_checks": {
                name: status.value for name, status in self.validation_checks.items()
            },
            "used_for_tuning": self.used_for_tuning,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> EvidenceRecord:
        expected = {
            "evidence_id",
            "candidate_id",
            "evidence_reference",
            "metrics",
            "specification_hash",
            "recorded_at",
            "artifact_references",
            "cost_assumptions",
            "timing_assumptions",
            "validation_checks",
            "used_for_tuning",
        }
        _require_exact_keys(payload, expected=expected, field_name="Evidence record")
        return cls(
            evidence_id=payload["evidence_id"],
            candidate_id=payload["candidate_id"],
            evidence_reference=EvidenceReference.from_dict(
                payload["evidence_reference"]
            ),
            metrics=payload["metrics"],
            specification_hash=payload["specification_hash"],
            recorded_at=payload["recorded_at"],
            artifact_references=tuple(
                _require_json_array(
                    payload["artifact_references"],
                    field_name="artifact_references",
                )
            ),
            cost_assumptions=payload["cost_assumptions"],
            timing_assumptions=payload["timing_assumptions"],
            validation_checks=payload["validation_checks"],
            used_for_tuning=payload["used_for_tuning"],
        )


def require_usable_final_holdout(
    evidence: EvidenceRecord,
    *,
    current_specification_hash: str,
    material_changes_after_evaluation: Iterable[str] = (),
) -> None:
    """Fail closed when prospective evidence has been tuned on or contaminated."""

    if not isinstance(evidence, EvidenceRecord):
        raise ResearchContractError("evidence must be an EvidenceRecord.")
    current_hash = _require_sha256(
        current_specification_hash,
        field_name="current_specification_hash",
    )
    if evidence.stage is not EvidenceStage.FINAL_HOLDOUT:
        raise ResearchContractError("Evidence is not final-holdout evidence.")
    # EvidenceReference already guarantees PROSPECTIVE_FINAL for this stage.
    if evidence.used_for_tuning:
        raise ResearchContractError("Final-holdout evidence was used for tuning.")
    if evidence.specification_hash != current_hash:
        raise ResearchContractError(
            "Final-holdout evidence belongs to a different specification hash."
        )
    changes = tuple(material_changes_after_evaluation)
    if changes:
        raise ResearchContractError(
            "Final-holdout evidence was consumed by later material specification changes: "
            f"{changes}. A new prospective clock/sample is required."
        )


@dataclass(frozen=True)
class CanonicalValidationRecord:
    """Canonical OOS replay outcome under explicit timing and transaction costs."""

    validation_id: str
    candidate_id: str
    experiment_config_reference: str
    config_hash: str
    specification_hash: str
    dataset_reference: str
    dataset_fingerprint: Mapping[str, Any]
    oos_rows: int
    prediction_rows: int
    oos_coverage: float
    oos_marker: str
    cost_assumptions: Mapping[str, Any]
    timing_assumptions: Mapping[str, Any]
    metrics: Mapping[str, int | float | None]
    status: CheckStatus
    validated_at: str
    test_references: tuple[str, ...] = ()
    artifact_references: tuple[str, ...] = ()
    failure_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("validation_id", "candidate_id"):
            object.__setattr__(
                self,
                field_name,
                _require_identifier(getattr(self, field_name), field_name=field_name),
            )
        for field_name in (
            "experiment_config_reference",
            "dataset_reference",
            "oos_marker",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_non_empty(getattr(self, field_name), field_name=field_name),
            )
        object.__setattr__(
            self,
            "config_hash",
            _require_sha256(self.config_hash, field_name="config_hash"),
        )
        object.__setattr__(
            self,
            "specification_hash",
            _require_sha256(self.specification_hash, field_name="specification_hash"),
        )
        for field_name in ("oos_rows", "prediction_rows"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchContractError(f"{field_name} must be an integer >= 0.")
        if self.prediction_rows > self.oos_rows:
            raise ResearchContractError("prediction_rows cannot exceed oos_rows.")
        if (
            isinstance(self.oos_coverage, bool)
            or not isinstance(self.oos_coverage, (int, float))
            or not 0.0 <= float(self.oos_coverage) <= 1.0
        ):
            raise ResearchContractError("oos_coverage must be a finite value in [0, 1].")
        expected_coverage = (
            0.0 if self.oos_rows == 0 else self.prediction_rows / self.oos_rows
        )
        if not isclose(float(self.oos_coverage), expected_coverage, abs_tol=1e-12):
            raise ResearchContractError(
                "oos_coverage must equal prediction_rows / oos_rows."
            )
        try:
            status = CheckStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise ResearchContractError(str(exc)) from exc
        object.__setattr__(self, "status", status)
        if status not in {CheckStatus.PASS, CheckStatus.FAIL, CheckStatus.NOT_RUN}:
            raise ResearchContractError(
                "Canonical validation status must be pass, fail, or not_run."
            )
        object.__setattr__(
            self,
            "validated_at",
            _require_timestamp(self.validated_at, field_name="validated_at"),
        )
        fingerprint = _freeze_json_mapping(
            self.dataset_fingerprint,
            field_name="dataset_fingerprint",
        )
        _require_sha256(
            fingerprint.get("sha256"),
            field_name="dataset_fingerprint.sha256",
        )
        object.__setattr__(self, "dataset_fingerprint", fingerprint)
        object.__setattr__(self, "metrics", _freeze_metrics(self.metrics))
        object.__setattr__(
            self,
            "cost_assumptions",
            _freeze_json_mapping(self.cost_assumptions, field_name="cost_assumptions"),
        )
        object.__setattr__(
            self,
            "timing_assumptions",
            _freeze_json_mapping(
                self.timing_assumptions,
                field_name="timing_assumptions",
            ),
        )
        for field_name in (
            "test_references",
            "artifact_references",
            "failure_reasons",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_unique_strings(
                    getattr(self, field_name),
                    field_name=field_name,
                ),
            )
        if status is CheckStatus.PASS:
            if self.oos_rows == 0 or self.prediction_rows == 0:
                raise ResearchContractError(
                    "Passed canonical validation requires OOS predictions."
                )
            if not self.metrics or not self.cost_assumptions or not self.timing_assumptions:
                raise ResearchContractError(
                    "Passed canonical validation requires metrics, cost assumptions, "
                    "and timing assumptions."
                )
            if self.failure_reasons:
                raise ResearchContractError(
                    "Passed canonical validation cannot have failure_reasons."
                )
        if status is CheckStatus.FAIL and not self.failure_reasons:
            raise ResearchContractError(
                "Failed canonical validation requires failure_reasons."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "candidate_id": self.candidate_id,
            "experiment_config_reference": self.experiment_config_reference,
            "config_hash": self.config_hash,
            "specification_hash": self.specification_hash,
            "dataset_reference": self.dataset_reference,
            "dataset_fingerprint": dict(self.dataset_fingerprint),
            "oos_rows": self.oos_rows,
            "prediction_rows": self.prediction_rows,
            "oos_coverage": float(self.oos_coverage),
            "oos_marker": self.oos_marker,
            "cost_assumptions": dict(self.cost_assumptions),
            "timing_assumptions": dict(self.timing_assumptions),
            "metrics": dict(self.metrics),
            "status": self.status.value,
            "validated_at": self.validated_at,
            "test_references": list(self.test_references),
            "artifact_references": list(self.artifact_references),
            "failure_reasons": list(self.failure_reasons),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CanonicalValidationRecord:
        expected = {
            "validation_id",
            "candidate_id",
            "experiment_config_reference",
            "config_hash",
            "specification_hash",
            "dataset_reference",
            "dataset_fingerprint",
            "oos_rows",
            "prediction_rows",
            "oos_coverage",
            "oos_marker",
            "cost_assumptions",
            "timing_assumptions",
            "metrics",
            "status",
            "validated_at",
            "test_references",
            "artifact_references",
            "failure_reasons",
        }
        _require_exact_keys(
            payload,
            expected=expected,
            field_name="Canonical validation record",
        )
        return cls(
            validation_id=payload["validation_id"],
            candidate_id=payload["candidate_id"],
            experiment_config_reference=payload["experiment_config_reference"],
            config_hash=payload["config_hash"],
            specification_hash=payload["specification_hash"],
            dataset_reference=payload["dataset_reference"],
            dataset_fingerprint=payload["dataset_fingerprint"],
            oos_rows=payload["oos_rows"],
            prediction_rows=payload["prediction_rows"],
            oos_coverage=payload["oos_coverage"],
            oos_marker=payload["oos_marker"],
            cost_assumptions=payload["cost_assumptions"],
            timing_assumptions=payload["timing_assumptions"],
            metrics=payload["metrics"],
            status=CheckStatus(payload["status"]),
            validated_at=payload["validated_at"],
            test_references=tuple(
                _require_json_array(
                    payload["test_references"], field_name="test_references"
                )
            ),
            artifact_references=tuple(
                _require_json_array(
                    payload["artifact_references"],
                    field_name="artifact_references",
                )
            ),
            failure_reasons=tuple(
                _require_json_array(
                    payload["failure_reasons"], field_name="failure_reasons"
                )
            ),
        )


__all__ = [
    "CanonicalValidationRecord",
    "CheckStatus",
    "EvidenceRecord",
    "require_usable_final_holdout",
]
