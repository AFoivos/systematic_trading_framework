"""Backend-neutral research-run and search-breadth contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .contracts import (
    EvidenceReference,
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


class SelectionDirection(str, Enum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class ResearchRunStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class SearchMetadata:
    """Serializable search breadth without coupling to an optimizer library."""

    search_method: str
    requested_trials: int
    completed_trials: int
    failed_trials: int
    evaluated_alternatives: int
    candidate_count: int
    parameter_dimensions: tuple[str, ...] = ()
    selection_metric: str | None = None
    selection_direction: SelectionDirection | None = None
    random_seed: int | None = None
    study_name: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "search_method",
            _require_non_empty(self.search_method, field_name="search_method"),
        )
        for field_name in (
            "requested_trials",
            "completed_trials",
            "failed_trials",
            "evaluated_alternatives",
            "candidate_count",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchContractError(f"{field_name} must be an integer >= 0.")
        if self.completed_trials + self.failed_trials > self.requested_trials:
            raise ResearchContractError(
                "completed_trials + failed_trials cannot exceed requested_trials."
            )
        if self.evaluated_alternatives > self.completed_trials:
            raise ResearchContractError(
                "evaluated_alternatives cannot exceed completed_trials."
            )
        if self.candidate_count > self.evaluated_alternatives:
            raise ResearchContractError(
                "candidate_count cannot exceed evaluated_alternatives."
            )
        object.__setattr__(
            self,
            "parameter_dimensions",
            _require_unique_strings(
                self.parameter_dimensions,
                field_name="parameter_dimensions",
            ),
        )
        if (self.selection_metric is None) is not (
            self.selection_direction is None
        ):
            raise ResearchContractError(
                "selection_metric and selection_direction must be supplied together."
            )
        if self.selection_metric is not None:
            object.__setattr__(
                self,
                "selection_metric",
                _require_non_empty(
                    self.selection_metric,
                    field_name="selection_metric",
                ),
            )
            try:
                direction = SelectionDirection(self.selection_direction)
            except (TypeError, ValueError) as exc:
                raise ResearchContractError(str(exc)) from exc
            object.__setattr__(self, "selection_direction", direction)
        if self.random_seed is not None and (
            isinstance(self.random_seed, bool)
            or not isinstance(self.random_seed, int)
            or self.random_seed < 0
        ):
            raise ResearchContractError("random_seed must be null or an integer >= 0.")
        if self.study_name is not None:
            object.__setattr__(
                self,
                "study_name",
                _require_non_empty(self.study_name, field_name="study_name"),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "search_method": self.search_method,
            "requested_trials": self.requested_trials,
            "completed_trials": self.completed_trials,
            "failed_trials": self.failed_trials,
            "evaluated_alternatives": self.evaluated_alternatives,
            "candidate_count": self.candidate_count,
            "parameter_dimensions": list(self.parameter_dimensions),
            "selection_metric": self.selection_metric,
            "selection_direction": (
                None
                if self.selection_direction is None
                else self.selection_direction.value
            ),
            "random_seed": self.random_seed,
            "study_name": self.study_name,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SearchMetadata:
        expected = {
            "search_method",
            "requested_trials",
            "completed_trials",
            "failed_trials",
            "evaluated_alternatives",
            "candidate_count",
            "parameter_dimensions",
            "selection_metric",
            "selection_direction",
            "random_seed",
            "study_name",
        }
        _require_exact_keys(payload, expected=expected, field_name="Search metadata")
        return cls(
            search_method=payload["search_method"],
            requested_trials=payload["requested_trials"],
            completed_trials=payload["completed_trials"],
            failed_trials=payload["failed_trials"],
            evaluated_alternatives=payload["evaluated_alternatives"],
            candidate_count=payload["candidate_count"],
            parameter_dimensions=tuple(
                _require_json_array(
                    payload["parameter_dimensions"],
                    field_name="parameter_dimensions",
                )
            ),
            selection_metric=payload["selection_metric"],
            selection_direction=(
                None
                if payload["selection_direction"] is None
                else SelectionDirection(payload["selection_direction"])
            ),
            random_seed=payload["random_seed"],
            study_name=payload["study_name"],
        )


@dataclass(frozen=True)
class ResearchRun:
    """One reproducible execution linking a hypothesis, request, data, and output."""

    research_run_id: str
    hypothesis_id: str
    request_id: str
    backend: str
    started_at: str
    status: ResearchRunStatus
    config_reference: str
    config_hash: str
    dataset_reference: str
    dataset_fingerprint: Mapping[str, Any]
    evidence_reference: EvidenceReference
    search_metadata: SearchMetadata
    completed_at: str | None = None
    backend_version: str | None = None
    artifact_references: tuple[str, ...] = ()
    candidate_ids: tuple[str, ...] = ()
    git_revision: str | None = None
    random_seed: int | None = None
    runtime_mode: str | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("research_run_id", "hypothesis_id", "request_id"):
            object.__setattr__(
                self,
                field_name,
                _require_identifier(getattr(self, field_name), field_name=field_name),
            )
        for field_name in (
            "backend",
            "config_reference",
            "dataset_reference",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_non_empty(getattr(self, field_name), field_name=field_name),
            )
        object.__setattr__(
            self,
            "started_at",
            _require_timestamp(self.started_at, field_name="started_at"),
        )
        object.__setattr__(
            self,
            "config_hash",
            _require_sha256(self.config_hash, field_name="config_hash"),
        )
        try:
            status = ResearchRunStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise ResearchContractError(str(exc)) from exc
        object.__setattr__(self, "status", status)
        if not isinstance(self.evidence_reference, EvidenceReference):
            raise ResearchContractError(
                "evidence_reference must be an EvidenceReference value."
            )
        if not isinstance(self.search_metadata, SearchMetadata):
            raise ResearchContractError("search_metadata must be SearchMetadata.")
        fingerprint = _freeze_json_mapping(
            self.dataset_fingerprint,
            field_name="dataset_fingerprint",
        )
        digest = fingerprint.get("sha256")
        _require_sha256(digest, field_name="dataset_fingerprint.sha256")
        object.__setattr__(self, "dataset_fingerprint", fingerprint)
        terminal = {
            ResearchRunStatus.COMPLETED,
            ResearchRunStatus.FAILED,
            ResearchRunStatus.CANCELLED,
        }
        if (status in terminal) is not (self.completed_at is not None):
            raise ResearchContractError(
                "Terminal research runs require completed_at; non-terminal runs forbid it."
            )
        if self.completed_at is not None:
            completed = _require_timestamp(self.completed_at, field_name="completed_at")
            if datetime.fromisoformat(completed.replace("Z", "+00:00")) < datetime.fromisoformat(
                self.started_at.replace("Z", "+00:00")
            ):
                raise ResearchContractError("completed_at cannot precede started_at.")
            object.__setattr__(self, "completed_at", completed)
        if status is ResearchRunStatus.COMPLETED and (
            len(self.candidate_ids) != self.search_metadata.candidate_count
        ):
            raise ResearchContractError(
                "Completed run candidate_ids must match search_metadata.candidate_count."
            )
        for field_name in ("backend_version", "git_revision", "runtime_mode"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    _require_non_empty(value, field_name=field_name),
                )
        if self.random_seed is not None and (
            isinstance(self.random_seed, bool)
            or not isinstance(self.random_seed, int)
            or self.random_seed < 0
        ):
            raise ResearchContractError("random_seed must be null or an integer >= 0.")
        if (
            self.random_seed is not None
            and self.search_metadata.random_seed is not None
            and self.random_seed != self.search_metadata.random_seed
        ):
            raise ResearchContractError(
                "ResearchRun random_seed must match SearchMetadata random_seed."
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
            "candidate_ids",
            _require_unique_strings(self.candidate_ids, field_name="candidate_ids"),
        )
        object.__setattr__(
            self,
            "provenance",
            _freeze_json_mapping(self.provenance, field_name="provenance"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "research_run_id": self.research_run_id,
            "hypothesis_id": self.hypothesis_id,
            "request_id": self.request_id,
            "backend": self.backend,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status.value,
            "config_reference": self.config_reference,
            "config_hash": self.config_hash,
            "dataset_reference": self.dataset_reference,
            "dataset_fingerprint": dict(self.dataset_fingerprint),
            "evidence_reference": self.evidence_reference.to_dict(),
            "search_metadata": self.search_metadata.to_dict(),
            "backend_version": self.backend_version,
            "artifact_references": list(self.artifact_references),
            "candidate_ids": list(self.candidate_ids),
            "git_revision": self.git_revision,
            "random_seed": self.random_seed,
            "runtime_mode": self.runtime_mode,
            "provenance": dict(self.provenance),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ResearchRun:
        expected = {
            "research_run_id",
            "hypothesis_id",
            "request_id",
            "backend",
            "started_at",
            "completed_at",
            "status",
            "config_reference",
            "config_hash",
            "dataset_reference",
            "dataset_fingerprint",
            "evidence_reference",
            "search_metadata",
            "backend_version",
            "artifact_references",
            "candidate_ids",
            "git_revision",
            "random_seed",
            "runtime_mode",
            "provenance",
        }
        _require_exact_keys(payload, expected=expected, field_name="Research run")
        return cls(
            research_run_id=payload["research_run_id"],
            hypothesis_id=payload["hypothesis_id"],
            request_id=payload["request_id"],
            backend=payload["backend"],
            started_at=payload["started_at"],
            completed_at=payload["completed_at"],
            status=ResearchRunStatus(payload["status"]),
            config_reference=payload["config_reference"],
            config_hash=payload["config_hash"],
            dataset_reference=payload["dataset_reference"],
            dataset_fingerprint=payload["dataset_fingerprint"],
            evidence_reference=EvidenceReference.from_dict(
                payload["evidence_reference"]
            ),
            search_metadata=SearchMetadata.from_dict(payload["search_metadata"]),
            backend_version=payload["backend_version"],
            artifact_references=tuple(
                _require_json_array(
                    payload["artifact_references"],
                    field_name="artifact_references",
                )
            ),
            candidate_ids=tuple(
                _require_json_array(
                    payload["candidate_ids"], field_name="candidate_ids"
                )
            ),
            git_revision=payload["git_revision"],
            random_seed=payload["random_seed"],
            runtime_mode=payload["runtime_mode"],
            provenance=payload["provenance"],
        )


__all__ = [
    "ResearchRun",
    "ResearchRunStatus",
    "SearchMetadata",
    "SelectionDirection",
]
