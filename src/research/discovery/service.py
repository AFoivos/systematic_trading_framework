"""Canonical alpha-discovery orchestration over Phase 1 research records."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from ..candidate import CandidateStatus, ResearchCandidate
from ..contracts import (
    ResearchContractError,
    ResearchResult,
    _freeze_json_mapping,
    _require_identifier,
    _require_timestamp,
    _require_unique_strings,
)
from ..evidence import CheckStatus
from ..hypothesis import ResearchHypothesis
from ..run import (
    ResearchRun,
    ResearchRunStatus,
    SearchMetadata,
    SelectionDirection,
)
from ..selection import SelectionRecord, candidate_from_research_result
from .contracts import (
    CandidateRanking,
    DiscoverySpecification,
    DiscoveryTrial,
    ParameterNeighborhoodStability,
    RankingEntry,
    TrialEvaluation,
    TrialProposal,
    TrialStatus,
)
from .validation import CanonicalValidationRequest, prepare_canonical_validation


TrialEvaluator = Callable[[TrialProposal], TrialEvaluation]


class DiscoverySearchExecutor(Protocol):
    """Framework-owned boundary implemented by grid or existing search engines."""

    @property
    def name(self) -> str: ...

    @property
    def backend_name(self) -> str: ...

    def execute(
        self,
        specification: DiscoverySpecification,
        *,
        research_run_id: str,
        evaluator: TrialEvaluator | None = None,
    ) -> tuple[DiscoveryTrial, ...]: ...


class DiscoveryRecordStore(Protocol):
    def save_run(self, run: ResearchRun) -> None: ...

    def save_selection(self, selection: SelectionRecord) -> None: ...

    def save_candidate(self, candidate: ResearchCandidate) -> None: ...


class GridCandidateGenerator:
    """Small deterministic executor used for manual grids and smoke research."""

    name = "grid"
    backend_name = "framework_grid"

    def execute(
        self,
        specification: DiscoverySpecification,
        *,
        research_run_id: str,
        evaluator: TrialEvaluator | None = None,
    ) -> tuple[DiscoveryTrial, ...]:
        if evaluator is None:
            raise ResearchContractError("Grid discovery requires a trial evaluator.")
        if specification.search_method != self.name:
            raise ResearchContractError(
                f"Grid executor cannot run search_method={specification.search_method!r}."
            )
        proposals = specification.search_space.iter_grid(
            limit=specification.trial_budget
        )
        trials: list[DiscoveryTrial] = []
        for index, parameters in enumerate(proposals):
            proposal = TrialProposal(
                trial_id=f"{research_run_id}-trial-{index:06d}",
                research_run_id=research_run_id,
                parameters=parameters,
                seed=specification.random_seed + index,
            )
            try:
                evaluation = evaluator(proposal)
                if not isinstance(evaluation, TrialEvaluation):
                    raise ResearchContractError(
                        "Trial evaluator must return TrialEvaluation."
                    )
            except ResearchContractError as exc:
                evaluation = TrialEvaluation(
                    status=TrialStatus.INVALID,
                    failure_reason=f"{type(exc).__name__}: {exc}",
                )
            except Exception as exc:  # evaluator failures belong in search breadth
                evaluation = TrialEvaluation(
                    status=TrialStatus.FAILED,
                    failure_reason=f"{type(exc).__name__}: {exc}",
                )
            trials.append(
                DiscoveryTrial(
                    trial_id=proposal.trial_id,
                    research_run_id=proposal.research_run_id,
                    parameters=proposal.parameters,
                    status=evaluation.status,
                    metrics=evaluation.metrics,
                    checks=evaluation.checks,
                    seed=proposal.seed,
                    failure_reason=evaluation.failure_reason,
                    artifact_references=evaluation.artifact_references,
                    runtime_metadata=evaluation.runtime_metadata,
                )
            )
        return tuple(trials)


def validate_framework_components(specification: DiscoverySpecification) -> None:
    """Resolve declared component names before an expensive search begins."""

    from src.features.registry import get_feature_fn
    from src.models.registry import get_model_fn
    from src.signals.registry import get_signal_fn
    from src.targets.registry import get_target_builder

    for name in specification.feature_families:
        get_feature_fn(name)
    get_target_builder(specification.target_family)
    for name in specification.model_families:
        get_model_fn(name)
    for name in specification.signal_families:
        get_signal_fn(name)


def _require_metric(
    trial: DiscoveryTrial,
    name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> str | None:
    value = trial.metrics.get(name)
    if value is None:
        return f"missing_metric:{name}"
    numeric = float(value)
    if minimum is not None and numeric < minimum:
        return f"minimum_not_met:{name}"
    if maximum is not None and numeric > maximum:
        return f"maximum_exceeded:{name}"
    return None


def _eligibility_reasons(
    specification: DiscoverySpecification,
    trial: DiscoveryTrial,
) -> tuple[str, ...]:
    if trial.status is not TrialStatus.COMPLETED:
        return (
            f"trial_status:{trial.status.value}:{trial.failure_reason}",
        )
    reasons: list[str] = []
    primary_metric = specification.selection.primary.metric
    if trial.metrics.get(primary_metric) is None:
        reasons.append(f"missing_selection_metric:{primary_metric}")

    requirements = specification.eligibility.minimum_data
    checks = (
        ("observation_count", requirements.minimum_observations, None),
        ("oos_rows", requirements.minimum_oos_rows, None),
        ("trade_count", requirements.minimum_trades, None),
        ("oos_coverage", requirements.minimum_coverage, None),
        ("missing_rate", None, requirements.maximum_missing_rate),
    )
    for name, minimum, maximum in checks:
        if minimum is None and maximum is None:
            continue
        reason = _require_metric(
            trial,
            name,
            minimum=None if minimum is None else float(minimum),
            maximum=None if maximum is None else float(maximum),
        )
        if reason is not None:
            reasons.append(reason)

    required_checks = {
        "causal_features",
        "target_signal_compatible",
        *specification.eligibility.required_checks,
    }
    if specification.model_families:
        required_checks.update({"fold_safe_preprocessing", "oos_predictions"})
    for name in sorted(required_checks):
        if trial.checks.get(name) is not True:
            reasons.append(f"required_check_failed:{name}")

    for rule in specification.eligibility.metric_rules:
        value = trial.metrics.get(rule.metric)
        if value is None:
            reasons.append(f"missing_metric:{rule.metric}")
        elif not rule.passes(value):
            reasons.append(rule.rejection_reason)
    return tuple(dict.fromkeys(reasons))


def _metric_sort_key(
    trial: DiscoveryTrial,
    *,
    metric: str,
    direction: SelectionDirection,
) -> tuple[int, float]:
    value = trial.metrics.get(metric)
    if value is None:
        return (1, 0.0)
    numeric = float(value)
    return (0, -numeric if direction is SelectionDirection.MAXIMIZE else numeric)


def rank_trials(
    specification: DiscoverySpecification,
    trials: Iterable[DiscoveryTrial],
) -> CandidateRanking:
    """Apply structural eligibility before deterministic metric ranking."""

    values = tuple(trials)
    if len(values) > specification.trial_budget:
        raise ResearchContractError(
            "Executor emitted more trials than the declared trial budget."
        )
    trial_ids = tuple(trial.trial_id for trial in values)
    if len(set(trial_ids)) != len(trial_ids):
        raise ResearchContractError("Discovery trial IDs must be unique.")
    reasons_by_trial = {
        trial.trial_id: _eligibility_reasons(specification, trial)
        for trial in values
    }
    eligible = [trial for trial in values if not reasons_by_trial[trial.trial_id]]
    preferences = (
        specification.selection.primary,
        *specification.selection.tie_breakers,
    )

    def sort_key(trial: DiscoveryTrial) -> tuple[Any, ...]:
        components: list[Any] = []
        for preference in preferences:
            components.extend(
                _metric_sort_key(
                    trial,
                    metric=preference.metric,
                    direction=preference.direction,
                )
            )
        components.append(trial.trial_id)
        return tuple(components)

    eligible.sort(key=sort_key)
    rank_by_trial = {
        trial.trial_id: rank for rank, trial in enumerate(eligible, start=1)
    }
    trial_by_id = {trial.trial_id: trial for trial in values}
    ordered_ids = [trial.trial_id for trial in eligible]
    ordered_ids.extend(sorted(set(trial_ids).difference(ordered_ids)))
    entries: list[RankingEntry] = []
    rejections: Counter[str] = Counter()
    primary_metric = specification.selection.primary.metric
    for trial_id in ordered_ids:
        trial = trial_by_id[trial_id]
        reasons = reasons_by_trial[trial_id]
        rejections.update(reasons)
        entries.append(
            RankingEntry(
                trial_id=trial_id,
                trial_status=trial.status,
                eligible=not reasons,
                rank=rank_by_trial.get(trial_id),
                score=trial.metrics.get(primary_metric),
                rejection_reasons=reasons,
            )
        )
    return CandidateRanking(
        selection_metric=primary_metric,
        selection_direction=specification.selection.primary.direction,
        tie_break_rule=specification.selection.tie_break_rule,
        entries=tuple(entries),
        total_trial_count=len(values),
        completed_trial_count=sum(
            trial.status is TrialStatus.COMPLETED for trial in values
        ),
        eligible_candidate_count=len(eligible),
        rejection_counts=dict(sorted(rejections.items())),
    )


def select_trials(
    ranking: CandidateRanking,
    trials: Iterable[DiscoveryTrial],
    *,
    top_k: int,
) -> tuple[DiscoveryTrial, ...]:
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ResearchContractError("top_k must be an integer >= 1.")
    trial_by_id = {trial.trial_id: trial for trial in trials}
    selected_entries = sorted(
        (
            entry
            for entry in ranking.entries
            if entry.eligible and entry.rank is not None and entry.rank <= top_k
        ),
        key=lambda entry: entry.rank,
    )
    return tuple(trial_by_id[entry.trial_id] for entry in selected_entries)


def analyze_parameter_neighborhood(
    trials: Iterable[DiscoveryTrial],
    *,
    candidate_trial_id: str,
    parameter_name: str,
    selection_metric: str,
    direction: SelectionDirection,
    configured_max_degradation: float,
) -> ParameterNeighborhoodStability:
    """Evaluate one-dimensional observed neighbors without launching new trials."""

    values = tuple(trials)
    selected = next(
        (trial for trial in values if trial.trial_id == candidate_trial_id), None
    )
    if selected is None or selected.status is not TrialStatus.COMPLETED:
        raise ResearchContractError(
            "Parameter-neighborhood analysis requires a completed selected trial."
        )
    center = selected.metrics.get(selection_metric)
    if center is None:
        raise ResearchContractError(
            "Selected trial is missing the neighborhood selection metric."
        )
    if parameter_name not in selected.parameters:
        raise ResearchContractError(
            f"Selected trial is missing parameter {parameter_name!r}."
        )
    neighbor_scores: dict[str, int | float] = {}
    for trial in values:
        if trial.trial_id == selected.trial_id or trial.status is not TrialStatus.COMPLETED:
            continue
        if trial.metrics.get(selection_metric) is None:
            continue
        if set(trial.parameters) != set(selected.parameters):
            continue
        differing = tuple(
            name
            for name in selected.parameters
            if trial.parameters[name] != selected.parameters[name]
        )
        if differing == (parameter_name,):
            neighbor_scores[trial.trial_id] = trial.metrics[selection_metric]
    if not neighbor_scores:
        return ParameterNeighborhoodStability(
            candidate_trial_id=selected.trial_id,
            parameter_name=parameter_name,
            selection_metric=selection_metric,
            direction=direction,
            configured_max_degradation=configured_max_degradation,
            neighbor_scores={},
            status=CheckStatus.NOT_RUN,
            details={"reason": "no_observed_one_parameter_neighbors"},
        )
    center_value = float(center)
    degradations = {
        trial_id: (
            center_value - float(score)
            if direction is SelectionDirection.MAXIMIZE
            else float(score) - center_value
        )
        for trial_id, score in neighbor_scores.items()
    }
    failed = {
        trial_id: degradation
        for trial_id, degradation in degradations.items()
        if degradation > float(configured_max_degradation)
    }
    return ParameterNeighborhoodStability(
        candidate_trial_id=selected.trial_id,
        parameter_name=parameter_name,
        selection_metric=selection_metric,
        direction=direction,
        configured_max_degradation=configured_max_degradation,
        neighbor_scores=neighbor_scores,
        status=CheckStatus.FAIL if failed else CheckStatus.PASS,
        details={
            "center_score": center_value,
            "neighbor_count": len(neighbor_scores),
            "failed_neighbor_ids": sorted(failed),
            "degradation_by_trial": degradations,
        },
    )


@dataclass(frozen=True)
class DiscoveryRunResult:
    hypothesis: ResearchHypothesis
    specification: DiscoverySpecification
    research_run: ResearchRun
    trials: tuple[DiscoveryTrial, ...]
    ranking: CandidateRanking
    selections: tuple[SelectionRecord, ...]
    candidates: tuple[ResearchCandidate, ...]
    validation_requests: tuple[CanonicalValidationRequest, ...]
    duplicate_of_run_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.hypothesis, ResearchHypothesis):
            raise ResearchContractError("hypothesis must be ResearchHypothesis.")
        if not isinstance(self.specification, DiscoverySpecification):
            raise ResearchContractError(
                "specification must be DiscoverySpecification."
            )
        if not isinstance(self.research_run, ResearchRun):
            raise ResearchContractError("research_run must be ResearchRun.")
        if not isinstance(self.ranking, CandidateRanking):
            raise ResearchContractError("ranking must be CandidateRanking.")
        if len(self.trials) != self.ranking.total_trial_count:
            raise ResearchContractError("Trial count differs from ranking breadth.")
        if not (
            len(self.selections)
            == len(self.candidates)
            == len(self.validation_requests)
        ):
            raise ResearchContractError(
                "Selections, candidates, and validation requests must align."
            )
        if any(
            candidate.status is not CandidateStatus.PENDING_CANONICAL_VALIDATION
            for candidate in self.candidates
        ):
            raise ResearchContractError(
                "Discovery output candidates must stop at pending canonical validation."
            )
        object.__setattr__(
            self,
            "duplicate_of_run_ids",
            _require_unique_strings(
                self.duplicate_of_run_ids, field_name="duplicate_of_run_ids"
            ),
        )
        object.__setattr__(
            self,
            "warnings",
            _require_unique_strings(self.warnings, field_name="warnings"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis": self.hypothesis.to_dict(),
            "specification": self.specification.to_dict(),
            "specification_hash": self.specification.specification_hash,
            "research_run": self.research_run.to_dict(),
            "trials": [trial.to_dict() for trial in self.trials],
            "ranking": self.ranking.to_dict(),
            "selections": [selection.to_dict() for selection in self.selections],
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "validation_requests": [
                request.to_dict() for request in self.validation_requests
            ],
            "duplicate_of_run_ids": list(self.duplicate_of_run_ids),
            "warnings": list(self.warnings),
        }


def _identity_digest(payload: Mapping[str, Any]) -> str:
    from src.utils.run_metadata import compute_config_hash

    digest, _ = compute_config_hash(payload)
    return digest


def run_discovery(
    hypothesis: ResearchHypothesis,
    specification: DiscoverySpecification,
    *,
    executor: DiscoverySearchExecutor,
    research_run_id: str,
    request_id: str,
    started_at: str,
    completed_at: str,
    evaluator: TrialEvaluator | None = None,
    backend_version: str | None = None,
    git_revision: str | None = None,
    runtime_provenance: Mapping[str, Any] | None = None,
    duplicate_of_run_ids: tuple[str, ...] = (),
    record_store: DiscoveryRecordStore | None = None,
    validate_components: bool = True,
) -> DiscoveryRunResult:
    """Execute discovery through selection and stop at canonical validation."""

    if not isinstance(hypothesis, ResearchHypothesis):
        raise ResearchContractError("hypothesis must be ResearchHypothesis.")
    if not isinstance(specification, DiscoverySpecification):
        raise ResearchContractError(
            "specification must be DiscoverySpecification."
        )
    run_id = _require_identifier(research_run_id, field_name="research_run_id")
    backend_request_id = _require_identifier(request_id, field_name="request_id")
    start = _require_timestamp(started_at, field_name="started_at")
    complete = _require_timestamp(completed_at, field_name="completed_at")
    if hypothesis.hypothesis_id != specification.hypothesis_id:
        raise ResearchContractError(
            "Hypothesis ID differs from discovery specification."
        )
    if hypothesis.assets != specification.assets:
        raise ResearchContractError(
            "Hypothesis assets differ from discovery specification."
        )
    if hypothesis.timeframe not in {None, specification.timeframe}:
        raise ResearchContractError(
            "Hypothesis timeframe differs from discovery specification."
        )
    if executor.name != specification.search_method:
        raise ResearchContractError(
            "Search executor name differs from specification search_method."
        )
    if validate_components:
        validate_framework_components(specification)

    resolved_backend_version = backend_version
    if resolved_backend_version is None:
        executor_backend_version = getattr(executor, "backend_version", None)
        if callable(executor_backend_version):
            executor_backend_version = executor_backend_version()
        if executor_backend_version is not None:
            resolved_backend_version = str(executor_backend_version)

    trials = tuple(
        executor.execute(
            specification,
            research_run_id=run_id,
            evaluator=evaluator,
        )
    )
    if any(not isinstance(trial, DiscoveryTrial) for trial in trials):
        raise ResearchContractError(
            "Search executor must return only DiscoveryTrial values."
        )
    if any(trial.research_run_id != run_id for trial in trials):
        raise ResearchContractError(
            "Every discovery trial must reference the active research run."
        )
    expected_parameters = set(specification.search_space.parameter_names)
    for trial in trials:
        actual_parameters = set(trial.parameters)
        if not actual_parameters.issubset(expected_parameters) or (
            trial.status is TrialStatus.COMPLETED
            and actual_parameters != expected_parameters
        ):
            raise ResearchContractError(
                "Completed trials must cover every declared dimension; failed/pruned "
                "trials may preserve a partial parameter set but cannot add dimensions."
            )
    ranking = rank_trials(specification, trials)
    selected_trials = select_trials(
        ranking,
        trials,
        top_k=specification.selection.top_k,
    )

    candidate_ids = tuple(
        "candidate-"
        + _identity_digest(
            {
                "discovery_specification_hash": specification.specification_hash,
                "parameters": dict(trial.parameters),
            }
        )[:24]
        for trial in selected_trials
    )
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ResearchContractError(
            "Selected trials produced duplicate deterministic candidate identities."
        )
    non_completed_count = len(trials) - ranking.completed_trial_count
    search_metadata = SearchMetadata(
        search_method=specification.search_method,
        requested_trials=specification.trial_budget,
        completed_trials=ranking.completed_trial_count,
        failed_trials=non_completed_count,
        evaluated_alternatives=ranking.completed_trial_count,
        candidate_count=len(candidate_ids),
        parameter_dimensions=specification.search_space.parameter_names,
        selection_metric=specification.selection.primary.metric,
        selection_direction=specification.selection.primary.direction,
        random_seed=specification.random_seed,
        study_name=None,
    )
    trial_state_counts = Counter(trial.status.value for trial in trials)
    duplicate_ids = _require_unique_strings(
        duplicate_of_run_ids, field_name="duplicate_of_run_ids"
    )
    warnings: list[str] = []
    if duplicate_ids:
        warnings.append(
            "deterministic_specification_hash_matches_prior_run"
        )
    cardinality = specification.search_space.cardinality()
    if cardinality is not None and cardinality > specification.trial_budget:
        warnings.append("grid_truncated_by_declared_trial_budget")
    if len(trials) < specification.trial_budget:
        warnings.append("executor_emitted_fewer_trials_than_requested_budget")
    if not selected_trials:
        warnings.append("no_eligible_candidate_selected")

    provenance = dict(runtime_provenance or {})
    provenance.update(
        {
            "discovery_specification_hash": specification.specification_hash,
            "trial_state_counts": dict(sorted(trial_state_counts.items())),
            "eligible_candidate_count": ranking.eligible_candidate_count,
            "selected_candidate_count": len(candidate_ids),
            "duplicate_of_run_ids": list(duplicate_ids),
        }
    )
    artifact_references = tuple(
        sorted(
            {
                reference
                for trial in trials
                for reference in trial.artifact_references
            }
        )
    )
    run = ResearchRun(
        research_run_id=run_id,
        hypothesis_id=hypothesis.hypothesis_id,
        request_id=backend_request_id,
        backend=executor.backend_name,
        backend_version=resolved_backend_version,
        started_at=start,
        completed_at=complete,
        status=ResearchRunStatus.COMPLETED,
        config_reference=specification.config_reference,
        config_hash=specification.config_hash,
        dataset_reference=specification.dataset_reference,
        dataset_fingerprint=specification.dataset_fingerprint,
        evidence_reference=specification.evidence_reference,
        search_metadata=search_metadata,
        artifact_references=artifact_references,
        candidate_ids=candidate_ids,
        git_revision=git_revision,
        random_seed=specification.random_seed,
        runtime_mode="research",
        provenance=_freeze_json_mapping(provenance, field_name="provenance"),
    )

    source_candidates: list[ResearchCandidate] = []
    selections: list[SelectionRecord] = []
    for trial, candidate_id in zip(selected_trials, candidate_ids):
        entry = ranking.entry_for(trial.trial_id)
        if entry.rank is None:
            raise ResearchContractError("Selected trial has no deterministic rank.")
        source_candidates.append(
            ResearchCandidate(
                candidate_id=candidate_id,
                strategy_name=hypothesis.name,
                backend=executor.backend_name,
                config_reference=specification.config_reference,
                assets=specification.assets,
                timeframe=specification.timeframe,
                sample_reference=specification.dataset_reference,
                metrics=trial.metrics,
                cost_assumptions=specification.cost_assumptions,
                search_metadata={
                    "trial_id": trial.trial_id,
                    "trial_parameters": dict(trial.parameters),
                    "trial_seed": trial.seed,
                    "trial_artifact_references": list(
                        trial.artifact_references
                    ),
                    "trial_runtime_metadata": dict(trial.runtime_metadata),
                    "discovery_specification_hash": specification.specification_hash,
                    "config_hash": specification.config_hash,
                    "dataset_fingerprint": dict(
                        specification.dataset_fingerprint
                    ),
                    "git_revision": git_revision,
                    "total_trial_count": ranking.total_trial_count,
                    "completed_trial_count": ranking.completed_trial_count,
                    "eligible_candidate_count": ranking.eligible_candidate_count,
                    "requested_trial_budget": specification.trial_budget,
                    "failed_trial_count": trial_state_counts.get("failed", 0),
                    "pruned_trial_count": trial_state_counts.get("pruned", 0),
                    "invalid_trial_count": trial_state_counts.get("invalid", 0),
                },
                status=CandidateStatus.SCREENED,
            )
        )
        selection_id = (
            "selection-"
            + _identity_digest(
                {
                    "research_run_id": run_id,
                    "candidate_id": candidate_id,
                    "rank": entry.rank,
                }
            )[:24]
        )
        selections.append(
            SelectionRecord(
                selection_id=selection_id,
                research_run_id=run_id,
                candidate_id=candidate_id,
                evaluated_alternatives=ranking.completed_trial_count,
                selection_metric=ranking.selection_metric,
                selection_direction=ranking.selection_direction,
                candidate_rank=entry.rank,
                tie_break_rule=ranking.tie_break_rule,
                selected_at=complete,
            )
        )

    portable_result = ResearchResult(
        request_id=backend_request_id,
        backend=executor.backend_name,
        candidates=tuple(source_candidates),
        artifact_references=artifact_references,
        metadata={
            "discovery_specification_hash": specification.specification_hash,
            "total_trial_count": ranking.total_trial_count,
            "eligible_candidate_count": ranking.eligible_candidate_count,
        },
    )
    pending_candidates: list[ResearchCandidate] = []
    validation_requests: list[CanonicalValidationRequest] = []
    trial_by_candidate = dict(zip(candidate_ids, selected_trials))
    for selection in selections:
        screened = candidate_from_research_result(
            portable_result,
            research_run=run,
            selection=selection,
        )
        trial = trial_by_candidate[screened.candidate_id]
        validation_request_id = (
            "validation-request-"
            + _identity_digest(
                {
                    "research_run_id": run_id,
                    "candidate_id": screened.candidate_id,
                    "discovery_specification_hash": specification.specification_hash,
                }
            )[:20]
        )
        pending, validation_request = prepare_canonical_validation(
            screened,
            specification=specification,
            request_id=validation_request_id,
            candidate_parameters=trial.parameters,
            created_at=complete,
        )
        pending_candidates.append(pending)
        validation_requests.append(validation_request)

    result = DiscoveryRunResult(
        hypothesis=hypothesis,
        specification=specification,
        research_run=run,
        trials=trials,
        ranking=ranking,
        selections=tuple(selections),
        candidates=tuple(pending_candidates),
        validation_requests=tuple(validation_requests),
        duplicate_of_run_ids=duplicate_ids,
        warnings=tuple(warnings),
    )
    if record_store is not None:
        record_store.save_run(run)
        for selection in result.selections:
            record_store.save_selection(selection)
        for candidate in result.candidates:
            record_store.save_candidate(candidate)
    return result


__all__ = [
    "DiscoveryRecordStore",
    "DiscoveryRunResult",
    "DiscoverySearchExecutor",
    "GridCandidateGenerator",
    "TrialEvaluator",
    "analyze_parameter_neighborhood",
    "rank_trials",
    "run_discovery",
    "select_trials",
    "validate_framework_components",
]
