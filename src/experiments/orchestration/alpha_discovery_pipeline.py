from __future__ import annotations

"""Approval-gated execution boundary for preregistered alpha discovery."""

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from src.experiments.alpha_discovery_scanner import (
    AR0001_CONDITION_UNIVERSE,
    ConditionUniverse,
    ScannerSettings,
    fit_discovery_quintiles,
    scan_conditional_effects,
)
from src.experiments.alpha_discovery_targets import build_alpha_discovery_targets
from src.experiments.orchestration.alpha_discovery_artifacts import (
    AlphaDiscoveryArtifactLayout,
    AlphaDiscoveryArtifactResult,
    write_alpha_discovery_artifacts,
)
from src.features.alpha_discovery_primitives import build_alpha_discovery_features
from src.src_data.research_access import DiscoveryDataAccess, SnapshotReference
from src.src_data.research_roles import EvidenceRole
from src.utils.alpha_discovery_config import (
    AlphaDiscoveryStatus,
    validate_alpha_discovery_any_config,
)
from src.utils.config import load_experiment_config


class AlphaDiscoveryExecutionRefused(RuntimeError):
    """Fail-closed refusal for unapproved alpha-discovery research."""


@dataclass(frozen=True)
class AlphaDiscoveryRunResult:
    research_id: str
    specification_hash: str
    snapshot_id: str
    snapshot_sha256: str
    input_row_count: int
    conditional_effect_count: int
    eligible_inference_count: int
    bin_edge_hash: str
    artifacts: AlphaDiscoveryArtifactResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "research_id": self.research_id,
            "specification_hash": self.specification_hash,
            "snapshot_id": self.snapshot_id,
            "snapshot_sha256": self.snapshot_sha256,
            "input_row_count": self.input_row_count,
            "conditional_effect_count": self.conditional_effect_count,
            "eligible_inference_count": self.eligible_inference_count,
            "bin_edge_hash": self.bin_edge_hash,
            "run_root": str(self.artifacts.run_root),
            "run_manifest_path": str(self.artifacts.run_manifest_path),
            "run_identity_sha256": self.artifacts.run_identity_sha256,
        }


def _condition_universe(cfg: dict[str, Any]) -> ConditionUniverse:
    kind = str(cfg["pipeline"]["kind"])
    if kind == "alpha_discovery_v1":
        return AR0001_CONDITION_UNIVERSE
    if kind == "alpha_discovery_v2":
        from src.utils.alpha_discovery_v2_config import (
            AR0002_CONTINUOUS_FEATURES,
            AR0002_INTERACTION_PAIRS,
        )

        return ConditionUniverse(
            continuous_features=AR0002_CONTINUOUS_FEATURES,
            interaction_pairs=AR0002_INTERACTION_PAIRS,
        )
    raise AlphaDiscoveryExecutionRefused(
        f"Unsupported alpha-discovery pipeline kind: {kind!r}."
    )


def _build_features(cfg: dict[str, Any], frame: pd.DataFrame) -> pd.DataFrame:
    if cfg["pipeline"]["kind"] == "alpha_discovery_v1":
        return build_alpha_discovery_features(frame)
    from src.features.alpha_discovery_liquidity import (
        build_alpha_discovery_liquidity_features,
    )

    return build_alpha_discovery_liquidity_features(frame)


def _snapshot_reference(cfg: dict[str, Any]) -> SnapshotReference:
    raw = cfg["snapshot_reference"]
    return SnapshotReference(
        snapshot_id=str(raw["snapshot_id"]),
        manifest_path=Path(str(raw["manifest_path"])),
        expected_sha256=str(raw["expected_sha256"]),
        evidence_role=EvidenceRole(raw["evidence_role"]),
    )


def _validate_loaded_discovery_partition(
    cfg: dict[str, Any],
    *,
    loaded: Any,
) -> None:
    """Bind runtime access to the exact frozen discovery child, never its parent."""

    reference = cfg["snapshot_reference"]
    if loaded.manifest.row_count != int(reference["expected_row_count"]):
        raise AlphaDiscoveryExecutionRefused(
            "Discovery child row count differs from the frozen specification."
        )
    if loaded.manifest.first_timestamp != reference["expected_first_timestamp"]:
        raise AlphaDiscoveryExecutionRefused(
            "Discovery child first timestamp differs from the frozen specification."
        )
    if loaded.manifest.last_timestamp != reference["expected_last_timestamp"]:
        raise AlphaDiscoveryExecutionRefused(
            "Discovery child last timestamp differs from the frozen specification."
        )
    timestamps = pd.to_datetime(loaded.frame["timestamp"], utc=True, errors="raise")
    start = pd.Timestamp(reference["partition_start_inclusive"])
    end = pd.Timestamp(reference["partition_end_exclusive"])
    if timestamps.duplicated().any() or not timestamps.is_monotonic_increasing:
        raise AlphaDiscoveryExecutionRefused(
            "Discovery child timestamps must be unique and sorted."
        )
    if not (timestamps.ge(start) & timestamps.lt(end)).all():
        raise AlphaDiscoveryExecutionRefused(
            "Discovery child contains a timestamp outside its frozen historical partition."
        )
    lineage = loaded.manifest.config_version.get("historical_partition")
    expected_lineage = {
        "schema_version": 1,
        "parent_snapshot_id": reference["parent_snapshot_id"],
        "parent_sha256": reference["parent_sha256"],
        "cutoff_utc": cfg["historical_partition"]["cutoff_utc"],
        "assignment_rule": cfg["historical_partition"]["assignment_rule"],
        "partition_role": "DISCOVERY",
        "partition_start_inclusive": reference["partition_start_inclusive"],
        "partition_end_exclusive": reference["partition_end_exclusive"],
        "row_count": reference["expected_row_count"],
    }
    if not isinstance(lineage, dict) or any(
        lineage.get(key) != value for key, value in expected_lineage.items()
    ):
        raise AlphaDiscoveryExecutionRefused(
            "Discovery child lineage differs from the frozen parent/cutoff contract."
        )


