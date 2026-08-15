from __future__ import annotations

from types import SimpleNamespace

from src.experiments.optuna_discovery import (
    ExistingOptunaSearchExecutor,
    to_existing_optuna_search_dimensions,
)
from src.research import CandidateStatus, EvidenceReference, EvidenceStage
from src.research.discovery import (
    DiscoverySpecification,
    EligibilityPolicy,
    EligibilityRule,
    MetricPreference,
    MinimumDataRequirements,
    ParameterKind,
    ParameterSpec,
    RuleOperator,
    SearchSpace,
    SelectionMetricBasis,
    SelectionPolicy,
    TrialStatus,
    run_discovery,
)
from src.research.hypothesis import ResearchHypothesis
from src.research.run import SelectionDirection
from src.src_data.research_roles import EvidenceRole


NOW = "2026-08-14T10:00:00+00:00"
LATER = "2026-08-14T10:01:00+00:00"


def _specification() -> DiscoverySpecification:
    return DiscoverySpecification(
        hypothesis_id="hypothesis-phase2",
        assets=("ETHUSD",),
        timeframe="30m",
        feature_families=("roc",),
        target_family="forward_return",
        model_families=(),
        signal_families=(),
        search_method="optuna",
        trial_budget=4,
        search_space=SearchSpace(
            (
                ParameterSpec(
                    "lookback",
                    ParameterKind.INTEGER,
                    path="features.0.params.window",
                    low=1,
                    high=4,
                ),
            )
        ),
        selection=SelectionPolicy(
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
                    "turnover",
                    RuleOperator.LE,
                    5.0,
                    "turnover_limit_exceeded",
                ),
            ),
            required_checks=("data_quality",),
        ),
        config_reference="config/experiments/synthetic_phase2.yaml#frozen",
        config_hash="b" * 64,
        dataset_reference="snapshot:discovery-phase2-v1",
        dataset_fingerprint={"sha256": "c" * 64, "rows": 1000},
        evidence_reference=EvidenceReference(
            stage=EvidenceStage.DEVELOPMENT,
            evidence_role=EvidenceRole.DISCOVERY,
            artifact_reference="snapshots/discovery-phase2-v1/manifest.json",
            sample_reference="snapshot:discovery-phase2-v1",
        ),
        cost_assumptions={"spread_bps": 1.5},
        validation_method="canonical_experiment",
        random_seed=7,
    )


def test_neutral_search_space_maps_to_existing_optuna_dimensions() -> None:
    dimensions = to_existing_optuna_search_dimensions(
        SearchSpace(
            (
                ParameterSpec(
                    "integer",
                    ParameterKind.INTEGER,
                    path="model.params.depth",
                    low=2,
                    high=8,
                    step=2,
                ),
                ParameterSpec(
                    "log_float",
                    ParameterKind.FLOAT,
                    path="model.params.learning_rate",
                    low=0.001,
                    high=0.1,
                    log=True,
                ),
                ParameterSpec(
                    "category",
                    ParameterKind.CATEGORICAL,
                    path="model.kind",
                    values=("a", "b"),
                ),
                ParameterSpec(
                    "fixed",
                    ParameterKind.FIXED,
                    path="signals.params.delay",
                    values=(1,),
                ),
            )
        )
    )

    assert [dimension.kind for dimension in dimensions] == [
        "int",
        "float",
        "categorical",
        "categorical",
    ]
    assert dimensions[1].log is True
    assert list(dimensions[2].choices or ()) == ["a", "b"]
    assert list(dimensions[3].choices or ()) == [1]


def test_existing_optuna_executor_preserves_all_trial_states_and_search_breadth() -> None:
    captured = {}

    class State:
        def __init__(self, name: str) -> None:
            self.name = name

    complete_metrics = {
        "observation_count": 1000,
        "oos_rows": 100,
        "prediction_rows": 95,
        "oos_coverage": 0.95,
        "trade_count": 20,
        "missing_rate": 0.01,
        "turnover": 1.0,
    }
    trials = (
        SimpleNamespace(
            number=0,
            state=State("COMPLETE"),
            value=0.25,
            params={"lookback": 2},
            user_attrs={
                "trial_failed": False,
                "primary_summary": complete_metrics,
                "discovery_checks": {
                    "causal_features": True,
                    "target_signal_compatible": True,
                    "data_quality": True,
                },
                "experiment_run_dir": "logs/experiments/trial-0",
            },
        ),
        SimpleNamespace(
            number=1,
            state=State("COMPLETE"),
            value=-1.0e12,
            params={"lookback": 1},
            user_attrs={
                "trial_failed": True,
                "exception": "RuntimeError: synthetic",
            },
        ),
        SimpleNamespace(
            number=2,
            state=State("PRUNED"),
            value=None,
            params={"lookback": 3},
            user_attrs={},
        ),
        SimpleNamespace(
            number=3,
            state=State("FAIL"),
            value=None,
            params={},
            user_attrs={"exception": "ValueError: invalid"},
        ),
    )

    def fake_study_runner(config_path, **kwargs):
        captured["config_path"] = config_path
        captured.update(kwargs)
        return SimpleNamespace(study_name="phase2-fake", trials=trials)

    specification = _specification()
    executor = ExistingOptunaSearchExecutor(
        "config/experiments/synthetic_phase2.yaml",
        study_runner=fake_study_runner,
    )
    hypothesis = ResearchHypothesis(
        hypothesis_id="hypothesis-phase2",
        name="Synthetic causal discovery",
        thesis="Existing Optuna results remain screening evidence.",
        assets=("ETHUSD",),
        timeframe="30m",
        created_at=NOW,
        feature_families=("roc",),
        target_kind="forward_return",
    )

    result = run_discovery(
        hypothesis,
        specification,
        executor=executor,
        research_run_id="run-optuna-phase2",
        request_id="request-optuna-phase2",
        started_at=NOW,
        completed_at=LATER,
    )

    assert captured["n_trials"] == 4
    assert captured["seed"] == 7
    assert captured["objective"].metric_path == "rank_ic"
    assert [trial.status for trial in result.trials] == [
        TrialStatus.COMPLETED,
        TrialStatus.FAILED,
        TrialStatus.PRUNED,
        TrialStatus.FAILED,
    ]
    assert result.ranking.total_trial_count == 4
    assert result.ranking.completed_trial_count == 1
    assert len(result.candidates) == 1
    assert result.candidates[0].status is CandidateStatus.PENDING_CANONICAL_VALIDATION
    assert result.candidates[0].search_metadata["failed_trial_count"] == 2
    assert result.candidates[0].search_metadata["pruned_trial_count"] == 1
