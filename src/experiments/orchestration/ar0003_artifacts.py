"""Immutable artifact writer for the approved AR-0003 discovery run."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping

import pandas as pd
import yaml

from src.research.ar0003_runtime import AR0003BuiltPanel
from src.utils.run_metadata import collect_git_metadata, compute_config_hash, file_sha256


class AR0003ArtifactError(RuntimeError):
    """Raised when immutable AR-0003 persistence cannot be completed."""


def ar0003_run_root(cfg: Mapping[str, Any]) -> Path:
    return Path(str(cfg["artifacts"]["output_root"])) / str(cfg["specification_hash"])[:16]


def _json_default(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Value of type {type(value).__name__} is not JSON-compatible.")


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            allow_nan=False,
            default=_json_default,
        )
        + "\n",
        encoding="utf-8",
    )


def write_ar0003_artifacts(
    *,
    cfg: Mapping[str, Any],
    built: AR0003BuiltPanel,
    evaluation: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist all outputs atomically and refuse any overwrite."""

    run_root = ar0003_run_root(cfg)
    if run_root.exists():
        raise AR0003ArtifactError(
            f"Immutable AR-0003 run already exists at {run_root}; refusing overwrite."
        )
    run_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{run_root.name}.", dir=run_root.parent))
    written: list[Path] = []
    try:
        directories = {
            name: temporary / name
            for name in ("contracts", "datasets", "data_quality", "predictions", "reports")
        }
        for directory in directories.values():
            directory.mkdir(parents=True, exist_ok=False)

        resolved = dict(cfg)
        resolved.pop("config_path", None)
        spec_path = directories["contracts"] / "resolved_specification.yaml"
        spec_path.write_text(yaml.safe_dump(resolved, sort_keys=False), encoding="utf-8")
        written.append(spec_path)

        for horizon in (16, 32):
            metadata_path = directories["datasets"] / f"panel_h{horizon}_metadata.json"
            _write_json(metadata_path, built.metadata[horizon].to_dict())
            written.append(metadata_path)

        quality_path = directories["data_quality"] / "source_quality.json"
        _write_json(quality_path, built.source_quality)
        written.append(quality_path)

        predictions = evaluation["primary_predictions"]
        if not isinstance(predictions, pd.DataFrame):
            raise AR0003ArtifactError("AR-0003 primary predictions must be a DataFrame internally.")
        predictions_path = directories["predictions"] / "primary_score_predictions.csv.gz"
        predictions.to_csv(
            predictions_path,
            index=False,
            compression="gzip",
            float_format="%.17g",
        )
        written.append(predictions_path)

        primary = dict(evaluation["primary_diagnostics"])
        primary.pop("prediction_records", None)
        report_payloads = {
            "cross_sectional_diagnostics.json": primary,
            "per_asset_diagnostics.json": evaluation["per_asset_diagnostics"],
            "temporal_stability.json": evaluation["temporal_stability"],
            "robustness_family.json": evaluation["variants"],
            "search_breadth.json": evaluation["search_breadth"],
        }
        for name, payload in report_payloads.items():
            path = directories["reports"] / name
            _write_json(path, payload)
            written.append(path)

        artifact_sha256 = {
            str(path.relative_to(temporary)): file_sha256(path)
            for path in sorted(written, key=lambda item: str(item.relative_to(temporary)))
        }
        identity_payload = {
            "research_id": cfg["research_id"],
            "specification_hash": cfg["specification_hash"],
            "panel_h16_sha256": built.metadata[16].dataset_fingerprint["sha256"],
            "panel_h32_sha256": built.metadata[32].dataset_fingerprint["sha256"],
            "source_sha256": cfg["dataset_contract"]["source_snapshot_fingerprints"],
            "artifact_sha256": artifact_sha256,
            "code_version": collect_git_metadata(),
        }
        run_identity_sha256, _ = compute_config_hash(identity_payload)
        manifest = {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **identity_payload,
            "run_identity_sha256": run_identity_sha256,
            "evidence_role": "DISCOVERY",
            "screening_only": True,
            "canonical_validation_required": True,
            "prospective_final_accessed": False,
            "validation_accessed": False,
            "portfolio_constructed": False,
            "backtest_performed": False,
            "broker_execution_performed": False,
            "primary_prediction_rows": int(len(predictions)),
            "deterministic_variants": int(len(evaluation["variants"])),
            "search_breadth": evaluation["search_breadth"],
        }
        manifest_path = temporary / "run_manifest.json"
        _write_json(manifest_path, manifest)
        temporary.rename(run_root)
        return {
            "research_id": cfg["research_id"],
            "specification_hash": cfg["specification_hash"],
            "run_root": str(run_root),
            "run_manifest_path": str(run_root / "run_manifest.json"),
            "run_identity_sha256": run_identity_sha256,
            "panel_h16_sha256": built.metadata[16].dataset_fingerprint["sha256"],
            "panel_h32_sha256": built.metadata[32].dataset_fingerprint["sha256"],
            "primary_prediction_rows": int(len(predictions)),
            "search_breadth": evaluation["search_breadth"],
            "evidence_role": "DISCOVERY",
            "candidate_status": "NO_AUTOMATIC_CANDIDATE_PROMOTION",
            "canonical_validation_required": True,
        }
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


__all__ = [
    "AR0003ArtifactError",
    "ar0003_run_root",
    "write_ar0003_artifacts",
]