def execute_approved_alpha_discovery(
    cfg: dict[str, Any],
    *,
    discovery_access: DiscoveryDataAccess,
) -> AlphaDiscoveryRunResult:
    """Measure the frozen discovery family without prospective or signal access."""

    validate_alpha_discovery_any_config(cfg)
    if AlphaDiscoveryStatus(cfg["status"]) is not AlphaDiscoveryStatus.APPROVED_TO_RUN:
        raise AlphaDiscoveryExecutionRefused(
            "Alpha discovery refused: status must be APPROVED_TO_RUN."
        )
    if not isinstance(discovery_access, DiscoveryDataAccess):
        raise TypeError("Alpha discovery requires DiscoveryDataAccess.")

    layout = AlphaDiscoveryArtifactLayout.from_config(cfg)
    if layout.run_root.exists():
        raise AlphaDiscoveryExecutionRefused(
            "Alpha discovery refused before data access: immutable run directory "
            f"already exists at {layout.run_root}."
        )
    loaded = discovery_access.load_discovery(_snapshot_reference(cfg))
    _validate_loaded_discovery_partition(cfg, loaded=loaded)
    universe = _condition_universe(cfg)
    features = _build_features(cfg, loaded.frame)
    targets = build_alpha_discovery_targets(
        loaded.frame,
        horizons=cfg["horizons"],
    )
    frozen_bins = fit_discovery_quintiles(
        features,
        snapshot_id=loaded.manifest.snapshot_id,
        specification_hash=cfg["specification_hash"],
        continuous_features=universe.continuous_features,
    )
    scan = scan_conditional_effects(
        features,
        targets,
        frozen_bins=frozen_bins,
        settings=ScannerSettings.from_config(
            cfg["statistics"],
            cfg["multiple_testing"],
            cfg.get("economic_gate"),
        ),
        horizons=cfg["horizons"],
        universe=universe,
        allowed_horizons=cfg["horizons"],
    )
    artifact_result = write_alpha_discovery_artifacts(
        layout=layout,
        cfg=cfg,
        loaded=loaded,
        scan=scan,
    )
    eligible_count = int((scan.effects["inference_status"] == "ELIGIBLE").sum())
    return AlphaDiscoveryRunResult(
        research_id=str(cfg["research_id"]),
        specification_hash=str(cfg["specification_hash"]),
        snapshot_id=loaded.manifest.snapshot_id,
        snapshot_sha256=loaded.manifest.sha256,
        input_row_count=int(len(loaded.frame)),
        conditional_effect_count=int(len(scan.effects)),
        eligible_inference_count=eligible_count,
        bin_edge_hash=frozen_bins.edge_hash,
        artifacts=artifact_result,
    )


def run_alpha_discovery_pipeline(
    config_path: str | Path,
) -> AlphaDiscoveryRunResult:
    cfg = load_experiment_config(config_path)
    validate_alpha_discovery_any_config(cfg)
    if AlphaDiscoveryStatus(cfg["status"]) is not AlphaDiscoveryStatus.APPROVED_TO_RUN:
        raise AlphaDiscoveryExecutionRefused(
            "Alpha discovery refused before data access: configuration status is "
            f"{cfg['status']}, not APPROVED_TO_RUN."
        )
    return execute_approved_alpha_discovery(
        cfg,
        discovery_access=DiscoveryDataAccess(),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an explicitly approved frozen alpha-discovery specification."
    )
    parser.add_argument(
        "--config", required=True, help="Path to AR specification YAML."
    )
    args = parser.parse_args(argv)
    result = run_alpha_discovery_pipeline(args.config)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AlphaDiscoveryArtifactLayout",
    "AlphaDiscoveryExecutionRefused",
    "AlphaDiscoveryRunResult",
    "execute_approved_alpha_discovery",
    "main",
    "run_alpha_discovery_pipeline",
]
