from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from src.research import CandidateStatus, EvidenceReference, EvidenceStage
from src.research.contracts import ResearchContractError
from src.research.discovery import (
    DiscoveryArtifactError,
    DiscoveryArtifactWriter,
    DiscoverySpecification,
    DiscoveryTrial,
    EligibilityPolicy,
    EligibilityRule,
    GridCandidateGenerator,
    MetricPreference,
    MinimumDataRequirements,
    ParameterKind,
    ParameterSpec,
    RuleOperator,
    SearchSpace,
    SelectionMetricBasis,
    SelectionPolicy,
    TrialEvaluation,
    TrialStatus,
    analyze_parameter_neighborhood,
    rank_trials,
    run_discovery,
)
from src.research.hypothesis import ResearchHypothesis
from src.research.run import SelectionDirection
from src.research.storage import FilesystemResearchStore
from src.src_data.research_roles import EvidenceRole


CONFIG_HASH = "b" * 64
DATA_HASH = "c" * 64
NOW = "2026-08-14T10:00:00+00:00"
LATER = "2026-08-14T10:01:00+00:00"


def _hypothesis() -> ResearchHypothesis:
    return ResearchHypothesis(
        hypothesis_id="hypothesis-phase2",
        name="Synthetic causal discovery",
        thesis="A configured causal effect should survive explicit eligibility gates.",
        assets=("ETHUSD",),
        timeframe="30m",
        created_at=NOW,
        feature_families=("roc",),
        target_kind="forward_return",
    )


def _specification(
    *,
    search_method: str = "grid",
    search_space: SearchSpace | None = None,
    selection: SelectionPolicy | None = None,
    model_families: tuple[str, ...] = (),
    evidence_reference: EvidenceReference | None = None,
    cost_assumptions: dict | None = None,
) -> DiscoverySpecification:
    return DiscoverySpecification(
        hypothesis_id="hypothesis-phase2",
        assets=("ETHUSD",),
        timeframe="30m",
        feature_families=("roc",),
        target_family="forward_return",
        model_families=model_families,
        signal_families=(),
        search_method=search_method,
        trial_budget=4,
        search_space=search_space
        or SearchSpace(
            (
                ParameterSpec(
                    name="lookback",
                    kind=ParameterKind.INTEGER,
                    path="features.0.params.window",
                    low=1,
                    high=4,
                ),
            )
        ),
        selection=selection
        or SelectionPolicy(
            primary=MetricPreference("rank_ic", SelectionDirection.MAXIMIZE),
            metric_basis=SelectionMetricBasis.PREDICTION,
            top_k=1,
            tie_breakers=(
                MetricPreference("turnover", SelectionDirection.MINIMIZE),
            ),
        ),
        eligibility=EligibilityPolicy(
            minimum_data=MinimumDataRequirements(
                minimum_observations=100,
                minimum_oos_rows=50,
                minimum_trades=10,
                minimum_coverage=0.90,
                maximum_missing_rate=0.05,
            ),
            metric_rules=(
                EligibilityRule(
                    metric="turnover",
                    operator=RuleOperator.LE,
                    threshold=5.0,
                    rejection_reason="turnover_limit_exceeded",
                ),
            ),
            required_checks=("data_quality",),
        ),
        config_reference="config/experiments/synthetic_phase2.yaml#frozen",
        config_hash=CONFIG_HASH,
        dataset_reference="snapshot:discovery-phase2-v1",
        dataset_fingerprint={"sha256": DATA_HASH, "rows": 1000},
        evidence_reference=evidence_reference
        or EvidenceReference(
            stage=EvidenceStage.DEVELOPMENT,
            evidence_role=EvidenceRole.DISCOVERY,
            artifact_reference="snapshots/discovery-phase2-v1/manifest.json",
            sample_reference="snapshot:discovery-phase2-v1",
        ),
        cost_assumptions=cost_assumptions
        if cost_assumptions is not None
        else {"spread_bps": 1.5, "commission_bps": 0.5},
        validation_method="canonical_experiment",
        random_seed=7,
    )


def _completed_trial(
    trial_id: str,
    *,
    score: float,
    turnover: float = 1.0,
    parameter: int = 1,
    checks: dict[str, bool] | None = None,
    metric_name: str = "rank_ic",
) -> DiscoveryTrial:
    return DiscoveryTrial(
        trial_id=trial_id,
        research_run_id="run-phase2",
        parameters={"lookback": parameter},
        status=TrialStatus.COMPLETED,
        metrics={
            metric_name: score,
            "turnover": turnover,
            "observation_count": 1000,
            "oos_rows": 100,
            "prediction_rows": 95,
            "oos_coverage": 0.95,
            "trade_count": 20,
            "missing_rate": 0.01,
        },
        checks=checks
        or {
            "causal_features": True,
            "target_signal_compatible": True,
            "data_quality": True,
        },
        seed=7 + parameter,
    )


