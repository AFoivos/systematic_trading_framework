"""Approval-gated AR-0003 cross-sectional discovery runner."""

from __future__ import annotations

from pathlib import Path

from src.utils.alpha_discovery_config import AlphaDiscoveryStatus
from src.utils.alpha_discovery_v3_config import validate_alpha_discovery_v3_config
from src.utils.config import load_experiment_config
from src.utils.paths import PROJECT_ROOT


class CrossSectionalAlphaExecutionRefused(RuntimeError):
    """Raised before data access when AR-0003 is not execution-ready."""


def run_alpha_discovery_v3_pipeline(config_path: str | Path) -> dict[str, object]:
    """Run the frozen deterministic family using DISCOVERY sources only."""

    cfg = load_experiment_config(config_path)
    validate_alpha_discovery_v3_config(cfg)
    if AlphaDiscoveryStatus(cfg["status"]) is not AlphaDiscoveryStatus.APPROVED_TO_RUN:
        raise CrossSectionalAlphaExecutionRefused(
            "AR-0003 refused before data access: status is SPECIFICATION_ONLY. "
            "Bind frozen sources, target/cost semantics, inference policy, resource "
            "limits, and an exact specification-hash approval before requesting a run."
        )
    from src.experiments.orchestration.ar0003_artifacts import (
        ar0003_run_root,
        write_ar0003_artifacts,
    )
    from src.research.ar0003_runtime import build_ar0003_panel, evaluate_ar0003

    run_root = ar0003_run_root(cfg)
    if run_root.exists():
        raise CrossSectionalAlphaExecutionRefused(
            "AR-0003 refused before data access because the immutable run directory "
            f"already exists: {run_root}."
        )
    built = build_ar0003_panel(cfg, project_root=PROJECT_ROOT)
    evaluation = evaluate_ar0003(cfg, built)
    return write_ar0003_artifacts(cfg=cfg, built=built, evaluation=evaluation)


__all__ = [
    "CrossSectionalAlphaExecutionRefused",
    "run_alpha_discovery_v3_pipeline",
]
