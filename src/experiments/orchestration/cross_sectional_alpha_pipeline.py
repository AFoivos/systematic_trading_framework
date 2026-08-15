"""Fail-closed runner boundary for AR-0003 cross-sectional research."""

from __future__ import annotations

from pathlib import Path

from src.utils.alpha_discovery_config import AlphaDiscoveryStatus
from src.utils.alpha_discovery_v3_config import validate_alpha_discovery_v3_config
from src.utils.config import load_experiment_config


class CrossSectionalAlphaExecutionRefused(RuntimeError):
    """Raised before data access when AR-0003 is not execution-ready."""


def run_alpha_discovery_v3_pipeline(config_path: str | Path) -> None:
    """Validate AR-0003, then refuse unless the complete runtime is approved.

    The checked-in specification deliberately has unresolved universe, panel,
    executable-target, cost, and multiple-testing bindings.  This boundary is
    registered so the stable runner fails with an actionable research refusal
    rather than falling through to the canonical experiment or touching data.
    """

    cfg = load_experiment_config(config_path)
    validate_alpha_discovery_v3_config(cfg)
    if AlphaDiscoveryStatus(cfg["status"]) is not AlphaDiscoveryStatus.APPROVED_TO_RUN:
        raise CrossSectionalAlphaExecutionRefused(
            "AR-0003 refused before data access: status is SPECIFICATION_ONLY. "
            "Bind a canonical asset universe, validated DISCOVERY panel, executable "
            "target/cost mapping, statistical policy, resource preflight, and exact "
            "human approval before requesting a run."
        )
    raise CrossSectionalAlphaExecutionRefused(
        "AR-0003 approved execution is not implemented by this specification-only "
        "boundary; do not bypass it with raw data or the canonical runner."
    )


__all__ = [
    "CrossSectionalAlphaExecutionRefused",
    "run_alpha_discovery_v3_pipeline",
]
