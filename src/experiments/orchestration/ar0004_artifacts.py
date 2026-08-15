"""Atomic, immutable artifacts for the AR-0004 cloud tournament."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping

import pandas as pd
import yaml

from src.research import DiscoveryArtifactWriter, DiscoveryRunResult
from src.research.ar0004_runtime import (
    AR0004BuiltPanel,
    CandidateEvaluation,
    materialize_screening_predictions,
)
from src.utils.run_metadata import collect_git_metadata, compute_config_hash, file_sha256


class AR0004ArtifactError(RuntimeError):
    """Raised when immutable AR-0004 persistence cannot be completed."""


def ar0004_run_root(cfg: Mapping[str, Any]) -> Path:
    return Path(str(cfg["artifacts"]["output_root"])) / str(cfg["specification_hash"])[:16]


def _json_default(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Value of type {type(value).__name__} is not JSON-compatible.")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def _evaluation_payload(evaluation: CandidateEvaluation) -> dict[str, Any]:
    return {
        "identity": evaluation.identity,
        "parameters": evaluation.parameters,
        "status": evaluation.status,
        "failure_reason": evaluation.failure_reason,
        "metrics": evaluation.metrics,
        "fold_metrics": [item.to_dict() for item in evaluation.fold_metrics],
        "rank_ic_periods": int(len(evaluation.rank_ic_timeline)),
    }


def _selected_predictions(
    *,
    cfg: Mapping[str, Any],
    built: AR0004BuiltPanel,
    lifecycle: DiscoveryRunResult,
    evaluation_by_trial: Mapping[str, CandidateEvaluation],
) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for candidate in lifecycle.candidates:
        trial_id = str(candidate.search_metadata["trial_id"])
        evaluation = evaluation_by_trial[trial_id]
        frame = materialize_screening_predictions(cfg, built, evaluation)
        frame = frame.copy()
        frame["candidate_id"] = candidate.candidate_id
        frame["trial_id"] = trial_id
        parts.append(frame)
    if not parts:
        return pd.DataFrame(
            columns=[
                "candidate_id",
                "trial_id",
                "timestamp",
                "asset_id",
                "fold_id",
                "prediction",
                "target",
                "is_oos",
                "trained_without_this_row",
                "model_fit_end_timestamp",
            ]
        )
    output = pd.concat(parts, ignore_index=True)
    maximum = int(cfg["resource_policy"]["maximum_selected_prediction_rows_written"])
    if len(output) > maximum:
        raise AR0004ArtifactError(
            f"Selected prediction artifact exceeds cap: {len(output)}>{maximum}."
        )
    return output.sort_values(
        ["candidate_id", "timestamp", "asset_id"], kind="mergesort"
    ).reset_index(drop=True)


def _report(
    cfg: Mapping[str, Any], lifecycle: DiscoveryRunResult, breadth: Mapping[str, Any]
) -> str:
    selected = [
        f"- `{candidate.candidate_id}` — status `{candidate.status.value}`"
        for candidate in lifecycle.candidates
    ] or ["- No candidate passed every frozen gate."]
    return "\n".join(
        [
            "# AR-0004 Cloud Alpha Tournament",
            "",
            f"- Specification: `{cfg['specification_hash']}`",
            "- Evidence role: `DISCOVERY`",
            "- Tuning: Optuna on four expanding walk-forward folds",
            "- Screening: 24 frozen finalists plus one fixed ensemble on three later OOS folds",
            "- Binding multiplicity: global BY at 5% over all 25 screening alternatives",
            "- Cost gate: observed bid/ask stressed to 1.50x",
            "",
            "## Search breadth",
            "",
            *[f"- {name}: {value}" for name, value in sorted(breadth.items())],
            "",
            "## Selected candidates",
            "",
            *selected,
            "",
            "Every selected candidate stops at `PENDING_CANONICAL_VALIDATION`.",
            "Screening OOS is discovery evidence, not validation or a final holdout.",
            "No portfolio backtest or live/paper/demo execution was performed.",
            "",
        ]
    )


def write_ar0004_artifacts(
    *,
    cfg: Mapping[str, Any],
    built: AR0004BuiltPanel,
    tournament: Mapping[str, Any],
    lifecycle: DiscoveryRunResult,
    evaluation_by_trial: Mapping[str, CandidateEvaluation],
) -> dict[str, Any]:
    """Persist the entire run atomically and refuse any overwrite."""

    run_root = ar0004_run_root(cfg)
    if run_root.exists():
        raise AR0004ArtifactError(f"Immutable AR-0004 run already exists: {run_root}")
    run_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{run_root.name}.", dir=run_root.parent))
    try:
        for name in (
            "contracts",
            "data_quality",
            "datasets",
            "tuning",
            "screening",
            "candidates",
            "reports",
        ):
            (temporary / name).mkdir(parents=True, exist_ok=False)

        resolved = dict(cfg)
        resolved.pop("config_path", None)
        (temporary / "contracts" / "resolved_specification.yaml").write_text(
            yaml.safe_dump(resolved, sort_keys=False), encoding="utf-8"
        )
        _write_json(temporary / "data_quality" / "source_quality.json", built.source_quality)
        _write_json(
            temporary / "datasets" / "panel_metadata.json",
            {
                "dataset_id": "AR-0004-RUNTIME-BUILT-DISCOVERY-PANEL-V1",
                "dataset_fingerprint": built.dataset_fingerprint,
                "rows": int(len(built.frame)),
                "assets": list(cfg["asset_universe"]["asset_ids"]),
                "timezone": "UTC",
                "evidence_role": "DISCOVERY",
                "row_identity": ["timestamp", "asset_id"],
                "features": list(cfg["features"]["feature_sets"]["full_cross_sectional"]),
                "targets": ["future_executable_return_h16", "future_executable_return_h32"],
            },
        )

        tuning_rows = tournament["tuning_rows"].copy()
        if "fold_metrics" in tuning_rows:
            tuning_rows["fold_metrics"] = tuning_rows["fold_metrics"].map(
                lambda value: json.dumps(value, sort_keys=True, allow_nan=False)
                if value is not None
                else ""
            )
        tuning_rows.to_csv(temporary / "tuning" / "optuna_trials.csv", index=False)
        study_path = Path(tournament["study_storage"])
        if study_path.is_file():
            shutil.copy2(study_path, temporary / "tuning" / "optuna_study.db")

        DiscoveryArtifactWriter(temporary / "screening" / "lifecycle").write(lifecycle)
        evaluations = list(tournament["evaluations"])
        _write_json(
            temporary / "screening" / "fold_metrics.json",
            [
                {
                    "identity": item.identity,
                    "fold_metrics": [fold.to_dict() for fold in item.fold_metrics],
                }
                for item in evaluations
            ],
        )
        _write_json(
            temporary / "screening" / "inference.json",
            [_evaluation_payload(item) for item in evaluations],
        )
        selected_predictions = _selected_predictions(
            cfg=cfg,
            built=built,
            lifecycle=lifecycle,
            evaluation_by_trial=evaluation_by_trial,
        )
        selected_predictions.to_csv(
            temporary / "screening" / "selected_predictions.csv.gz",
            index=False,
            compression="gzip",
            float_format="%.17g",
        )
        _write_json(
            temporary / "candidates" / "selected_candidates.json",
            [candidate.to_dict() for candidate in lifecycle.candidates],
        )
        _write_json(
            temporary / "candidates" / "canonical_validation_requests.json",
            [request.to_dict() for request in lifecycle.validation_requests],
        )
        _write_json(
            temporary / "reports" / "search_breadth.json",
            tournament["search_breadth"],
        )
        (temporary / "reports" / "final_report.md").write_text(
            _report(cfg, lifecycle, tournament["search_breadth"]), encoding="utf-8"
        )

        artifact_hashes = {
            str(path.relative_to(temporary)): file_sha256(path)
            for path in sorted(temporary.rglob("*"))
            if path.is_file()
        }
        identity_payload = {
            "research_id": cfg["research_id"],
            "specification_hash": cfg["specification_hash"],
            "dataset_fingerprint": built.dataset_fingerprint,
            "source_sha256": {
                asset: source["sha256"]
                for asset, source in cfg["asset_universe"]["source_files"].items()
            },
            "artifact_sha256": artifact_hashes,
            "code_version": collect_git_metadata(),
        }
        run_identity, _ = compute_config_hash(identity_payload)
        manifest = {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **identity_payload,
            "run_identity_sha256": run_identity,
            "evidence_role": "DISCOVERY",
            "screening_only": True,
            "validation_accessed": False,
            "prospective_final_accessed": False,
            "portfolio_constructed": False,
            "canonical_backtest_performed": False,
            "broker_execution_performed": False,
            "selected_candidate_count": len(lifecycle.candidates),
            "selected_prediction_rows": int(len(selected_predictions)),
            "search_breadth": tournament["search_breadth"],
        }
        _write_json(temporary / "run_manifest.json", manifest)
        temporary.rename(run_root)
        return {
            "research_id": cfg["research_id"],
            "specification_hash": cfg["specification_hash"],
            "run_root": str(run_root),
            "run_manifest_path": str(run_root / "run_manifest.json"),
            "run_identity_sha256": run_identity,
            "dataset_fingerprint": built.dataset_fingerprint,
            "search_breadth": tournament["search_breadth"],
            "candidate_count": len(lifecycle.candidates),
            "candidate_status_ceiling": "PENDING_CANONICAL_VALIDATION",
            "canonical_validation_required": True,
        }
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


__all__ = ["AR0004ArtifactError", "ar0004_run_root", "write_ar0004_artifacts"]
