from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.src_data.research_access import DiscoveryDataAccess
from src.utils.alpha_discovery_config import (
    AlphaDiscoveryStatus,
    validate_alpha_discovery_config,
)
from src.utils.config import load_experiment_config


class AlphaDiscoveryExecutionRefused(RuntimeError):
    """Fail-closed refusal for unapproved or not-yet-implemented research."""


@dataclass(frozen=True)
class AlphaDiscoveryArtifactLayout:
    """Versioned layout under the existing experiment artifact root."""

    run_root: Path
    contracts: Path
    data_quality: Path
    snapshots: Path
    hypotheses: Path
    registry: Path
    reports: Path

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> AlphaDiscoveryArtifactLayout:
        validate_alpha_discovery_config(cfg)
        research_id = str(cfg["research_id"])
        specification_hash = str(cfg["specification_hash"])
        output_root = Path(str(cfg["artifacts"]["output_root"]))
        run_root = output_root / research_id / specification_hash[:16]
        return cls(
            run_root=run_root,
            contracts=run_root / "contracts",
            data_quality=run_root / "data_quality",
            snapshots=run_root / "snapshots",
            hypotheses=run_root / "hypotheses",
            registry=run_root / "registry",
            reports=run_root / "reports",
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "run_root": str(self.run_root),
            "contracts": str(self.contracts),
            "data_quality": str(self.data_quality),
            "snapshots": str(self.snapshots),
            "hypotheses": str(self.hypotheses),
            "registry": str(self.registry),
            "reports": str(self.reports),
        }


def execute_approved_alpha_discovery(
    cfg: dict[str, Any],
    *,
    discovery_access: DiscoveryDataAccess,
) -> None:
    """Typed future boundary: discovery receives no prospective access object."""

    validate_alpha_discovery_config(cfg)
    if AlphaDiscoveryStatus(cfg["status"]) is not AlphaDiscoveryStatus.APPROVED_TO_RUN:
        raise AlphaDiscoveryExecutionRefused(
            "Alpha discovery refused: status must be APPROVED_TO_RUN."
        )
    if not isinstance(discovery_access, DiscoveryDataAccess):
        raise TypeError("Future alpha discovery requires DiscoveryDataAccess.")
    raise AlphaDiscoveryExecutionRefused(
        "Alpha discovery execution is intentionally unavailable in PHASE 0-2; "
        "the scanner, statistics, and signal stages are not implemented."
    )


def run_alpha_discovery_pipeline(config_path: str | Path) -> None:
    cfg = load_experiment_config(config_path)
    validate_alpha_discovery_config(cfg)
    if AlphaDiscoveryStatus(cfg["status"]) is not AlphaDiscoveryStatus.APPROVED_TO_RUN:
        raise AlphaDiscoveryExecutionRefused(
            "Alpha discovery refused before data access: configuration status is "
            f"{cfg['status']}, not APPROVED_TO_RUN."
        )
    execute_approved_alpha_discovery(cfg, discovery_access=DiscoveryDataAccess())


__all__ = [
    "AlphaDiscoveryArtifactLayout",
    "AlphaDiscoveryExecutionRefused",
    "execute_approved_alpha_discovery",
    "run_alpha_discovery_pipeline",
]