def test_search_space_supports_portable_parameter_kinds_and_deterministic_roundtrip() -> None:
    space = SearchSpace(
        (
            ParameterSpec("integer", ParameterKind.INTEGER, low=1, high=5, step=2),
            ParameterSpec("float", ParameterKind.FLOAT, low=0.1, high=0.3, step=0.1),
            ParameterSpec("log_float", ParameterKind.FLOAT, low=0.001, high=1.0, log=True),
            ParameterSpec(
                "category", ParameterKind.CATEGORICAL, values=("a", "b")
            ),
            ParameterSpec("fixed", ParameterKind.FIXED, values=(None,)),
        )
    )

    assert space.parameters[0].grid_values() == (1, 3, 5)
    assert space.parameters[1].grid_values() == (0.1, 0.2, 0.3)
    assert space.cardinality() is None
    assert SearchSpace.from_dict(space.to_dict()) == space
    with pytest.raises(ResearchContractError, match="continuous/log-scaled"):
        space.parameters[2].grid_values()


def test_search_space_rejects_invalid_ranges_and_duplicate_names() -> None:
    with pytest.raises(ResearchContractError, match="low < high"):
        ParameterSpec("bad", ParameterKind.INTEGER, low=5, high=5)
    with pytest.raises(ResearchContractError, match="requires low > 0"):
        ParameterSpec("bad_log", ParameterKind.FLOAT, low=0.0, high=1.0, log=True)
    with pytest.raises(ResearchContractError, match="cannot contain duplicates"):
        ParameterSpec(
            "duplicate_values",
            ParameterKind.CATEGORICAL,
            values=("x", "x"),
        )
    parameter = ParameterSpec("duplicate", ParameterKind.FIXED, values=(1,))
    with pytest.raises(ResearchContractError, match="names must be unique"):
        SearchSpace((parameter, parameter))


def test_specification_hash_is_canonical_and_final_holdout_is_forbidden() -> None:
    specification = _specification()

    assert DiscoverySpecification.from_dict(specification.to_dict()) == specification
    assert (
        DiscoverySpecification.from_dict(specification.to_dict()).specification_hash
        == specification.specification_hash
    )
    with pytest.raises(ResearchContractError, match="development/DISCOVERY"):
        _specification(
            evidence_reference=EvidenceReference(
                stage=EvidenceStage.FINAL_HOLDOUT,
                evidence_role=EvidenceRole.PROSPECTIVE_FINAL,
                artifact_reference="final/manifest.json",
                sample_reference="snapshot:discovery-phase2-v1",
            )
        )


def test_trading_metric_selection_requires_explicit_cost_assumptions() -> None:
    selection = SelectionPolicy(
        primary=MetricPreference("net_sharpe", SelectionDirection.MAXIMIZE),
        metric_basis=SelectionMetricBasis.TRADING,
        top_k=1,
    )
    with pytest.raises(ResearchContractError, match="cost_assumptions"):
        _specification(selection=selection, cost_assumptions={})


def test_trials_preserve_failure_states_and_reject_non_finite_metrics() -> None:
    failed = DiscoveryTrial(
        trial_id="run-phase2-trial-failed",
        research_run_id="run-phase2",
        parameters={"lookback": 2},
        status=TrialStatus.FAILED,
        metrics={},
        checks={},
        seed=8,
        failure_reason="synthetic failure",
    )
    assert DiscoveryTrial.from_dict(failed.to_dict()) == failed
    with pytest.raises(ResearchContractError, match="finite"):
        TrialEvaluation(
            status=TrialStatus.COMPLETED,
            metrics={"rank_ic": float("nan")},
        )
    with pytest.raises(ResearchContractError, match="requires low"):
        ParameterSpec("invalid", ParameterKind.FLOAT, high=1.0)


