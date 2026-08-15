"""Small orchestration-side factory for concrete discovery executors."""

from __future__ import annotations

from typing import Any

from src.research.contracts import ResearchContractError
from src.research.discovery.service import GridCandidateGenerator


def get_discovery_executor(name: str, **kwargs: Any) -> Any:
    """Resolve only implemented executors; never fall back silently."""

    if name == "grid":
        if kwargs:
            raise ResearchContractError(
                "GridCandidateGenerator does not accept constructor options."
            )
        return GridCandidateGenerator()
    if name == "optuna":
        from src.experiments.optuna_discovery import ExistingOptunaSearchExecutor

        return ExistingOptunaSearchExecutor(**kwargs)
    if name == "vectorbt":
        from src.research.backends.vectorbt import VectorBTSearchExecutor

        return VectorBTSearchExecutor(**kwargs)
    if name == "pybroker":
        from src.research.backends.pybroker import PyBrokerSearchExecutor

        return PyBrokerSearchExecutor(**kwargs)
    raise ResearchContractError(
        "Unknown discovery executor "
        f"{name!r}; available: grid, optuna, vectorbt, pybroker."
    )


__all__ = ["get_discovery_executor"]
