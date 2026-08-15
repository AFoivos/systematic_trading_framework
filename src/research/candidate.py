"""Neutral candidate representation emitted by research backends."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any

from .contracts import (
    EvidenceReference,
    ResearchContractError,
    _freeze_json_mapping,
    _require_non_empty,
)


class CandidateStatus(str, Enum):
    """Lifecycle states before and after framework-owned canonical validation."""

    SCREENED = "screened"
    PENDING_CANONICAL_VALIDATION = "pending_canonical_validation"
    CANONICALLY_VALIDATED = "canonically_validated"
    ROBUSTNESS_PENDING = "robustness_pending"
    ROBUSTNESS_PASSED = "robustness_passed"
    FINAL_HOLDOUT_PENDING = "final_holdout_pending"
    FINAL_HOLDOUT_PASSED = "final_holdout_passed"
    VALIDATED = "validated"
    REJECTED = "rejected"
    RETIRED = "retired"
    # Preserved only for serialized Phase 0 compatibility. New lifecycle code
    # promotes to VALIDATED and never emits this legacy state.
    PROMOTED = "promoted"


def _freeze_metrics(metrics: Mapping[str, int | float | None]) -> Mapping[str, int | float | None]:
    if not isinstance(metrics, Mapping):
        raise ResearchContractError("metrics must be a mapping.")
    copied: dict[str, int | float | None] = {}
    for key, value in metrics.items():
        clean_key = _require_non_empty(key, field_name="metrics key")
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(float(value))
        ):
            raise ResearchContractError(
                f"Metric {clean_key!r} must be a finite number or null."
            )
        copied[clean_key] = value
    return MappingProxyType(copied)


@dataclass(frozen=True)
class ResearchCandidate:
    """Backend-neutral description of a screened strategy candidate.

    The object carries references and serializable summaries only. It must not
    embed a VectorBT portfolio, PyBroker strategy, Qlib record, fitted estimator,
    or any other backend-native object.
    """

    candidate_id: str
    strategy_name: str
    backend: str
    config_reference: str
    assets: tuple[str, ...]
    timeframe: str
    sample_reference: str
    metrics: Mapping[str, int | float | None] = field(default_factory=dict)
    cost_assumptions: Mapping[str, Any] = field(default_factory=dict)
    search_metadata: Mapping[str, Any] = field(default_factory=dict)
    status: CandidateStatus = CandidateStatus.PENDING_CANONICAL_VALIDATION
    evidence_references: tuple[EvidenceReference, ...] = ()
    hypothesis_id: str | None = None
    research_run_id: str | None = None
    selection_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "candidate_id",
            "strategy_name",
            "backend",
            "config_reference",
            "timeframe",
            "sample_reference",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_non_empty(getattr(self, field_name), field_name=field_name),
            )
        if isinstance(self.assets, (str, bytes, bytearray)):
            raise ResearchContractError("assets must be a sequence of asset identifiers.")
        assets = tuple(
            _require_non_empty(item, field_name="assets item") for item in self.assets
        )
        if not assets:
            raise ResearchContractError("assets must contain at least one asset.")
        if len(set(assets)) != len(assets):
            raise ResearchContractError("assets cannot contain duplicates.")
        try:
            status = CandidateStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise ResearchContractError(str(exc)) from exc
        if isinstance(self.evidence_references, (str, bytes, bytearray)):
            raise ResearchContractError(
                "evidence_references must be a sequence of EvidenceReference values."
            )
        evidence_references = tuple(self.evidence_references)
        if any(not isinstance(item, EvidenceReference) for item in evidence_references):
            raise ResearchContractError(
                "evidence_references must contain only EvidenceReference values."
            )
        if len(set(evidence_references)) != len(evidence_references):
            raise ResearchContractError(
                "evidence_references cannot contain duplicates."
            )
        object.__setattr__(self, "assets", assets)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "metrics", _freeze_metrics(self.metrics))
        object.__setattr__(
            self,
            "cost_assumptions",
            _freeze_json_mapping(self.cost_assumptions, field_name="cost_assumptions"),
        )
        object.__setattr__(
            self,
            "search_metadata",
            _freeze_json_mapping(self.search_metadata, field_name="search_metadata"),
        )
        object.__setattr__(self, "evidence_references", evidence_references)
        for field_name in ("hypothesis_id", "research_run_id", "selection_id"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    _require_non_empty(value, field_name=field_name),
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "strategy_name": self.strategy_name,
            "backend": self.backend,
            "config_reference": self.config_reference,
            "assets": list(self.assets),
            "timeframe": self.timeframe,
            "sample_reference": self.sample_reference,
            "metrics": dict(self.metrics),
            "cost_assumptions": dict(self.cost_assumptions),
            "search_metadata": dict(self.search_metadata),
            "status": self.status.value,
            "evidence_references": [
                reference.to_dict() for reference in self.evidence_references
            ],
            "hypothesis_id": self.hypothesis_id,
            "research_run_id": self.research_run_id,
            "selection_id": self.selection_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ResearchCandidate:
        from .contracts import _require_exact_keys
        from .contracts import _require_json_array

        _require_exact_keys(
            payload,
            expected={
                "candidate_id",
                "strategy_name",
                "backend",
                "config_reference",
                "assets",
                "timeframe",
                "sample_reference",
                "metrics",
                "cost_assumptions",
                "search_metadata",
                "status",
                "evidence_references",
            },
            optional={"hypothesis_id", "research_run_id", "selection_id"},
            field_name="Research candidate",
        )
        return cls(
            candidate_id=payload["candidate_id"],
            strategy_name=payload["strategy_name"],
            backend=payload["backend"],
            config_reference=payload["config_reference"],
            assets=tuple(_require_json_array(payload["assets"], field_name="assets")),
            timeframe=payload["timeframe"],
            sample_reference=payload["sample_reference"],
            metrics=payload["metrics"],
            cost_assumptions=payload["cost_assumptions"],
            search_metadata=payload["search_metadata"],
            status=CandidateStatus(payload["status"]),
            evidence_references=tuple(
                EvidenceReference.from_dict(item)
                for item in _require_json_array(
                    payload["evidence_references"],
                    field_name="evidence_references",
                )
            ),
            hypothesis_id=payload.get("hypothesis_id"),
            research_run_id=payload.get("research_run_id"),
            selection_id=payload.get("selection_id"),
        )


__all__ = ["CandidateStatus", "ResearchCandidate"]
