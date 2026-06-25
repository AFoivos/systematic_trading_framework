from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.experiments.runner import ExperimentResult


def run_canonical_pipeline(config_path: str | Path) -> "ExperimentResult":
    """
    Run the canonical config-driven experiment pipeline.

    This is the public pipeline facade for the end-to-end workflow:
    data loading/PIT hardening, feature generation, model training, signal
    generation, optional target diagnostics, backtesting, reporting, monitoring,
    and execution output.
    """
    from src.experiments.runner import run_experiment

    return run_experiment(config_path)


__all__ = ["run_canonical_pipeline"]