def test_ranking_applies_eligibility_before_metric_and_breaks_ties_deterministically() -> None:
    specification = _specification()
    trials = (
        _completed_trial("run-phase2-trial-b", score=0.2, turnover=2.0, parameter=2),
        _completed_trial("run-phase2-trial-a", score=0.2, turnover=1.0, parameter=1),
        _completed_trial("run-phase2-trial-c", score=0.5, turnover=8.0, parameter=3),
        DiscoveryTrial(
            trial_id="run-phase2-trial-d",
            research_run_id="run-phase2",
            parameters={"lookback": 4},
            status=TrialStatus.PRUNED,
            metrics={},
            checks={},
            seed=11,
            failure_reason="median pruner",
        ),
    )

    ranking = rank_trials(specification, trials)

    assert ranking.total_trial_count == 4
    assert ranking.completed_trial_count == 3
    assert ranking.eligible_candidate_count == 2
    assert ranking.entry_for("run-phase2-trial-a").rank == 1
    assert ranking.entry_for("run-phase2-trial-b").rank == 2
    assert ranking.entry_for("run-phase2-trial-c").rank is None
    assert ranking.rejection_counts["turnover_limit_exceeded"] == 1
    assert type(ranking).from_dict(ranking.to_dict()) == ranking


def test_minimize_ranking_missing_metric_and_model_oos_gates_fail_closed() -> None:
    selection = SelectionPolicy(
        primary=MetricPreference("loss", SelectionDirection.MINIMIZE),
        metric_basis=SelectionMetricBasis.PREDICTION,
        top_k=1,
    )
    specification = _specification(
        selection=selection,
        model_families=("logistic_regression_clf",),
    )
    missing_oos_checks = _completed_trial(
        "run-phase2-trial-model-a",
        score=0.2,
        parameter=1,
        metric_name="loss",
    )
    missing_metric = replace(
        _completed_trial(
            "run-phase2-trial-model-b",
            score=0.1,
            parameter=2,
            metric_name="loss",
        ),
        metrics={
            "turnover": 1.0,
            "observation_count": 1000,
            "oos_rows": 100,
            "oos_coverage": 0.95,
            "trade_count": 20,
            "missing_rate": 0.01,
        },
    )

    ranking = rank_trials(specification, (missing_oos_checks, missing_metric))

    assert ranking.eligible_candidate_count == 0
    assert ranking.rejection_counts["required_check_failed:oos_predictions"] == 2
    assert ranking.rejection_counts["required_check_failed:fold_safe_preprocessing"] == 2
    assert ranking.rejection_counts["missing_selection_metric:loss"] == 1


def test_parameter_neighborhood_analysis_is_configuration_driven() -> None:
    trials = (
        _completed_trial("run-phase2-trial-center", score=0.30, parameter=2),
        _completed_trial("run-phase2-trial-low", score=0.27, parameter=1),
        _completed_trial("run-phase2-trial-high", score=0.10, parameter=3),
    )

    stability = analyze_parameter_neighborhood(
        trials,
        candidate_trial_id="run-phase2-trial-center",
        parameter_name="lookback",
        selection_metric="rank_ic",
        direction=SelectionDirection.MAXIMIZE,
        configured_max_degradation=0.05,
    )

    assert stability.status.value == "fail"
    assert stability.details["failed_neighbor_ids"] == ["run-phase2-trial-high"]
    assert type(stability).from_dict(stability.to_dict()) == stability


