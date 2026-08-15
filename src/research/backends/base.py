"""Minimal protocol implemented by future optional research adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.research.contracts import ResearchRequest, ResearchResult


@runtime_checkable
class ResearchBackend(Protocol):
    """Run a portable request and return framework-owned result contracts."""

    @property
    def name(self) -> str:
        """Stable backend identifier used in candidate provenance."""
        ...

    @property
    def capabilities(self) -> frozenset[str]:
        """Explicit capability names; callers must not assume feature parity."""
        ...

    def run(self, request: ResearchRequest) -> ResearchResult:
        """Execute screening without exposing backend-native objects."""
        ...


__all__ = ["ResearchBackend"]
