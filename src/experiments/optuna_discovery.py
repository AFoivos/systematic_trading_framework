"""Thin Phase 2 adapter over the repository's existing Optuna engine."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from math import isfinite
from pathlib import Path
from typing import Any

from src.experiments.optuna_search import (
    ObjectiveSpec,
    PruningSpec,
    SearchDimension,
    normalize_objective_spec,
    optimize_experiment,
)
from src.research.contracts import ResearchContractError
from src.research.discovery.contracts import (
    DiscoverySpecification,
    DiscoveryTrial,
    TrialStatus,
)
from src.research.discovery.search_space import ParameterKind, SearchSpace
from src.research.discovery.service import TrialEvaluator


def to_existing_optuna_search_dimensions(
    search_space: SearchSpace,
) -> tuple[SearchDimension, ...]:
    """Translate neutral dimensions to the already supported Optuna schema."""

    dimensions: list[SearchDimension] = []
    kind_map = {
        ParameterKind.INTEGER: "int",
        ParameterKind.FLOAT: "float",
        ParameterKind.CATEGORICAL: "categorical",
        ParameterKind.FIXED: "categorical",
    }
    for parameter in search_space.parameters:
        if parameter.path is None:
            raise ResearchContractError(
                f"Optuna parameter {parameter.name!r} requires a config path."
            )
        choices = None
        if parameter.kind in {ParameterKind.CATEGORICAL, ParameterKind.FIXED}:
            choices = list(parameter.values)
        dimensions.append(
            SearchDimension(
                name=parameter.name,
                path=parameter.path,
                kind=kind_map[parameter.kind],
                low=parameter.low,
                high=parameter.high,
                step=parameter.step,
                log=parameter.log,
                choices=choices,
            )
        )
    return tuple(dimensions)


def _state_name(trial: Any) -> str:
    state = getattr(trial, "state", None)
    return str(getattr(state, "name", state)).upper()


def _finite_metrics(
    value: float,
    *,
    selection_metric: str,
    user_attrs: Mapping[str, Any],
) -> dict[str, int | float]:
    metrics: dict[str, int | float] = {selection_metric: float(value)}
    for prefix, key in (
        ("summary", "primary_summary"),
        ("derived", "derived_metrics"),
    ):
        values = dict(user_attrs.get(key, {}) or {})
        for raw_name, raw_value in sorted(values.items()):
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                continue
            if not isfinite(float(raw_value)):
                continue
            name = str(raw_name)
            metrics[f"{prefix}.{name}"] = raw_value
            metrics.setdefault(name, raw_value)
    return metrics


class ExistingOptunaSearchExecutor:
    """Execute the existing config-driven optimizer and emit portable trials.

    The adapter does not reinterpret an Optuna winner as validated evidence.
    OOS/fold-safe/causality checks must be present in ``discovery_checks`` trial
    user attributes when the DiscoverySpecification requires them.
    """

    name = "optuna"
    backend_name = "existing_optuna"

    def __init__(
        self,
        config_path: str | Path,
        *,
        objective: ObjectiveSpec | Mapping[str, Any] | None = None,
        pruning: PruningSpec | Mapping[str, Any] | None = None,
        study_name: str | None = None,
        storage: str | None = None,
        load_if_exists: bool = False,
        sampler: str = "tpe",
        timeout: float | None = None,
        n_jobs: int = 1,
        logging_enabled: bool = False,
        catch_exceptions: bool = True,
        report_output_dir: str | Path | None = None,
        report_run_name: str | None = None,
        study_runner: Callable[..., Any] = optimize_experiment,
    ) -> None:
        self.config_path = Path(config_path)
        self.objective = objective
        self.pruning = pruning
        self.study_name = study_name
        self.storage = storage
        self.load_if_exists = load_if_exists
        self.sampler = sampler
        self.timeout = timeout
        self.n_jobs = n_jobs
        self.logging_enabled = logging_enabled
        self.catch_exceptions = catch_exceptions
        self.report_output_dir = report_output_dir
        self.report_run_name = report_run_name
        self._study_runner = study_runner

    def execute(
        self,
        specification: DiscoverySpecification,
        *,
        research_run_id: str,
        evaluator: TrialEvaluator | None = None,
    ) -> tuple[DiscoveryTrial, ...]:
        if specification.search_method != self.name:
            raise ResearchContractError(
                f"Optuna executor cannot run {specification.search_method!r}."
            )
        if evaluator is not None:
            raise ResearchContractError(
                "Existing Optuna executor owns evaluation through the canonical runner."
            )
        dimensions = to_existing_optuna_search_dimensions(
            specification.search_space
        )
        objective = self.objective or ObjectiveSpec(
            metric_path=specification.selection.primary.metric,
            direction=specification.selection.primary.direction.value,
        )
        normalized_objective = normalize_objective_spec(objective)
        if (
            normalized_objective.direction
            != specification.selection.primary.direction.value
        ):
            raise ResearchContractError(
                "Optuna objective direction differs from discovery selection direction."
            )
        study = self._study_runner(
            self.config_path,
            search_space=dimensions,
            objective=normalized_objective,
            pruning=self.pruning,
            study_name=self.study_name,
            storage=self.storage,
            load_if_exists=self.load_if_exists,
            sampler=self.sampler,
            seed=specification.random_seed,
            n_trials=specification.trial_budget,
            timeout=self.timeout,
            n_jobs=self.n_jobs,
            logging_enabled=self.logging_enabled,
            catch_exceptions=self.catch_exceptions,
            report_output_dir=self.report_output_dir,
            report_run_name=self.report_run_name,
        )
        trials: list[DiscoveryTrial] = []
        for fallback_number, trial in enumerate(
            tuple(getattr(study, "trials", ()) or ())
        ):
            raw_number = getattr(trial, "number", fallback_number)
            number = fallback_number if raw_number is None else int(raw_number)
            state = _state_name(trial)
            user_attrs = dict(getattr(trial, "user_attrs", {}) or {})
            raw_value = getattr(trial, "value", None)
            trial_failed = bool(user_attrs.get("trial_failed"))
            if trial_failed:
                status = TrialStatus.FAILED
                failure_reason = str(
                    user_attrs.get("exception") or "optuna_trial_marked_failed"
                )
            elif state == "PRUNED":
                status = TrialStatus.PRUNED
                failure_reason = str(
                    user_attrs.get("pruning_reason") or "optuna_trial_pruned"
                )
            elif state in {"FAIL", "FAILED"}:
                status = TrialStatus.FAILED
                failure_reason = str(
                    user_attrs.get("exception") or "optuna_trial_failed"
                )
            elif (
                state == "COMPLETE"
                and raw_value is not None
                and not isinstance(raw_value, bool)
                and isinstance(raw_value, (int, float))
                and isfinite(float(raw_value))
            ):
                status = TrialStatus.COMPLETED
                failure_reason = None
            else:
                status = TrialStatus.INVALID
                failure_reason = "optuna_trial_missing_finite_completed_objective"

            metrics = (
                _finite_metrics(
                    float(raw_value),
                    selection_metric=specification.selection.primary.metric,
                    user_attrs=user_attrs,
                )
                if status is TrialStatus.COMPLETED
                else {}
            )
            raw_checks = user_attrs.get("discovery_checks", {}) or {}
            if not isinstance(raw_checks, Mapping):
                raise ResearchContractError(
                    "Optuna discovery_checks user attribute must be a mapping."
                )
            checks = {str(name): value for name, value in raw_checks.items()}
            artifact_references = tuple(
                str(value)
                for value in (
                    user_attrs.get("experiment_run_dir"),
                    user_attrs.get("experiment_report"),
                )
                if value
            )
            trials.append(
                DiscoveryTrial(
                    trial_id=f"{research_run_id}-trial-{number:06d}",
                    research_run_id=research_run_id,
                    parameters=dict(getattr(trial, "params", {}) or {}),
                    status=status,
                    metrics=metrics,
                    checks=checks,
                    seed=specification.random_seed + number,
                    failure_reason=failure_reason,
                    artifact_references=artifact_references,
                    runtime_metadata={
                        "optuna_state": state,
                        "optuna_trial_number": number,
                        "study_name": getattr(study, "study_name", None),
                        "objective_metric": normalized_objective.metric_path,
                        "objective_direction": normalized_objective.direction,
                    },
                )
            )
        return tuple(trials)


__all__ = [
    "ExistingOptunaSearchExecutor",
    "to_existing_optuna_search_dimensions",
]