def test_end_to_end_discovery_preserves_breadth_provenance_and_stops_at_validation(
    tmp_path: Path,
) -> None:
    specification = _specification()

    def evaluator(proposal):
        lookback = int(proposal.parameters["lookback"])
        if lookback == 3:
            return TrialEvaluation(
                status=TrialStatus.PRUNED,
                failure_reason="synthetic pruner",
            )
        if lookback == 4:
            raise RuntimeError("synthetic evaluator failure")
        return TrialEvaluation(
            status=TrialStatus.COMPLETED,
            metrics={
                "rank_ic": 0.10 * lookback,
                "turnover": 1.0,
                "observation_count": 1000,
                "oos_rows": 100,
                "prediction_rows": 95,
                "oos_coverage": 0.95,
                "trade_count": 5 if lookback == 1 else 20,
                "missing_rate": 0.01,
            },
            checks={
                "causal_features": True,
                "target_signal_compatible": True,
                "data_quality": True,
            },
            artifact_references=(f"trials/lookback-{lookback}.json",),
            runtime_metadata={"worker": "synthetic"},
        )

    store = FilesystemResearchStore(tmp_path / "research_records")
    result = run_discovery(
        _hypothesis(),
        specification,
        executor=GridCandidateGenerator(),
        research_run_id="run-phase2",
        request_id="request-phase2",
        started_at=NOW,
        completed_at=LATER,
        evaluator=evaluator,
        backend_version="1",
        git_revision="deadbeef",
        runtime_provenance={"python": "synthetic"},
        duplicate_of_run_ids=("run-prior",),
        record_store=store,
    )

    assert [trial.status.value for trial in result.trials] == [
        "completed",
        "completed",
        "pruned",
        "failed",
    ]
    assert result.ranking.total_trial_count == 4
    assert result.ranking.eligible_candidate_count == 1
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.status is CandidateStatus.PENDING_CANONICAL_VALIDATION
    assert candidate.search_metadata["total_trial_count"] == 4
    assert candidate.search_metadata["pruned_trial_count"] == 1
    assert candidate.search_metadata["failed_trial_count"] == 1
    assert candidate.hypothesis_id == "hypothesis-phase2"
    assert candidate.research_run_id == "run-phase2"
    assert candidate.selection_id == result.selections[0].selection_id
    assert result.validation_requests[0].required_evidence_stage is EvidenceStage.VALIDATION
    assert result.validation_requests[0].required_evidence_role is EvidenceRole.VALIDATION
    assert store.load_candidate(candidate.candidate_id).status is CandidateStatus.PENDING_CANONICAL_VALIDATION
    with pytest.raises(ResearchContractError, match="Invalid candidate transition"):
        from src.research.lifecycle import transition_candidate

        transition_candidate(candidate, CandidateStatus.VALIDATED)

    writer = DiscoveryArtifactWriter(tmp_path / "discovery_artifacts")
    manifest = writer.write(result)
    assert set(manifest.artifacts) == {
        "discovery_spec",
        "trials",
        "ranking",
        "selected_candidates",
        "canonical_validation_requests",
        "parameter_neighborhood",
        "discovery_summary",
        "discovery_report",
    }
    trial_lines = manifest.artifacts["trials"].read_text().splitlines()
    assert len(trial_lines) == 4
    assert [json.loads(line)["status"] for line in trial_lines] == [
        "completed",
        "completed",
        "pruned",
        "failed",
    ]
    summary = json.loads(manifest.artifacts["discovery_summary"].read_text())
    assert summary["failed_trials"] == 1
    assert summary["pruned_trials"] == 1
    assert summary["validation_boundary"]["required_evidence_role"] == "VALIDATION"
    with pytest.raises(DiscoveryArtifactError, match="already exist"):
        writer.write(result)


def test_candidate_identity_is_stable_across_intentional_reruns() -> None:
    def evaluator(proposal):
        return TrialEvaluation(
            status=TrialStatus.COMPLETED,
            metrics={
                "rank_ic": 0.1 * int(proposal.parameters["lookback"]),
                "turnover": 1.0,
                "observation_count": 1000,
                "oos_rows": 100,
                "oos_coverage": 0.95,
                "trade_count": 20,
                "missing_rate": 0.01,
            },
            checks={
                "causal_features": True,
                "target_signal_compatible": True,
                "data_quality": True,
            },
        )

    first = run_discovery(
        _hypothesis(),
        _specification(),
        executor=GridCandidateGenerator(),
        research_run_id="run-rerun-a",
        request_id="request-rerun-a",
        started_at=NOW,
        completed_at=LATER,
        evaluator=evaluator,
    )
    second = run_discovery(
        _hypothesis(),
        _specification(),
        executor=GridCandidateGenerator(),
        research_run_id="run-rerun-b",
        request_id="request-rerun-b",
        started_at=NOW,
        completed_at=LATER,
        evaluator=evaluator,
        duplicate_of_run_ids=("run-rerun-a",),
    )

    assert first.specification.specification_hash == second.specification.specification_hash
    assert first.candidates[0].candidate_id == second.candidates[0].candidate_id
    assert second.duplicate_of_run_ids == ("run-rerun-a",)


def test_unknown_registry_component_fails_before_executor_runs() -> None:
    bad_specification = replace(
        _specification(), feature_families=("does_not_exist",)
    )

    class ForbiddenExecutor:
        name = "grid"
        backend_name = "forbidden"

        def execute(self, *args, **kwargs):
            raise AssertionError("executor must not run")

    with pytest.raises(Exception, match="Unknown feature 'does_not_exist'"):
        run_discovery(
            _hypothesis(),
            bad_specification,
            executor=ForbiddenExecutor(),
            research_run_id="run-invalid-component",
            request_id="request-invalid-component",
            started_at=NOW,
            completed_at=LATER,
        )
