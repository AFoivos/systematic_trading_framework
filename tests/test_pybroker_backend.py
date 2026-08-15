from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

from src.experiments.discovery_executors import get_discovery_executor
from src.research import CandidateStatus, EvidenceReference, EvidenceStage
from src.research.contracts import ResearchContractError
from src.research.discovery import (
    DiscoverySpecification,
    DiscoveryTrial,
    EligibilityPolicy,
    MetricPreference,
    MinimumDataRequirements,
    ParameterKind,
    ParameterSpec,
    SearchSpace,
    SelectionMetricBasis,
    SelectionPolicy,
    TrialStatus,
    run_discovery,
)
from src.research.hypothesis import ResearchHypothesis
from src.research.run import SelectionDirection
from src.research.backends.pybroker import (
    PYBROKER_CAPABILITIES,
    PYBROKER_PIN,
    PyBrokerCostMapping,
    PyBrokerDependencyError,
    PyBrokerFoldPolicy,
    PyBrokerInputError,
    PyBrokerParameterMapping,
    PyBrokerPreprocessingPolicy,
    PyBrokerResearchData,
    PyBrokerResourceLimitError,
    PyBrokerResourcePolicy,
    PyBrokerSearchExecutor,
    PyBrokerSignalPolicy,
    PyBrokerTimingPolicy,
    PyBrokerUnsupportedSemanticsError,
    pybroker_version,
)
from src.research.backends.pybroker.diagnostics import fold_trading_diagnostics
from src.src_data.research_roles import EvidenceRole


CONFIG_HASH = "6" * 64
DATA_HASH = "7" * 64
NOW = "2026-08-14T10:00:00+00:00"
LATER = "2026-08-14T10:01:00+00:00"


def _frame(rows: int = 80) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=rows, freq="30min", tz="UTC")
    phase = np.arange(rows, dtype=float)
    feature_a = np.sin(phase / 2.0)
    feature_b = np.cos(phase / 3.0) + phase / 200.0
    target = (feature_a + 0.2 * feature_b > 0.0).astype(float)
    target[-1] = np.nan
    open_price = 100.0 * np.cumprod(1.0 + 0.002 * np.sign(feature_a + 0.05))
    return pd.DataFrame(
        {
            "open": open_price,
            "close": open_price * (1.0 + 0.0002),
            "feature_a": feature_a,
            "feature_b": feature_b,
            "target": target,
        },
        index=index,
    )


def _research_data(frame: pd.DataFrame | None = None) -> PyBrokerResearchData:
    return PyBrokerResearchData(
        frame=_frame() if frame is None else frame,
        asset="ETHUSD",
        timeframe="30m",
        feature_columns=("feature_a", "feature_b"),
        target_column="target",
        target_family="forward_return",
        target_horizon=1,
        checks={
            "causal_features": True,
            "target_signal_compatible": True,
        },
        metadata={"source": "synthetic_framework_features_and_target"},
    )


def _search_space() -> SearchSpace:
    return SearchSpace(
        (
            ParameterSpec(
                name="model_c",
                kind=ParameterKind.CATEGORICAL,
                path="model.params.C",
                values=(0.5, 1.0),
            ),
            ParameterSpec(
                name="signal_threshold",
                kind=ParameterKind.CATEGORICAL,
                path="signals.params.threshold",
                values=(0.45, 0.55),
            ),
        )
    )


def _single_search_space() -> SearchSpace:
    return SearchSpace(
        (
            ParameterSpec(
                name="model_c",
                kind=ParameterKind.FIXED,
                path="model.params.C",
                values=(1.0,),
            ),
            ParameterSpec(
                name="signal_threshold",
                kind=ParameterKind.FIXED,
                path="signals.params.threshold",
                values=(0.50,),
            ),
        )
    )


