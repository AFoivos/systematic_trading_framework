"""Deterministic filesystem artifacts for one discovery run."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import tempfile
from typing import Any

from ..contracts import ResearchContractError
from ..serialization import deterministic_json_dumps
from .contracts import ParameterNeighborhoodStability
from .service import DiscoveryRunResult


class DiscoveryArtifactError(RuntimeError):
    """Raised when a discovery artifact would be rewritten or is invalid."""


@dataclass(frozen=True)
class DiscoveryArtifactManifest:
    root: Path
    artifacts: Mapping[str, Path]

    def to_dict(self) -> dict[str, str]:
        return {
            name: path.as_posix() for name, path in sorted(self.artifacts.items())
        }


def _write_once(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise DiscoveryArtifactError(
                f"Immutable discovery artifact already exists: {path}"
            ) from exc
    finally:
        temporary.unlink(missing_ok=True)


def _top_candidate_rows(result: DiscoveryRunResult) -> list[dict[str, Any]]:
    trial_by_id = {trial.trial_id: trial for trial in result.trials}
    rows: list[dict[str, Any]] = []
    for entry in result.ranking.entries:
        if not entry.eligible or entry.rank is None or entry.rank > 10:
            continue
        trial = trial_by_id[entry.trial_id]
        rows.append(
            {
                "rank": entry.rank,
                "trial_id": entry.trial_id,
                "score": entry.score,
                "parameters": dict(trial.parameters),
                "metrics": dict(trial.metrics),
            }
        )
    return rows


def build_discovery_summary(result: DiscoveryRunResult) -> dict[str, Any]:
    state_counts = Counter(trial.status.value for trial in result.trials)
    return {
        "hypothesis": result.hypothesis.to_dict(),
        "research_run_id": result.research_run.research_run_id,
        "request_id": result.research_run.request_id,
        "discovery_specification_hash": result.specification.specification_hash,
        "search_method": result.specification.search_method,
        "search_dimensions": [
            {
                "name": parameter.name,
                "kind": parameter.kind.value,
                "path": parameter.path,
            }
            for parameter in result.specification.search_space.parameters
        ],
        "requested_trials": result.specification.trial_budget,
        "emitted_trials": result.ranking.total_trial_count,
        "completed_trials": state_counts.get("completed", 0),
        "failed_trials": state_counts.get("failed", 0),
        "pruned_trials": state_counts.get("pruned", 0),
        "invalid_trials": state_counts.get("invalid", 0),
        "eligible_trials": result.ranking.eligible_candidate_count,
        "selection_metric": result.ranking.selection_metric,
        "selection_direction": result.ranking.selection_direction.value,
        "tie_break_rule": result.ranking.tie_break_rule,
        "top_candidates": _top_candidate_rows(result),
        "selected_candidates": [
            {
                "candidate_id": candidate.candidate_id,
                "status": candidate.status.value,
                "trial_id": candidate.search_metadata.get("trial_id"),
                "candidate_rank": candidate.search_metadata.get("candidate_rank"),
            }
            for candidate in result.candidates
        ],
        "rejection_counts": dict(result.ranking.rejection_counts),
        "dataset_reference": result.specification.dataset_reference,
        "dataset_fingerprint": dict(result.specification.dataset_fingerprint),
        "cost_assumptions": dict(result.specification.cost_assumptions),
        "validation_boundary": {
            "method": result.specification.validation_method,
            "required_evidence_stage": "validation",
            "required_evidence_role": "VALIDATION",
            "request_count": len(result.validation_requests),
        },
        "duplicate_of_run_ids": list(result.duplicate_of_run_ids),
        "warnings": list(result.warnings),
    }


def build_discovery_report(summary: Mapping[str, Any]) -> str:
    rejection_counts = dict(summary.get("rejection_counts", {}) or {})
    rejection_lines = (
        [f"- `{reason}`: {count}" for reason, count in sorted(rejection_counts.items())]
        or ["- Καμία structural rejection."]
    )
    warning_lines = (
        [f"- `{warning}`" for warning in summary.get("warnings", [])]
        or ["- Καμία."]
    )
    selected_lines = (
        [
            "- "
            f"`{row['candidate_id']}` από `{row['trial_id']}` "
            f"(rank={row['candidate_rank']}, status={row['status']})"
            for row in summary.get("selected_candidates", [])
        ]
        or ["- Κανένας candidate δεν πέρασε τα configured eligibility gates."]
    )
    return "\n".join(
        [
            "# Alpha discovery report",
            "",
            f"- Hypothesis: `{dict(summary['hypothesis'])['hypothesis_id']}` — "
            f"{dict(summary['hypothesis'])['name']}",
            f"- Research run: `{summary['research_run_id']}`",
            f"- Frozen discovery specification: `{summary['discovery_specification_hash']}`",
            f"- Search method: `{summary['search_method']}`",
            f"- Dataset: `{summary['dataset_reference']}` / "
            f"`{dict(summary['dataset_fingerprint']).get('sha256')}`",
            "",
            "## Search breadth",
            "",
            f"- Requested budget: {summary['requested_trials']}",
            f"- Emitted trials: {summary['emitted_trials']}",
            f"- Completed: {summary['completed_trials']}",
            f"- Failed: {summary['failed_trials']}",
            f"- Pruned: {summary['pruned_trials']}",
            f"- Invalid: {summary['invalid_trials']}",
            f"- Eligible: {summary['eligible_trials']}",
            "",
            "## Ranking και selection",
            "",
            f"- Primary metric: `{summary['selection_metric']}` "
            f"({summary['selection_direction']})",
            f"- Tie break: `{summary['tie_break_rule']}`",
            "",
            *selected_lines,
            "",
            "Οι επιλεγμένοι candidates είναι μόνο `pending_canonical_validation`. "
            "Το discovery ranking δεν αποτελεί canonical OOS validation, robustness "
            "ή final evidence.",
            "",
            "## Rejections",
            "",
            *rejection_lines,
            "",
            "## Validation boundary",
            "",
            "Κάθε selected candidate έχει portable request προς "
            "`canonical_experiment` και απαιτεί role-bound `VALIDATION` evidence. "
            "Το discovery service δεν φορτώνει validation ή `PROSPECTIVE_FINAL` data.",
            "",
            "## Warnings",
            "",
            *warning_lines,
            "",
        ]
    )


class DiscoveryArtifactWriter:
    """Write create-once JSON/JSONL/Markdown under a caller-owned run root."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        if self.root.exists() and not self.root.is_dir():
            raise DiscoveryArtifactError(
                f"Discovery artifact root is not a directory: {self.root}"
            )

    def write(
        self,
        result: DiscoveryRunResult,
        *,
        parameter_neighborhood: Iterable[ParameterNeighborhoodStability] = (),
    ) -> DiscoveryArtifactManifest:
        if not isinstance(result, DiscoveryRunResult):
            raise DiscoveryArtifactError("result must be DiscoveryRunResult.")
        neighborhoods = tuple(parameter_neighborhood)
        if any(
            not isinstance(item, ParameterNeighborhoodStability)
            for item in neighborhoods
        ):
            raise DiscoveryArtifactError(
                "parameter_neighborhood must contain only stability records."
            )
        summary = build_discovery_summary(result)
        payloads = {
            "discovery_spec": deterministic_json_dumps(
                {
                    "specification": result.specification.to_dict(),
                    "specification_hash": result.specification.specification_hash,
                },
                trailing_newline=True,
            ),
            "trials": "".join(
                deterministic_json_dumps(trial, trailing_newline=True)
                for trial in result.trials
            ),
            "ranking": deterministic_json_dumps(
                result.ranking.to_dict(), trailing_newline=True
            ),
            "selected_candidates": deterministic_json_dumps(
                {
                    "selections": [item.to_dict() for item in result.selections],
                    "candidates": [item.to_dict() for item in result.candidates],
                },
                trailing_newline=True,
            ),
            "canonical_validation_requests": deterministic_json_dumps(
                {
                    "requests": [
                        item.to_dict() for item in result.validation_requests
                    ]
                },
                trailing_newline=True,
            ),
            "parameter_neighborhood": deterministic_json_dumps(
                {"records": [item.to_dict() for item in neighborhoods]},
                trailing_newline=True,
            ),
            "discovery_summary": deterministic_json_dumps(
                summary, trailing_newline=True
            ),
            "discovery_report": build_discovery_report(summary),
        }
        filenames = {
            "discovery_spec": "discovery_spec.json",
            "trials": "trials.jsonl",
            "ranking": "ranking.json",
            "selected_candidates": "selected_candidates.json",
            "canonical_validation_requests": "canonical_validation_requests.json",
            "parameter_neighborhood": "parameter_neighborhood.json",
            "discovery_summary": "discovery_summary.json",
            "discovery_report": "discovery_report.md",
        }
        paths = {name: self.root / filename for name, filename in filenames.items()}
        existing = sorted(str(path) for path in paths.values() if path.exists())
        if existing:
            raise DiscoveryArtifactError(
                f"Immutable discovery artifacts already exist: {existing}"
            )
        try:
            for name, path in paths.items():
                _write_once(path, payloads[name])
        except (OSError, ResearchContractError) as exc:
            if isinstance(exc, DiscoveryArtifactError):
                raise
            raise DiscoveryArtifactError(f"Could not write discovery artifacts: {exc}") from exc
        return DiscoveryArtifactManifest(root=self.root, artifacts=paths)


__all__ = [
    "DiscoveryArtifactError",
    "DiscoveryArtifactManifest",
    "DiscoveryArtifactWriter",
    "build_discovery_report",
    "build_discovery_summary",
]
