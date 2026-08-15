from __future__ import annotations

"""Immutable artifact persistence for approved alpha-discovery measurements."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping

import yaml

from src.experiments.alpha_discovery_scanner import ConditionalScanResult
from src.src_data.research_access import LoadedResearchData
from src.utils.alpha_discovery_config import validate_alpha_discovery_any_config
from src.utils.run_metadata import (
    collect_git_metadata,
    compute_config_hash,
    file_sha256,
)


class AlphaDiscoveryArtifactError(RuntimeError):
    """Raised when an immutable alpha-discovery run cannot be persisted."""


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
        validate_alpha_discovery_any_config(cfg)
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


@dataclass(frozen=True)
class AlphaDiscoveryArtifactResult:
    run_root: Path
    run_manifest_path: Path
    run_identity_sha256: str
    artifact_sha256: dict[str, str]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _relative_layout(root: Path) -> AlphaDiscoveryArtifactLayout:
    return AlphaDiscoveryArtifactLayout(
        run_root=root,
        contracts=root / "contracts",
        data_quality=root / "data_quality",
        snapshots=root / "snapshots",
        hypotheses=root / "hypotheses",
        registry=root / "registry",
        reports=root / "reports",
    )


def _artifact_hashes(root: Path, paths: list[Path]) -> dict[str, str]:
    return {
        str(path.relative_to(root)): file_sha256(path)
        for path in sorted(paths, key=lambda item: str(item.relative_to(root)))
    }


def write_alpha_discovery_artifacts(
    *,
    layout: AlphaDiscoveryArtifactLayout,
    cfg: dict[str, Any],
    loaded: LoadedResearchData,
    scan: ConditionalScanResult,
) -> AlphaDiscoveryArtifactResult:
    """Persist a complete run once, atomically, without mutable result files."""

    validate_alpha_discovery_any_config(cfg)
    if layout.run_root.exists():
        raise AlphaDiscoveryArtifactError(
            "Immutable alpha-discovery run directory already exists: "
            f"{layout.run_root}"
        )
    parent = layout.run_root.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{layout.run_root.name}.", dir=parent))
    temporary_layout = _relative_layout(temporary)
    written: list[Path] = []
    try:
        for directory in (
            temporary_layout.contracts,
            temporary_layout.data_quality,
            temporary_layout.snapshots,
            temporary_layout.hypotheses,
            temporary_layout.registry,
            temporary_layout.reports,
        ):
            directory.mkdir(parents=True, exist_ok=False)

        resolved_cfg = dict(cfg)
        resolved_cfg.pop("config_path", None)
        specification_path = temporary_layout.contracts / "resolved_specification.yaml"
        specification_path.write_text(
            yaml.safe_dump(resolved_cfg, sort_keys=False),
            encoding="utf-8",
        )
        written.append(specification_path)

        snapshot_path = temporary_layout.snapshots / "discovery_snapshot_manifest.json"
        _write_json(snapshot_path, loaded.manifest.to_dict())
        written.append(snapshot_path)

        quality_path = temporary_layout.data_quality / "snapshot_quality_report.json"
        _write_json(quality_path, loaded.manifest.quality)
        written.append(quality_path)

        bins_path = temporary_layout.hypotheses / "frozen_quintile_edges.json"
        _write_json(bins_path, scan.frozen_bins.to_dict())
        written.append(bins_path)

        measurement_scope_path = temporary_layout.registry / "measurement_scope.json"
        _write_json(
            measurement_scope_path,
            {
                "research_id": cfg["research_id"],
                "scope": "CONDITIONAL_EFFECT_MEASUREMENT_ONLY",
                "hypothesis_promotion_performed": False,
                "signal_generation_performed": False,
                "backtest_performed": False,
                "prospective_data_accessed": False,
            },
        )
        written.append(measurement_scope_path)

        effects_path = temporary_layout.reports / "conditional_effects.csv"
        scan.effects.to_csv(effects_path, index=False)
        written.append(effects_path)
        stability_path = temporary_layout.reports / "temporal_stability.csv"
        scan.temporal_stability.to_csv(stability_path, index=False)
        written.append(stability_path)
        sensitivities_path = temporary_layout.reports / "inference_sensitivities.csv"
        scan.inference_sensitivities.to_csv(sensitivities_path, index=False)
        written.append(sensitivities_path)

        inference_contract_path = temporary_layout.registry / "inference_contract.json"
        automatic_fail_count = int(scan.effects["automatic_fail"].sum())
        _write_json(
            inference_contract_path,
            {
                "hac": cfg["statistics"]["hac"],
                "block_bootstrap": cfg["statistics"]["block_bootstrap"],
                "chronological_stability": cfg["statistics"][
                    "chronological_stability"
                ],
                "multiple_testing": cfg["multiple_testing"],
                **(
                    {"economic_gate": cfg["economic_gate"]}
                    if "economic_gate" in cfg
                    else {}
                ),
                "observed_effect_rows": int(len(scan.effects)),
                "automatic_fail_effect_rows": automatic_fail_count,
                "automatic_fail_p_value": 1.0,
                "global_family_size": cfg["multiple_testing"]["global_family_size"],
                "binding_gate": "GLOBAL_BY_AT_0.05",
            },
        )
        written.append(inference_contract_path)

        artifact_sha256 = _artifact_hashes(temporary, written)
        created_at = datetime.now(timezone.utc).isoformat()
        code_version = collect_git_metadata()
        eligible_count = int((scan.effects["inference_status"] == "ELIGIBLE").sum())
        identity_payload = {
            "research_id": cfg["research_id"],
            "specification_hash": cfg["specification_hash"],
            "snapshot_id": loaded.manifest.snapshot_id,
            "snapshot_sha256": loaded.manifest.sha256,
            "frozen_bin_edge_hash": scan.frozen_bins.edge_hash,
            "artifact_sha256": artifact_sha256,
            "code_version": code_version,
        }
        run_identity_sha256, _ = compute_config_hash(identity_payload)
        run_manifest = {
            "schema_version": 1,
            "created_at": created_at,
            **identity_payload,
            "run_identity_sha256": run_identity_sha256,
            "evidence_role": loaded.manifest.evidence_role.value,
            "source_classification": loaded.manifest.source_classification.value,
            "input_row_count": int(len(loaded.frame)),
            "conditional_effect_count": int(len(scan.effects)),
            "eligible_inference_count": eligible_count,
            "automatic_fail_effect_count": int(
                scan.effects["automatic_fail"].sum()
            ),
            "temporal_stability_row_count": int(len(scan.temporal_stability)),
            "inference_sensitivity_row_count": int(
                len(scan.inference_sensitivities)
            ),
            "global_multiple_testing_family_size": cfg["multiple_testing"][
                "global_family_size"
            ],
            "binding_multiple_testing_gate": "GLOBAL_BY_AT_0.05",
            "dimensions": sorted(
                int(value) for value in scan.effects["dimension"].unique()
            ),
            "horizons": [int(value) for value in cfg["horizons"]],
            "directions": ["LONG", "SHORT"],
            "net_cost_scope": cfg["execution_measurement"]["net_cost_scope"],
            **(
                {"economic_gate": cfg["economic_gate"]}
                if "economic_gate" in cfg
                else {}
            ),
            "runtime_assertions": {
                "autonomous_hypothesis_generation": False,
                "machine_learning": False,
                "signal_optimization": False,
                "backtests": False,
                "prospective_access": False,
            },
        }
        run_manifest_path = temporary / "run_manifest.json"
        _write_json(run_manifest_path, run_manifest)

        temporary.rename(layout.run_root)
        return AlphaDiscoveryArtifactResult(
            run_root=layout.run_root,
            run_manifest_path=layout.run_root / "run_manifest.json",
            run_identity_sha256=run_identity_sha256,
            artifact_sha256=artifact_sha256,
        )
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


__all__ = [
    "AlphaDiscoveryArtifactError",
    "AlphaDiscoveryArtifactLayout",
    "AlphaDiscoveryArtifactResult",
    "write_alpha_discovery_artifacts",
]