def _specification(
    *,
    search_space: SearchSpace | None = None,
    trial_budget: int = 4,
    cost_assumptions: dict[str, float] | None = None,
    model_families: tuple[str, ...] = ("logistic_regression_clf",),
) -> DiscoverySpecification:
    return DiscoverySpecification(
        hypothesis_id="hypothesis-pybroker-phase3b",
        assets=("ETHUSD",),
        timeframe="30m",
        feature_families=("roc",),
        target_family="forward_return",
        model_families=model_families,
        signal_families=("meta_probability_side",),
        search_method="pybroker",
        trial_budget=trial_budget,
        search_space=search_space or _search_space(),
        selection=SelectionPolicy(
            primary=MetricPreference("sharpe", SelectionDirection.MAXIMIZE),
            metric_basis=SelectionMetricBasis.TRADING,
            top_k=1,
            tie_breakers=(
                MetricPreference("brier", SelectionDirection.MINIMIZE),
            ),
        ),
        eligibility=EligibilityPolicy(
            minimum_data=MinimumDataRequirements(
                minimum_observations=80,
                minimum_oos_rows=40,
                minimum_trades=0,
                minimum_coverage=0.90,
                maximum_missing_rate=0.10,
            ),
            required_checks=(
                "data_quality",
                "chronological_folds",
                "purge_applied",
                "embargo_preserved",
                "timing_mapping_supported",
                "cost_mapping_supported",
                "screening_only",
            ),
        ),
        config_reference="config/experiments/synthetic_pybroker_phase3b.yaml#frozen",
        config_hash=CONFIG_HASH,
        dataset_reference="snapshot:synthetic-pybroker-phase3b-v1",
        dataset_fingerprint={"sha256": DATA_HASH, "rows": 80},
        evidence_reference=EvidenceReference(
            stage=EvidenceStage.DEVELOPMENT,
            evidence_role=EvidenceRole.DISCOVERY,
            artifact_reference="snapshots/synthetic-pybroker-phase3b-v1/manifest.json",
            sample_reference="snapshot:synthetic-pybroker-phase3b-v1",
        ),
        cost_assumptions=(
            cost_assumptions
            if cost_assumptions is not None
            else {
                "cost_per_turnover": 0.0003,
                "slippage_per_turnover": 0.0001,
            }
        ),
        validation_method="canonical_experiment",
        random_seed=23,
    )


def _executor(
    *,
    data: PyBrokerResearchData | None = None,
    artifact_root: Path | None = None,
    folds: PyBrokerFoldPolicy | None = None,
    resources: PyBrokerResourcePolicy | None = None,
    dependency_loader=None,
    base_model_parameters: dict | None = None,
) -> PyBrokerSearchExecutor:
    kwargs = {}
    if dependency_loader is not None:
        kwargs["dependency_loader"] = dependency_loader
    return PyBrokerSearchExecutor(
        data or _research_data(),
        folds=folds
        or PyBrokerFoldPolicy(
            train_size=20,
            test_size=10,
            purge_bars=1,
            embargo_bars=2,
            expanding=True,
            max_folds=5,
            minimum_train_rows=10,
        ),
        signal=PyBrokerSignalPolicy(
            threshold_parameter="signal_threshold"
        ),
        parameter_mapping=PyBrokerParameterMapping(
            model_parameters={"model_c": "C"}
        ),
        preprocessing=PyBrokerPreprocessingPolicy(scaler="standard"),
        timing=PyBrokerTimingPolicy(),
        base_model_parameters=base_model_parameters,
        periods_per_year=365 * 48,
        resources=resources,
        artifact_root=artifact_root,
        **kwargs,
    )


def test_core_import_is_dependency_safe_and_pybroker_pin_is_current() -> None:
    sys.modules.pop("pybroker", None)
    import src.research as research

    assert research.DiscoveryTrial.__name__ == DiscoveryTrial.__name__
    assert "pybroker" not in sys.modules
    assert pybroker_version() == PYBROKER_PIN == "1.2.14"
    assert "pybroker" not in sys.modules


def test_optional_dependency_errors_are_actionable_and_version_drift_fails(monkeypatch) -> None:
    from src.research.backends.pybroker import optional_dependency

    monkeypatch.setattr(optional_dependency, "version", lambda name: "1.2.13")
    with pytest.raises(PyBrokerDependencyError, match="reproducibility pin"):
        optional_dependency.load_pybroker()

    monkeypatch.setattr(optional_dependency, "version", lambda name: PYBROKER_PIN)

    def missing_import(name: str):
        error = ModuleNotFoundError(f"No module named {name!r}")
        error.name = name
        raise error

    monkeypatch.setattr(optional_dependency, "import_module", missing_import)
    with pytest.raises(
        PyBrokerDependencyError,
        match=r"optional dependency.*requirements\.pybroker\.txt",
    ):
        optional_dependency.load_pybroker()


def test_capabilities_declare_only_the_bounded_ml_scope() -> None:
    assert PYBROKER_CAPABILITIES == {
        "ml_walk_forward",
        "supervised_model_screening",
        "oos_prediction_screening",
        "chronological_fold_evaluation",
        "probability_signal_screening",
    }
    assert PYBROKER_CAPABILITIES.isdisjoint(
        {
            "vectorized_rule_screening",
            "portfolio_optimization",
            "event_driven_execution",
            "live_execution",
            "reinforcement_learning",
        }
    )


