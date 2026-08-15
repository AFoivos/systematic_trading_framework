"""Approval-gated AR-0004 cloud ML discovery orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.research import (
    DiscoverySpecification,
    DiscoveryTrial,
    EligibilityPolicy,
    EligibilityRule,
    EvidenceReference,
    EvidenceStage,
    MetricPreference,
    MinimumDataRequirements,
    ParameterKind,
    ParameterSpec,
    ResearchHypothesis,
    RuleOperator,
    SearchSpace,
    SelectionDirection,
    SelectionMetricBasis,
    SelectionPolicy,
    TrialStatus,
    run_discovery,
)
from src.research.ar0004_runtime import (
    AR0004BuiltPanel,
    CandidateEvaluation,
    build_ar0004_panel,
    run_ar0004_tournament,
    trial_identity,
)
from src.src_data.research_roles import EvidenceRole
from src.utils.alpha_discovery_config import AlphaDiscoveryStatus
from src.utils.alpha_discovery_v4_config import validate_alpha_discovery_v4_config
from src.utils.config import load_experiment_config
from src.utils.paths import PROJECT_ROOT


class CloudAlphaExecutionRefused(RuntimeError):
    """Raised before data/model access when AR-0004 is not approved exactly."""


class _PrecomputedScreeningExecutor:
    name = "ar0004_cloud_tournament"
    backend_name = "stf_cloud_walk_forward_lightgbm"
    backend_version = "ar0004-v1"

    def __init__(self, trials: Sequence[DiscoveryTrial]) -> None:
        self.trials = tuple(trials)

    def execute(
        self,
        specification: DiscoverySpecification,
        *,
        research_run_id: str,
        evaluator: Any = None,
    ) -> tuple[DiscoveryTrial, ...]:
        if evaluator is not None:
            raise CloudAlphaExecutionRefused("AR-0004 does not accept evaluator injection.")
        if specification.search_method != self.name:
            raise CloudAlphaExecutionRefused("AR-0004 search-method identity drifted.")
        if any(trial.research_run_id != research_run_id for trial in self.trials):
            raise CloudAlphaExecutionRefused("AR-0004 precomputed trial/run mismatch.")
        return self.trials


def _normalized_parameters(evaluation: CandidateEvaluation) -> dict[str, Any]:
    parameters = dict(evaluation.parameters)
    parameters.setdefault("ensemble_member_trials", [])
    required = {
        "candidate_kind",
        "source_trial_number",
        "ensemble_member_trials",
        "feature_set",
        "horizon_bars",
        "n_estimators",
        "learning_rate",
        "num_leaves",
        "max_depth",
        "min_child_samples",
        "subsample",
        "colsample_bytree",
        "reg_alpha",
        "reg_lambda",
    }
    if set(parameters) != required:
        raise CloudAlphaExecutionRefused(
            f"AR-0004 trial parameters drifted: {sorted(set(parameters) ^ required)}"
        )
    return parameters


def _portable_metrics(values: Mapping[str, Any]) -> dict[str, int | float | None]:
    output: dict[str, int | float | None] = {}
    for name, value in values.items():
        if value is None or isinstance(value, (int, float)) and not isinstance(value, bool):
            output[str(name)] = value
    return output


def _discovery_trials(
    cfg: Mapping[str, Any],
    evaluations: Sequence[CandidateEvaluation],
    *,
    research_run_id: str,
) -> tuple[tuple[DiscoveryTrial, ...], dict[str, CandidateEvaluation]]:
    gates = cfg["candidate_gates"]
    trials: list[DiscoveryTrial] = []
    by_trial: dict[str, CandidateEvaluation] = {}
    for evaluation in evaluations:
        parameters = _normalized_parameters(evaluation)
        trial_id = trial_identity(parameters)
        metrics = _portable_metrics(evaluation.metrics)
        checks = {
            "causal_features": True,
            "target_signal_compatible": True,
            "fold_safe_preprocessing": True,
            "oos_predictions": True,
            "chronological_walk_forward": evaluation.status == "COMPLETED",
            "target_horizon_purge": evaluation.status == "COMPLETED",
            "screening_only": True,
            "no_portfolio_semantics": True,
            "global_by": bool(
                metrics.get("global_by_p_value") is not None
                and float(metrics["global_by_p_value"]) <= float(cfg["inference"]["false_discovery_rate"])
            ),
            "bootstrap_positive": bool(
                metrics.get("bootstrap_confidence_lower") is not None
                and float(metrics["bootstrap_confidence_lower"]) > 0.0
            ),
            "positive_all_screening_folds": bool(
                metrics.get("positive_fold_count") == len(cfg["walk_forward"]["screening_folds"])
                and metrics.get("worst_fold_rank_correlation") is not None
                and float(metrics["worst_fold_rank_correlation"]) > 0.0
            ),
            "stressed_cost_positive": bool(
                metrics.get("stressed_top_bottom_return") is not None
                and float(metrics["stressed_top_bottom_return"]) > 0.0
            ),
        }
        status = TrialStatus.COMPLETED if evaluation.status == "COMPLETED" else TrialStatus.INVALID
        trial = DiscoveryTrial(
            trial_id=trial_id,
            research_run_id=research_run_id,
            parameters=parameters,
            status=status,
            metrics=metrics,
            checks=checks,
            seed=int(cfg["model_search"]["sampler"]["seed"]),
            failure_reason=evaluation.failure_reason,
            runtime_metadata={
                "backend_name": "stf_cloud_walk_forward_lightgbm",
                "backend_version": "ar0004-v1",
                "evidence_role": "DISCOVERY",
                "screening_only": True,
                "canonical_validation_required": True,
                "fold_metrics": [item.to_dict() for item in evaluation.fold_metrics],
                "oos_predictions_backfilled": False,
                "cost_stress_multiplier": cfg["cost_policy"]["stress_multiplier"],
                "candidate_gates": dict(gates),
            },
        )
        trials.append(trial)
        by_trial[trial_id] = evaluation
    return tuple(trials), by_trial


def _search_space(cfg: Mapping[str, Any]) -> SearchSpace:
    space = cfg["model_search"]["space"]
    return SearchSpace(
        (
            ParameterSpec("candidate_kind", ParameterKind.CATEGORICAL, values=("model", "ensemble")),
            ParameterSpec("source_trial_number", ParameterKind.INTEGER, low=-1, high=383),
            ParameterSpec("ensemble_member_trials", ParameterKind.FIXED, values=([],)),
            ParameterSpec("feature_set", ParameterKind.CATEGORICAL, values=tuple(space["feature_set"])),
            ParameterSpec("horizon_bars", ParameterKind.CATEGORICAL, values=tuple(space["horizon_bars"])),
            ParameterSpec("n_estimators", ParameterKind.INTEGER, **space["n_estimators"]),
            ParameterSpec("learning_rate", ParameterKind.FLOAT, **space["learning_rate"]),
            ParameterSpec("num_leaves", ParameterKind.INTEGER, **space["num_leaves"]),
            ParameterSpec("max_depth", ParameterKind.CATEGORICAL, values=tuple(space["max_depth"])),
            ParameterSpec("min_child_samples", ParameterKind.INTEGER, **space["min_child_samples"]),
            ParameterSpec("subsample", ParameterKind.FLOAT, **space["subsample"]),
            ParameterSpec("colsample_bytree", ParameterKind.FLOAT, **space["colsample_bytree"]),
            ParameterSpec("reg_alpha", ParameterKind.FLOAT, **space["reg_alpha"]),
            ParameterSpec("reg_lambda", ParameterKind.FLOAT, **space["reg_lambda"]),
        )
    )


def _specification(
    cfg: Mapping[str, Any], built: AR0004BuiltPanel
) -> DiscoverySpecification:
    gates = cfg["candidate_gates"]
    return DiscoverySpecification(
        hypothesis_id="hypothesis-ar0004-cross-asset-walk-forward",
        assets=tuple(cfg["asset_universe"]["asset_ids"]),
        timeframe="30m",
        feature_families=("multi_horizon_trend_quality_volatility_cross_sectional",),
        target_family="future_executable_long_coordinate_return",
        model_families=("lightgbm_regressor",),
        signal_families=(),
        search_method="ar0004_cloud_tournament",
        trial_budget=int(cfg["inference"]["screening_family_size"]),
        search_space=_search_space(cfg),
        selection=SelectionPolicy(
            primary=MetricPreference("mean_rank_correlation", SelectionDirection.MAXIMIZE),
            metric_basis=SelectionMetricBasis.PREDICTION,
            top_k=int(cfg["screening_evaluation"]["candidate_top_k"]),
            tie_breakers=(
                MetricPreference("worst_fold_rank_correlation", SelectionDirection.MAXIMIZE),
                MetricPreference("stressed_top_bottom_return", SelectionDirection.MAXIMIZE),
                MetricPreference("rmse", SelectionDirection.MINIMIZE),
            ),
        ),
        eligibility=EligibilityPolicy(
            minimum_data=MinimumDataRequirements(
                minimum_observations=int(gates["minimum_oos_rows"]),
                minimum_oos_rows=int(gates["minimum_oos_rows"]),
                minimum_coverage=float(gates["minimum_oos_coverage"]),
                maximum_missing_rate=float(1.0 - gates["minimum_oos_coverage"]),
            ),
            metric_rules=(
                EligibilityRule("mean_rank_correlation", RuleOperator.GT, 0.0, "non_positive_mean_rank_ic"),
                EligibilityRule("worst_fold_rank_correlation", RuleOperator.GT, 0.0, "non_positive_screening_fold"),
                EligibilityRule("bootstrap_confidence_lower", RuleOperator.GT, 0.0, "bootstrap_lower_not_positive"),
                EligibilityRule("global_by_p_value", RuleOperator.LE, 0.05, "global_by_failed"),
                EligibilityRule("stressed_top_bottom_return", RuleOperator.GT, 0.0, "stressed_cost_return_not_positive"),
            ),
            required_checks=(
                "chronological_walk_forward",
                "target_horizon_purge",
                "screening_only",
                "no_portfolio_semantics",
                "global_by",
                "bootstrap_positive",
                "positive_all_screening_folds",
                "stressed_cost_positive",
            ),
        ),
        config_reference="config/research/alpha_discovery/AR-0004_cloud_alpha_tournament.yaml",
        config_hash=str(cfg["specification_hash"]),
        dataset_reference="AR-0004-RUNTIME-BUILT-DISCOVERY-PANEL-V1",
        dataset_fingerprint=built.dataset_fingerprint,
        evidence_reference=EvidenceReference(
            stage=EvidenceStage.DEVELOPMENT,
            evidence_role=EvidenceRole.DISCOVERY,
            artifact_reference="data/raw/dukascopy_30m_clean#frozen-sha256-map",
            sample_reference="AR-0004-RUNTIME-BUILT-DISCOVERY-PANEL-V1",
        ),
        cost_assumptions={
            "observed_bid_ask": True,
            "stress_multiplier": cfg["cost_policy"]["stress_multiplier"],
            "commission": cfg["cost_policy"]["commission"],
            "slippage": cfg["cost_policy"]["slippage"],
            "swap": cfg["cost_policy"]["swap"],
        },
        validation_method="canonical_experiment",
        random_seed=int(cfg["model_search"]["sampler"]["seed"]),
    )


def _hypothesis(cfg: Mapping[str, Any]) -> ResearchHypothesis:
    return ResearchHypothesis(
        hypothesis_id="hypothesis-ar0004-cross-asset-walk-forward",
        name=str(cfg["title"]),
        thesis=str(cfg["hypothesis"]["statement"]),
        assets=tuple(cfg["asset_universe"]["asset_ids"]),
        created_at="2026-08-15T00:00:00+03:00",
        timeframe="30m",
        tags=("cross_asset", "walk_forward", "lightgbm", "discovery_only"),
        feature_families=("multi_horizon_trend_quality_volatility_cross_sectional",),
        target_kind="future_executable_long_coordinate_return",
        signal_family=None,
        expected_mechanism=str(cfg["hypothesis"]["mechanism"]),
    )


def run_alpha_discovery_v4_pipeline(config_path: str | Path) -> dict[str, Any]:
    """Run the approved tournament and stop at pending canonical validation."""

    cfg = load_experiment_config(config_path)
    validate_alpha_discovery_v4_config(cfg)
    if AlphaDiscoveryStatus(cfg["status"]) is not AlphaDiscoveryStatus.APPROVED_TO_RUN:
        raise CloudAlphaExecutionRefused(
            "AR-0004 is SPECIFICATION_ONLY. Approve the exact specification hash, "
            "set runtime.perform_alpha_calculation=true, and clear the blocker before running."
        )
    from src.experiments.orchestration.ar0004_artifacts import (
        ar0004_run_root,
        write_ar0004_artifacts,
    )

    run_root = ar0004_run_root(cfg)
    if run_root.exists():
        raise CloudAlphaExecutionRefused(f"Immutable AR-0004 run already exists: {run_root}")
    started_at = datetime.now(timezone.utc).isoformat()
    built = build_ar0004_panel(cfg, project_root=PROJECT_ROOT)
    study_storage = run_root.parent / ".studies" / f"{cfg['specification_hash'][:16]}.db"
    tournament = run_ar0004_tournament(cfg, built, study_storage=study_storage)
    research_run_id = f"ar0004-{cfg['specification_hash'][:16]}"
    trials, evaluation_by_trial = _discovery_trials(
        cfg, tournament["evaluations"], research_run_id=research_run_id
    )
    specification = _specification(cfg, built)
    completed_at = datetime.now(timezone.utc).isoformat()
    lifecycle = run_discovery(
        _hypothesis(cfg),
        specification,
        executor=_PrecomputedScreeningExecutor(trials),
        research_run_id=research_run_id,
        request_id=f"request-{research_run_id}",
        started_at=started_at,
        completed_at=completed_at,
        backend_version="ar0004-v1",
        runtime_provenance={
            "screening_only": True,
            "validation_accessed": False,
            "prospective_final_accessed": False,
            "portfolio_constructed": False,
            "tuning_search_breadth": tournament["search_breadth"],
        },
        validate_components=False,
    )
    return write_ar0004_artifacts(
        cfg=cfg,
        built=built,
        tournament=tournament,
        lifecycle=lifecycle,
        evaluation_by_trial=evaluation_by_trial,
    )


__all__ = ["CloudAlphaExecutionRefused", "run_alpha_discovery_v4_pipeline"]
