"""Auditable candidate promotion, rejection, hold, and retirement decisions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .candidate import CandidateStatus
from .contracts import (
    ResearchContractError,
    _require_exact_keys,
    _require_identifier,
    _require_json_array,
    _require_non_empty,
    _require_timestamp,
    _require_unique_strings,
)


class DecisionKind(str, Enum):
    PROMOTE = "promote"
    REJECT = "reject"
    HOLD = "hold"
    RETIRE = "retire"


@dataclass(frozen=True)
class PromotionDecision:
    decision_id: str
    candidate_id: str
    from_status: CandidateStatus
    to_status: CandidateStatus
    decision: DecisionKind
    reason: str
    evidence_references: tuple[str, ...]
    decided_at: str
    decided_by: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("decision_id", "candidate_id"):
            object.__setattr__(
                self,
                field_name,
                _require_identifier(getattr(self, field_name), field_name=field_name),
            )
        try:
            from_status = CandidateStatus(self.from_status)
            to_status = CandidateStatus(self.to_status)
            decision = DecisionKind(self.decision)
        except (TypeError, ValueError) as exc:
            raise ResearchContractError(str(exc)) from exc
        object.__setattr__(self, "from_status", from_status)
        object.__setattr__(self, "to_status", to_status)
        object.__setattr__(self, "decision", decision)
        object.__setattr__(
            self,
            "reason",
            _require_non_empty(self.reason, field_name="reason"),
        )
        object.__setattr__(
            self,
            "evidence_references",
            _require_unique_strings(
                self.evidence_references,
                field_name="evidence_references",
            ),
        )
        object.__setattr__(
            self,
            "decided_at",
            _require_timestamp(self.decided_at, field_name="decided_at"),
        )
        if self.decided_by is not None:
            object.__setattr__(
                self,
                "decided_by",
                _require_non_empty(self.decided_by, field_name="decided_by"),
            )
        if decision is DecisionKind.REJECT and to_status is not CandidateStatus.REJECTED:
            raise ResearchContractError("A reject decision must target REJECTED.")
        if decision is DecisionKind.RETIRE and to_status is not CandidateStatus.RETIRED:
            raise ResearchContractError("A retire decision must target RETIRED.")
        if decision is DecisionKind.HOLD and to_status is not from_status:
            raise ResearchContractError("A hold decision cannot change candidate status.")
        if decision is DecisionKind.PROMOTE and to_status in {
            CandidateStatus.REJECTED,
            CandidateStatus.RETIRED,
        }:
            raise ResearchContractError(
                "A promote decision cannot target REJECTED or RETIRED."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "candidate_id": self.candidate_id,
            "from_status": self.from_status.value,
            "to_status": self.to_status.value,
            "decision": self.decision.value,
            "reason": self.reason,
            "evidence_references": list(self.evidence_references),
            "decided_at": self.decided_at,
            "decided_by": self.decided_by,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> PromotionDecision:
        expected = {
            "decision_id",
            "candidate_id",
            "from_status",
            "to_status",
            "decision",
            "reason",
            "evidence_references",
            "decided_at",
            "decided_by",
        }
        _require_exact_keys(payload, expected=expected, field_name="Promotion decision")
        return cls(
            decision_id=payload["decision_id"],
            candidate_id=payload["candidate_id"],
            from_status=CandidateStatus(payload["from_status"]),
            to_status=CandidateStatus(payload["to_status"]),
            decision=DecisionKind(payload["decision"]),
            reason=payload["reason"],
            evidence_references=tuple(
                _require_json_array(
                    payload["evidence_references"],
                    field_name="evidence_references",
                )
            ),
            decided_at=payload["decided_at"],
            decided_by=payload["decided_by"],
        )


__all__ = ["DecisionKind", "PromotionDecision"]