def test_real_pybroker_callbacks_emit_only_chronological_oos_predictions() -> None:
    trial = _executor().execute(
        _specification(search_space=_single_search_space(), trial_budget=1),
        research_run_id="run-pybroker-oos",
    )[0]

    assert trial.status is TrialStatus.COMPLETED
    assert trial.metrics["oos_rows"] == 50
    assert trial.metrics["oos_prediction_rows"] == 50
    assert trial.metrics["missing_oos_rows"] == 0
    assert trial.metrics["oos_coverage"] == 1.0
    coverage = trial.runtime_metadata["prediction_coverage"]
    assert coverage["non_oos_prediction_rows"] == 0
    provenance = trial.runtime_metadata["oos_prediction_provenance"]
    assert len(provenance) == 50
    assert all(row["trained_without_this_row"] for row in provenance)
    assert all(row["is_oos"] for row in provenance)
    assert all(
        pd.Timestamp(row["model_fit_end_timestamp"])
        < pd.Timestamp(row["prediction_timestamp"])
        for row in provenance
    )
    assert all(
        fold["purge_bars"] == 1 and fold["embargo_bars"] == 2
        for fold in trial.runtime_metadata["folds"]
    )
    assert trial.runtime_metadata["model"]["shuffle"] is False
    assert trial.runtime_metadata["model"]["refit_per_fold"] is True


def test_future_rows_cannot_change_an_earlier_fold_preprocessor_or_predictions() -> None:
    specification = _specification(
        search_space=_single_search_space(), trial_budget=1
    )
    original = _executor().execute(
        specification,
        research_run_id="run-pybroker-train-only-original",
    )[0]
    changed_frame = _frame()
    changed_frame.loc[changed_frame.index[70:], "feature_a"] = 1_000_000.0
    changed_frame.loc[changed_frame.index[70:], "feature_b"] = -1_000_000.0
    changed = _executor(data=_research_data(changed_frame)).execute(
        specification,
        research_run_id="run-pybroker-train-only-changed",
    )[0]

    first_fold_original = [
        row["probability"]
        for row in original.runtime_metadata["oos_prediction_provenance"]
        if row["fold_id"] == 0
    ]
    first_fold_changed = [
        row["probability"]
        for row in changed.runtime_metadata["oos_prediction_provenance"]
        if row["fold_id"] == 0
    ]
    assert first_fold_changed == pytest.approx(first_fold_original, abs=1e-12)
    assert all(
        fold["preprocessing"]["train_only"] is True
        for fold in changed.runtime_metadata["folds"]
    )


def test_missing_test_features_remain_missing_without_oos_backfill() -> None:
    frame = _frame()
    missing_timestamps = frame.index[[23, 24, 42]]
    frame.loc[missing_timestamps, "feature_a"] = np.nan
    trial = _executor(data=_research_data(frame)).execute(
        _specification(search_space=_single_search_space(), trial_budget=1),
        research_run_id="run-pybroker-missing-oos",
    )[0]

    assert trial.status is TrialStatus.COMPLETED
    assert trial.metrics["oos_rows"] == 50
    assert trial.metrics["oos_prediction_rows"] == 47
    assert trial.metrics["missing_oos_rows"] == 3
    emitted = {
        row["prediction_timestamp"]
        for row in trial.runtime_metadata["oos_prediction_provenance"]
    }
    assert emitted.isdisjoint({value.isoformat() for value in missing_timestamps})
    assert trial.runtime_metadata["prediction_coverage"]["non_oos_prediction_rows"] == 0


