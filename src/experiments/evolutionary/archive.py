from __future__ import annotations

"""Search-level manifests, candidate configs, evaluation tables, and frequencies."""

import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import tempfile
from typing import Any, Iterable, Mapping, Sequence

import yaml

from src.experiments.evolutionary.schemas import EvolutionarySpec
from src.utils.paths import enforce_safe_absolute_path
from src.utils.run_metadata import canonical_json_dumps


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({str(key) for row in rows for key in row})
    if not fieldnames:
        fieldnames = ["status"]
        rows = [{"status": "no_rows"}]
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})
        temporary = Path(handle.name)
    temporary.replace(path)


class EvolutionaryArchive:
    """Own all evolutionary-search writes under one validated output directory."""

    def __init__(self, spec: EvolutionarySpec) -> None:
        self.spec = spec
        self.root = enforce_safe_absolute_path(spec.output_dir)
        self._run_destination_validated = False
        self._resume_contract_validated = False
        candidate_relative = Path(spec.execution.candidate_output_dir)
        if candidate_relative.is_absolute():
            raise ValueError("execution.candidate_output_dir must be relative to artifacts.output_dir.")
        self.candidate_dir = (self.root / candidate_relative).resolve()
        try:
            self.candidate_dir.relative_to(self.root.resolve())
        except ValueError as exc:
            raise ValueError("execution.candidate_output_dir escapes artifacts.output_dir.") from exc

    def validate_run_destination(self) -> None:
        """Reject a non-resume run before it can overwrite an existing archive."""
        if self.root.exists() and not self.root.is_dir():
            raise FileExistsError(
                f"Evolutionary output path exists and is not a directory: {self.root}"
            )
        if self.root.is_dir() and any(self.root.iterdir()) and not self.spec.search.resume:
            raise FileExistsError(
                f"Evolutionary output directory is not empty and search.resume=false: {self.root}"
            )
        self._run_destination_validated = True

    def validate_resume_contract(
        self,
        *,
        search_name: str,
        decoder_contract_hash: str,
        search_contract_hash: str,
    ) -> None:
        """Fail closed before resume when the existing archive contract differs."""
        if not self.spec.search.resume or not self.root.exists():
            self._resume_contract_validated = True
            return
        if not self.root.is_dir():
            raise FileExistsError(
                f"Evolutionary output path exists and is not a directory: {self.root}"
            )
        if not any(self.root.iterdir()):
            self._resume_contract_validated = True
            return
        path = self.root / "search_manifest.json"
        if not path.is_file():
            raise ValueError(
                "Cannot resume from a non-empty evolutionary archive without "
                f"search_manifest.json: {self.root}"
            )
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"Cannot read existing evolutionary manifest: {path}") from exc
        if not isinstance(previous, Mapping):
            raise ValueError(f"Existing evolutionary manifest is not a mapping: {path}")
        expected = {
            "search_name": search_name,
            "decoder_contract_hash": decoder_contract_hash,
            "search_contract_hash": search_contract_hash,
        }
        for key, value in expected.items():
            if previous.get(key) != value:
                raise ValueError(
                    f"Evolutionary resume contract mismatch for {key!r}: "
                    f"existing={previous.get(key)!r}, requested={value!r}."
                )
        self._resume_contract_validated = True

    def initialize(self, manifest: Mapping[str, Any]) -> Path:
        if not self._run_destination_validated:
            self.validate_run_destination()
        if not self._resume_contract_validated:
            self.validate_resume_contract(
                search_name=str(manifest["search_name"]),
                decoder_contract_hash=str(manifest["decoder_contract_hash"]),
                search_contract_hash=str(manifest["search_contract_hash"]),
            )
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / "search_manifest.json"
        previous: dict[str, Any] = {}
        if self.spec.search.resume and path.is_file():
            previous = dict(json.loads(path.read_text(encoding="utf-8")))
        payload = {**previous, **dict(manifest)}
        payload.setdefault("created_at_utc", datetime.now(timezone.utc).isoformat())
        _write_text_atomic(path, json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n")
        return path

    def update_manifest(self, updates: Mapping[str, Any]) -> None:
        path = self.root / "search_manifest.json"
        current: dict[str, Any] = {}
        if path.is_file():
            current = dict(json.loads(path.read_text(encoding="utf-8")))
        current.update(_jsonable(dict(updates)))
        _write_text_atomic(path, json.dumps(current, indent=2, sort_keys=True) + "\n")

    def write_candidate_config(self, candidate_hash: str, config: Mapping[str, Any]) -> Path | None:
        if not self.spec.execution.save_candidate_configs:
            return None
        path = self.candidate_dir / f"{candidate_hash}.yaml"
        _write_text_atomic(path, yaml.safe_dump(dict(config), sort_keys=False))
        return path

    @staticmethod
    def _parent_ids(trial: Any) -> list[int]:
        attrs = dict(getattr(trial, "system_attrs", {}) or {})
        for key, value in attrs.items():
            if "parent" not in str(key).lower():
                continue
            if isinstance(value, (list, tuple)):
                return [int(item) for item in value]
        return []

    def evaluation_rows(self, trials: Iterable[Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for trial in trials:
            attrs = dict(getattr(trial, "user_attrs", {}) or {})
            state = getattr(getattr(trial, "state", None), "name", str(getattr(trial, "state", "")))
            value = getattr(trial, "value", None)
            row = {
                "base_config_hash": attrs.get("base_config_hash"),
                "candidate_hash": attrs.get("candidate_hash"),
                "decoded_config_hash": attrs.get("decoded_config_hash"),
                "decoder_contract_hash": attrs.get("decoder_contract_hash"),
                "duplicate_of": attrs.get("duplicate_of"),
                "duplicate_reused": bool(attrs.get("duplicate_reused", False)),
                "duration_seconds": (
                    (trial.datetime_complete - trial.datetime_start).total_seconds()
                    if getattr(trial, "datetime_complete", None) is not None
                    and getattr(trial, "datetime_start", None) is not None
                    else None
                ),
                "fitness": value,
                "fitness_components": canonical_json_dumps(
                    _jsonable(dict(attrs.get("fitness_components", {}) or {}))
                ),
                "generation": attrs.get("generation"),
                "genome": canonical_json_dumps(_jsonable(dict(attrs.get("genome", {}) or {}))),
                "metrics": canonical_json_dumps(
                    _jsonable(dict(attrs.get("resolved_metrics", {}) or {}))
                ),
                "parent_ids": canonical_json_dumps(
                    self._parent_ids(trial) or list(attrs.get("parent_ids", []) or [])
                ),
                "promotion_failures": canonical_json_dumps(
                    _jsonable(list(attrs.get("promotion_failures", []) or []))
                ),
                "promotion_metrics": canonical_json_dumps(
                    _jsonable(dict(attrs.get("promotion_metrics", {}) or {}))
                ),
                "promotion_passed": bool(attrs.get("promotion_passed", False)),
                "reason": attrs.get("failure_reason"),
                "rejected": bool(attrs.get("rejected", False)),
                "search_contract_hash": attrs.get("search_contract_hash"),
                "state": state,
                "trial": int(getattr(trial, "number", -1)),
            }
            rows.append(row)
        return rows

    @staticmethod
    def _accepted_unique_trials(trials: Iterable[Any]) -> list[Any]:
        accepted: list[Any] = []
        for trial in trials:
            state = getattr(getattr(trial, "state", None), "name", "")
            attrs = dict(getattr(trial, "user_attrs", {}) or {})
            if (
                state == "COMPLETE"
                and not bool(attrs.get("rejected", False))
                and attrs.get("duplicate_of") is None
            ):
                accepted.append(trial)
        return accepted

    def _elite_trials(self, trials: Sequence[Any]) -> list[Any]:
        ranked = [trial for trial in trials if getattr(trial, "value", None) is not None]
        ranked.sort(
            key=lambda trial: float(trial.value),
            reverse=self.spec.fitness.direction == "maximize",
        )
        if not ranked:
            return []
        frequency = self.spec.artifacts.frequency_analysis
        elite_count = max(
            frequency.elite_minimum_candidates,
            math.ceil(frequency.elite_fraction * len(ranked)),
        )
        return ranked[: min(elite_count, len(ranked))]

    @staticmethod
    def _final_generation_trials(trials: Sequence[Any]) -> list[Any]:
        resolved: list[tuple[Any, int]] = []
        for trial in trials:
            raw = dict(getattr(trial, "user_attrs", {}) or {}).get("generation")
            try:
                resolved.append((trial, int(raw)))
            except (TypeError, ValueError):
                continue
        if not resolved:
            return []
        final_generation = max(generation for _, generation in resolved)
        return [trial for trial, generation in resolved if generation == final_generation]

    def _frequency_rows(
        self,
        trials: Iterable[Any],
        *,
        context_key: str,
        values: Sequence[str],
    ) -> list[dict[str, Any]]:
        completed = []
        for trial in trials:
            attrs = dict(getattr(trial, "user_attrs", {}) or {})
            if bool(attrs.get("rejected", False)):
                continue
            context = dict(attrs.get("decoder_context", {}) or {})
            completed.append(set(str(value) for value in list(context.get(context_key, []) or [])))
        total = len(completed)
        return [
            {
                "name": value,
                "selected_count": sum(value in selected for selected in completed),
                "evaluated_candidates": total,
                "frequency": (
                    sum(value in selected for selected in completed) / total if total else None
                ),
            }
            for value in values
        ]

    @staticmethod
    def _module_frequency_rows(trials: Sequence[Any]) -> list[dict[str, Any]]:
        total = len(trials)
        enabled = sum(
            bool(
                dict(
                    dict(getattr(trial, "user_attrs", {}) or {}).get(
                        "decoder_context", {}
                    )
                    or {}
                ).get("use_high_volatility_regime_filter", False)
            )
            for trial in trials
        )
        return [
            {
                "name": "use_high_volatility_regime_filter",
                "selected_count": enabled,
                "evaluated_candidates": total,
                "frequency": enabled / total if total else None,
            }
        ]

    def _write_frequency_reports(
        self,
        *,
        trials: Sequence[Any],
        cohort_suffix: str,
        artifacts: dict[str, str],
    ) -> None:
        genome_params = self.spec.genome.decoder_params
        reports: list[tuple[bool, str, str, str, Sequence[str]]] = [
            (
                self.spec.artifacts.save_feature_frequency,
                "feature_family_frequency",
                "enabled_feature_families",
                "feature_family_frequency.csv",
                list(dict(genome_params.get("feature_families", {}) or {})),
            ),
            (
                self.spec.artifacts.save_gate_frequency,
                "gate_frequency",
                "enabled_gates",
                "gate_frequency.csv",
                list(dict(genome_params.get("gate_genes", {}) or {})),
            ),
            (
                self.spec.artifacts.save_asset_frequency,
                "asset_frequency",
                "selected_assets",
                "asset_frequency.csv",
                list(dict(genome_params.get("asset_genes", {}) or {})),
            ),
            (
                self.spec.artifacts.save_group_frequency,
                "group_frequency",
                "selected_groups",
                "group_frequency.csv",
                sorted(set(dict(genome_params.get("asset_groups", {}) or {}).values())),
            ),
        ]
        for enabled, key, context_key, filename, values in reports:
            if not enabled:
                continue
            artifact_key = f"{key}{cohort_suffix}"
            path = self.root / f"{Path(filename).stem}{cohort_suffix}.csv"
            _write_csv(
                path,
                self._frequency_rows(
                    trials,
                    context_key=context_key,
                    values=values,
                ),
            )
            artifacts[artifact_key] = str(path)
        if self.spec.artifacts.save_module_frequency:
            artifact_key = f"module_frequency{cohort_suffix}"
            path = self.root / f"module_frequency{cohort_suffix}.csv"
            _write_csv(path, self._module_frequency_rows(trials))
            artifacts[artifact_key] = str(path)

    def _candidate_config(
        self,
        candidate_id: str,
        candidate_configs: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any] | None:
        config = candidate_configs.get(candidate_id)
        if config is not None:
            return dict(config)
        if not candidate_id or any(character not in "0123456789abcdef" for character in candidate_id):
            return None
        path = self.candidate_dir / f"{candidate_id}.yaml"
        if not path.is_file():
            return None
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return dict(payload) if isinstance(payload, Mapping) else None

    def _generation_rows(self, evaluations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        generations = sorted(
            {
                int(row["generation"])
                for row in evaluations
                if row.get("generation") is not None
            }
        )
        rows: list[dict[str, Any]] = []
        maximize = self.spec.fitness.direction == "maximize"
        for generation in generations:
            subset = [row for row in evaluations if row.get("generation") == generation]
            values = [
                float(row["fitness"])
                for row in subset
                if row.get("fitness") is not None and not bool(row.get("rejected"))
            ]
            rows.append(
                {
                    "generation": generation,
                    "candidate_count": len(subset),
                    "accepted_count": len(values),
                    "rejected_count": sum(bool(row.get("rejected")) for row in subset),
                    "duplicate_count": sum(row.get("duplicate_of") is not None for row in subset),
                    "best_fitness": (max(values) if maximize else min(values)) if values else None,
                    "mean_fitness": sum(values) / len(values) if values else None,
                }
            )
        return rows

    def write_study_artifacts(
        self,
        study: Any,
        *,
        candidate_configs: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, str]:
        trials = list(getattr(study, "trials", []) or [])
        evaluations = self.evaluation_rows(trials)
        artifacts: dict[str, str] = {}
        if self.spec.artifacts.save_evaluations:
            path = self.root / "evaluations.csv"
            _write_csv(path, evaluations)
            artifacts["evaluations"] = str(path)
        if self.spec.artifacts.save_generation_summary:
            path = self.root / "generation_summary.csv"
            _write_csv(path, self._generation_rows(evaluations))
            artifacts["generation_summary"] = str(path)
        if self.spec.execution.save_failed_candidates:
            path = self.root / "failed_candidates.csv"
            _write_csv(path, [row for row in evaluations if bool(row.get("rejected"))])
            artifacts["failed_candidates"] = str(path)

        accepted_trials = self._accepted_unique_trials(trials)
        self._write_frequency_reports(
            trials=accepted_trials,
            cohort_suffix="",
            artifacts=artifacts,
        )
        frequency = self.spec.artifacts.frequency_analysis
        if frequency.enabled:
            self._write_frequency_reports(
                trials=self._elite_trials(accepted_trials),
                cohort_suffix="_elite",
                artifacts=artifacts,
            )
            if frequency.include_final_generation:
                self._write_frequency_reports(
                    trials=self._final_generation_trials(accepted_trials),
                    cohort_suffix="_final_generation",
                    artifacts=artifacts,
                )

        if self.spec.promotion.enabled:
            promotion_path = self.root / "promotion_report.csv"
            promotion_rows = []
            for trial, row in zip(trials, evaluations):
                attrs = dict(getattr(trial, "user_attrs", {}) or {})
                failures = list(attrs.get("promotion_failures", []) or [])
                promotion_rows.append(
                    {
                        "candidate_hash": row.get("candidate_hash"),
                        "duplicate_of": row.get("duplicate_of"),
                        "failed_gate_count": len(failures),
                        "failed_gates": canonical_json_dumps(_jsonable(failures)),
                        "fitness": row.get("fitness"),
                        "promotion_metrics": row.get("promotion_metrics"),
                        "promotion_passed": row.get("promotion_passed"),
                        "rejected": row.get("rejected"),
                        "state": row.get("state"),
                        "trial": row.get("trial"),
                    }
                )
            _write_csv(promotion_path, promotion_rows)
            artifacts["promotion_report"] = str(promotion_path)

            promoted_dir = self.root / "promoted_candidates"
            promoted_dir.mkdir(parents=True, exist_ok=True)
            for trial in accepted_trials:
                attrs = dict(getattr(trial, "user_attrs", {}) or {})
                if not bool(attrs.get("promotion_passed", False)):
                    continue
                candidate_id = str(attrs.get("candidate_hash", ""))
                config = self._candidate_config(candidate_id, candidate_configs)
                if config is None:
                    continue
                path = promoted_dir / f"{candidate_id}.yaml"
                _write_text_atomic(path, yaml.safe_dump(config, sort_keys=False))
            artifacts["promoted_candidates"] = str(promoted_dir)

        if self.spec.artifacts.save_best_candidates:
            direction_factor = -1.0 if self.spec.fitness.direction == "maximize" else 1.0
            ranked = sorted(
                (
                    trial
                    for trial in accepted_trials
                    if getattr(trial, "value", None) is not None
                ),
                key=lambda trial: direction_factor * float(trial.value),
            )[:10]
            best_dir = self.root / "best_candidates"
            for rank, trial in enumerate(ranked, start=1):
                candidate_id = str(dict(trial.user_attrs).get("candidate_hash", ""))
                config = self._candidate_config(candidate_id, candidate_configs)
                if config is None:
                    continue
                path = best_dir / f"rank_{rank:02d}_{candidate_id}.yaml"
                _write_text_atomic(path, yaml.safe_dump(config, sort_keys=False))
            artifacts["best_candidates"] = str(best_dir)

        if self.spec.artifacts.save_pareto_front:
            pareto = []
            for trial in list(getattr(study, "best_trials", []) or []):
                values = list(getattr(trial, "values", []) or [])
                if len(values) <= 1:
                    continue
                pareto.append(
                    {
                        "trial": trial.number,
                        "candidate_hash": dict(trial.user_attrs).get("candidate_hash"),
                        "values": canonical_json_dumps(values),
                    }
                )
            if pareto:
                path = self.root / "pareto_front.csv"
                _write_csv(path, pareto)
                artifacts["pareto_front"] = str(path)
        return artifacts


__all__ = ["EvolutionaryArchive"]
