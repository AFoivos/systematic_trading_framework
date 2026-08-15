"""Auditable selection context for converting backend results to candidates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from .candidate import CandidateStatus, ResearchCandidate
from .contracts import (
    ResearchContractError,
    ResearchResult,
    _require_exact_keys,
    _require_identifier,
    _require_non_empty,
    _require_timestamp,
)
from .run import ResearchRun, ResearchRunStatus, SelectionDirection


@dataclass(frozen=True)
class SelectionRecord:
    """Why one portable result was selected from a broader search."""

    selection_id: str
    research_run_id: str
    candidate_id: str
    evaluated_alternatives: int
    selection_metric: str
    selection_direction: SelectionDirection
    candidate_rank: int
    tie_break_rule: str
    selected_at: str

    def __post_init__(self) -> None:
        for field_name in ("selection_id", "research_run_id", "candidate_id"):
            object.__setattr__(
                self,
                field_name,
                _require_identifier(getattr(self, field_name), field_name=field_name),
            )
        for field_name in ("selection_metric", "tie_break_rule"):
            object.__setattr__(
                self,
                field_name,
                _require_non_empty(getattr(self, field_name), field_name=field_name),
            )
        if (
            isinstance(self.evaluated_alternatives, bool)
            or not isinstance(self.evaluated_alternatives, int)
            or self.evaluated_alternatives < 1
        ):
            raise ResearchContractError(
                "evaluated_alternatives must be an integer >= 1."
            )
        if (
            isinstance(self.candidate_rank, bool)
            or not isinstance(self.candidate_rank, int)
            or not 1 <= self.candidate_rank <= self.evaluated_alternatives
        ):
            raise ResearchContractError(
                "candidate_rank must be between 1 and evaluated_alternatives."
            )
        try:
            direction = SelectionDirection(self.selection_direction)
        except (TypeError, ValueError) as exc:
            raise ResearchContractError(str(exc)) from exc
        object.__setattr__(self, "selection_direction", direction)
        object.__setattr__(
            self,
            "selected_at",
            _require_timestamp(self.selected_at, field_name="selected_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "selection_id": self.selection_id,
            "research_run_id": self.research_run_id,
            "candidate_id": self.candidate_id,
            "evaluated_alternatives": self.evaluated_alternatives,
            "selection_metric": self.selection_metric,
            "selection_direction": self.selection_direction.value,
            "candidate_rank": self.candidate_rank,
            "tie_break_rule": self.tie_break_rule,
            "selected_at": self.selected_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SelectionRecord:
        expected = {
            "selection_id",
            "research_run_id",
            "candidate_id",
            "evaluated_alternatives",
            "selection_metric",
            "selection_direction",
            "candidate_rank",
            "tie_break_rule",
            "selected_at",
        }
        _require_exact_keys(payload, expected=expected, field_name="Selection record")
        return cls(
            selection_id=payload["selection_id"],
            research_run_id=payload["research_run_id"],
            candidate_id=payload["candidate_id"],
            evaluated_alternatives=payload["evaluated_alternatives"],
            selection_metric=payload["selection_metric"],
            selection_direction=SelectionDirection(payload["selection_direction"]),
            candidate_rank=payload["candidate_rank"],
            tie_break_rule=payload["tie_break_rule"],
            selected_at=payload["selected_at"],
        )


def candidate_from_research_result(
    result: ResearchResult,
    *,
    research_run: ResearchRun,
    selection: SelectionRecord,
) -> ResearchCandidate:
    """Create a linked candidate using only the result's portable fields."""

    if not isinstance(result, ResearchResult):
        raise ResearchContractError("result must be a ResearchResult.")
    if not isinstance(research_run, ResearchRun):
        raise ResearchContractError("research_run must be a ResearchRun.")
    if not isinstance(selection, SelectionRecord):
        raise ResearchContractError("selection must be a SelectionRecord.")
    if research_run.status is not ResearchRunStatus.COMPLETED:
        raise ResearchContractError("Candidates can be selected only from a completed run.")
    if result.request_id != research_run.request_id:
        raise ResearchContractError("ResearchResult request_id does not match ResearchRun.")
    if result.backend != research_run.backend:
        raise ResearchContractError("ResearchResult backend does not match ResearchRun.")
    if selection.research_run_id != research_run.research_run_id:
        raise ResearchContractError("SelectionRecord does not reference ResearchRun.")
    if (
        selection.evaluated_alternatives
        != research_run.search_metadata.evaluated_alternatives
    ):
        raise ResearchContractError(
            "SelectionRecord evaluated_alternatives differs from the run search breadth."
        )
    if selection.selection_metric != research_run.search_metadata.selection_metric:
        raise ResearchContractError("Selection metric differs from ResearchRun metadata.")
    if (
        selection.selection_direction
        is not research_run.search_metadata.selection_direction
    ):
        raise ResearchContractError("Selection direction differs from ResearchRun metadata.")
    matches = tuple(
        candidate
        for candidate in result.candidates
        if candidate.candidate_id == selection.candidate_id
    )
    if len(matches) != 1:
        raise ResearchContractError(
            "SelectionRecord must identify exactly one candidate in ResearchResult."
        )
    if selection.candidate_id not in research_run.candidate_ids:
        raise ResearchContractError("Selected candidate is not linked by ResearchRun.")
    source = matches[0]
    portable_search_metadata = dict(source.search_metadata)
    portable_search_metadata.update(
        {
            "evaluated_alternatives": selection.evaluated_alternatives,
            "selection_metric": selection.selection_metric,
            "selection_direction": selection.selection_direction.value,
            "candidate_rank": selection.candidate_rank,
            "tie_break_rule": selection.tie_break_rule,
        }
    )
    return replace(
        source,
        status=CandidateStatus.SCREENED,
        hypothesis_id=research_run.hypothesis_id,
        research_run_id=research_run.research_run_id,
        selection_id=selection.selection_id,
        search_metadata=portable_search_metadata,
    )


__all__ = ["SelectionRecord", "candidate_from_research_result"]
