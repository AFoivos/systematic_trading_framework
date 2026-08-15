"""Small persistence protocol kept independent of a database or service."""

from __future__ import annotations

from typing import Protocol

from ..candidate import ResearchCandidate


class CandidateStore(Protocol):
    def save_candidate(self, candidate: ResearchCandidate) -> None: ...

    def load_candidate(self, candidate_id: str) -> ResearchCandidate: ...

    def list_candidates(self) -> tuple[ResearchCandidate, ...]: ...


__all__ = ["CandidateStore"]