def test_same_close_execution_is_forbidden_and_next_open_cost_math_has_parity() -> None:
    with pytest.raises(
        PyBrokerUnsupportedSemanticsError,
        match="same-close execution is forbidden",
    ):
        PyBrokerTimingPolicy(entry_delay_bars=0)

    index = pd.date_range("2026-01-01", periods=5, freq="30min", tz="UTC")
    opens = pd.Series([100.0, 101.0, 103.0, 102.0, 104.0], index=index)
    signal = pd.Series([1.0, 1.0, 0.0, 1.0, 1.0], index=index)
    costs = PyBrokerCostMapping.from_stf_assumptions(
        {"cost_per_turnover": 0.001, "slippage_per_turnover": 0.0005}
    )
    metrics, ledger = fold_trading_diagnostics(
        open_prices=opens,
        signal=signal,
        cost_mapping=costs,
        periods_per_year=365 * 48,
    )

    execution = ledger.loc[ledger["net_return"].notna()]
    assert execution.index.tolist() == index[1:-1].tolist()
    assert execution["position"].tolist() == [1.0, 1.0, 0.0]
    expected_gross = pd.Series(
        [103.0 / 101.0 - 1.0, 102.0 / 103.0 - 1.0, 0.0],
        index=index[1:-1],
    )
    assert execution["gross_return"].tolist() == pytest.approx(
        expected_gross.tolist(), abs=1e-12
    )
    assert execution["turnover"].sum() == pytest.approx(2.0)
    expected_net = expected_gross.copy()
    expected_net.iloc[0] -= 0.0015
    expected_net.iloc[2] -= 0.0015
    assert execution["net_return"].tolist() == pytest.approx(
        expected_net.tolist(), abs=1e-12
    )
    assert metrics["turnover"] == pytest.approx(2.0)


def test_finite_search_is_deterministic_and_trials_are_strict_json() -> None:
    specification = _specification()
    first = _executor().execute(
        specification,
        research_run_id="run-pybroker-deterministic",
    )
    second = _executor().execute(
        specification,
        research_run_id="run-pybroker-deterministic",
    )

    assert len(first) == 4
    assert [trial.trial_id for trial in first] == [trial.trial_id for trial in second]
    assert [dict(trial.parameters) for trial in first] == list(
        _search_space().iter_grid()
    )
    assert [dict(trial.metrics) for trial in first] == [
        dict(trial.metrics) for trial in second
    ]
    serialized = json.dumps([trial.to_dict() for trial in first], allow_nan=False)
    assert "ModelTrainer" not in serialized
    assert "LogisticRegression(" not in serialized


def test_single_class_and_insufficient_training_folds_are_auditable_invalid_trials() -> None:
    single_class = _frame()
    single_class.loc[single_class.index[:20], "target"] = 0.0
    invalid_class = _executor(data=_research_data(single_class)).execute(
        _specification(search_space=_single_search_space(), trial_budget=1),
        research_run_id="run-pybroker-single-class",
    )[0]
    assert invalid_class.status is TrialStatus.INVALID
    assert "single_target_class" in invalid_class.failure_reason

    insufficient = _executor(
        folds=PyBrokerFoldPolicy(
            train_size=20,
            test_size=10,
            purge_bars=1,
            minimum_train_rows=25,
            max_folds=2,
        )
    ).execute(
        _specification(search_space=_single_search_space(), trial_budget=1),
        research_run_id="run-pybroker-insufficient",
    )[0]
    assert insufficient.status is TrialStatus.INVALID
    assert "insufficient_training_rows" in insufficient.failure_reason


def test_model_exception_is_retained_as_failed_trial() -> None:
    trial = _executor(base_model_parameters={"solver": "not-a-solver"}).execute(
        _specification(search_space=_single_search_space(), trial_budget=1),
        research_run_id="run-pybroker-model-exception",
    )[0]
    assert trial.status is TrialStatus.FAILED
    assert "model_exception" in trial.failure_reason
    assert trial.runtime_metadata["pybroker_version"] == PYBROKER_PIN
    assert trial.runtime_metadata["model"]["shuffle"] is False
    assert trial.runtime_metadata["target"]["horizon"] == 1
    assert trial.runtime_metadata["planned_folds"][0]["purge_bars"] == 1
    assert trial.runtime_metadata["planned_folds"][0]["embargo_bars"] == 2
    assert trial.runtime_metadata["cost_mapping"]["screening_only"] is True


def test_horizon_purge_dimension_and_unsupported_semantics_fail_closed() -> None:
    with pytest.raises(PyBrokerInputError, match="too small for the target horizon"):
        _executor(
            folds=PyBrokerFoldPolicy(
                train_size=20,
                test_size=10,
                purge_bars=0,
            )
        ).execute(
            _specification(search_space=_single_search_space(), trial_budget=1),
            research_run_id="run-pybroker-bad-purge",
        )

    with pytest.raises(PyBrokerUnsupportedSemanticsError, match="exactly model_families"):
        _executor().execute(
            _specification(
                search_space=_single_search_space(),
                trial_budget=1,
                model_families=("xgboost_clf",),
            ),
            research_run_id="run-pybroker-unsupported-model",
        )

    with pytest.raises(PyBrokerUnsupportedSemanticsError, match="approximate"):
        _executor().execute(
            _specification(
                search_space=_single_search_space(),
                trial_budget=1,
                cost_assumptions={"spread_bps_per_side": 1.0},
            ),
            research_run_id="run-pybroker-spread",
        )


