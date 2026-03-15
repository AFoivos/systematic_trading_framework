from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .contracts import (
    DataContract,
    TargetContract,
    validate_data_contract,
    validate_feature_target_contract,
)

if TYPE_CHECKING:
    from .runner import ExperimentResult


def __getattr__(name: str) -> Any:
    """
    Lazily expose runner symbols so package imports do not trigger orchestration-side circular
    imports during config and registry loading.
    """
    if name in {"ExperimentResult", "run_experiment"}:
        from .runner import ExperimentResult, run_experiment

        exports = {
            "ExperimentResult": ExperimentResult,
            "run_experiment": run_experiment,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "ExperimentResult",
    "run_experiment",
    "DataContract",
    "TargetContract",
    "validate_data_contract",
    "validate_feature_target_contract",
]