def test_resource_guard_precedes_optional_dependency_loading() -> None:
    calls = {"dependency": 0}

    def forbidden_dependency():
        calls["dependency"] += 1
        raise AssertionError("dependency must not load after failed preflight")

    executor = _executor(
        resources=PyBrokerResourcePolicy(max_combinations=2),
        dependency_loader=forbidden_dependency,
    )
    with pytest.raises(PyBrokerResourceLimitError, match="resource_limit"):
        executor.execute(
            _specification(), research_run_id="run-pybroker-resource-limit"
        )
    assert calls["dependency"] == 0


def test_executor_factory_is_explicit_and_has_no_unknown_fallback() -> None:
    executor = get_discovery_executor(
        "pybroker",
        data=_research_data(),
        folds=PyBrokerFoldPolicy(train_size=20, test_size=10),
        signal=PyBrokerSignalPolicy(threshold_parameter="signal_threshold"),
        parameter_mapping=PyBrokerParameterMapping(
            model_parameters={"model_c": "C"}
        ),
        periods_per_year=365 * 48,
    )
    assert isinstance(executor, PyBrokerSearchExecutor)
    with pytest.raises(ResearchContractError, match="available:.*pybroker"):
        get_discovery_executor("unknown")


def test_candidate_stops_pending_validation_and_artifacts_are_portable(
    tmp_path: Path,
) -> None:
    specification = _specification()
    hypothesis = ResearchHypothesis(
        hypothesis_id=specification.hypothesis_id,
        name="Synthetic PyBroker screening",
        thesis="A fold-safe classifier fixture verifies the Phase 3B boundary.",
        assets=specification.assets,
        timeframe=specification.timeframe,
        created_at=NOW,
        feature_families=specification.feature_families,
        target_kind=specification.target_family,
    )
    result = run_discovery(
        hypothesis,
        specification,
        executor=_executor(artifact_root=tmp_path),
        research_run_id="run-pybroker-lifecycle",
        request_id="request-pybroker-lifecycle",
        started_at=NOW,
        completed_at=LATER,
    )

    assert result.research_run.backend == "pybroker"
    assert result.research_run.backend_version == PYBROKER_PIN
    assert result.ranking.total_trial_count == 4
    assert result.ranking.completed_trial_count == 4
    assert result.ranking.eligible_candidate_count == 4
    assert len(result.candidates) == len(result.validation_requests) == 1
    candidate = result.candidates[0]
    assert candidate.status is CandidateStatus.PENDING_CANONICAL_VALIDATION
    assert candidate.status is not CandidateStatus.VALIDATED
    assert (
        candidate.search_metadata["trial_runtime_metadata"]
        ["screening_metrics_are_canonical_evidence"]
        is False
    )
    assert (
        candidate.search_metadata["trial_runtime_metadata"]
        ["pybroker_oos_predictions_are_untouched_final_holdout"]
        is False
    )
    expected = {
        "pybroker_backend.json",
        "pybroker_fold_diagnostics.json",
        "pybroker_oos_predictions.jsonl",
        "pybroker_search_summary.json",
    }
    assert {path.name for path in tmp_path.iterdir()} == expected
    prediction_rows = [
        json.loads(line)
        for line in (tmp_path / "pybroker_oos_predictions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(prediction_rows) == 4 * 50
    assert all(row["trained_without_this_row"] for row in prediction_rows)
    for path in tmp_path.iterdir():
        assert "ModelTrainer" not in path.read_text(encoding="utf-8")

    request = result.validation_requests[0]
    assert request.validation_method == "canonical_experiment"
    assert request.required_evidence_role is EvidenceRole.VALIDATION


def test_native_outputs_never_enter_portable_trial_contract() -> None:
    trial = _executor().execute(
        _specification(search_space=_single_search_space(), trial_budget=1),
        research_run_id="run-pybroker-portable",
    )[0]
    payload = json.dumps(trial.to_dict(), allow_nan=False)
    forbidden = (
        "ExecContext",
        "Strategy",
        "TestResult",
        "DataSource",
        "numpy.ndarray",
    )
    assert all(name not in payload for name in forbidden)
