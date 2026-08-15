from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

from src.backtesting.engine import run_backtest
from src.experiments.discovery_executors import get_discovery_executor
from src.research import CandidateStatus, EvidenceReference, EvidenceStage
from src.research.contracts import ResearchContractError
from src.research.discovery import (
    DiscoverySpecification,
    DiscoveryTrial,
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
from src.research.backends.vectorbt import (
    VECTORBT_PIN,
    VectorBTCostMapping,
    VectorBTDependencyError,
    VectorBTInputError,
    VectorBTResourceLimitError,
    VectorBTResourcePolicy,
    VectorBTSearchExecutor,
    VectorBTSignalSet,
    VectorBTTimingPolicy,
    VectorBTUnsupportedSemanticsError,
    prepare_vectorbt_signals,
    vectorbt_version,
)
from src.src_data.research_roles import EvidenceRole


CONFIG_HASH = "d" * 64
DATA_HASH = "e" * 64
NOW = "2026-08-14T10:00:00+00:00"
LATER = "2026-08-14T10:01:00+00:00"
COST_PARITY_ABS_TOLERANCE = 1e-5


def _market_data(rows: int = 14) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=rows, freq="30min", tz="UTC")
    open_prices = np.array(
        [100, 101, 102, 104, 103, 105, 106, 104, 107, 108, 106, 109, 110, 111],
        dtype=float,
    )[:rows]
    return pd.DataFrame(
        {
            "open": open_prices,
            "close": open_prices * (1.0 + 0.0005),
        },
        index=index,
    )


def _search_space() -> SearchSpace:
    return SearchSpace(
        (
            ParameterSpec(
                name="lookback",
                kind=ParameterKind.INTEGER,
                path="features.0.params.window",
                low=1,
                high=3,
            ),
            ParameterSpec(
                name="threshold",
                kind=ParameterKind.CATEGORICAL,
                path="signals.0.params.threshold",
                values=(0.1, 0.2, 0.3, 0.4),
            ),
        )
    )


def _specification(
    *,
    assets: tuple[str, ...] = ("ETHUSD",),
    search_space: SearchSpace | None = None,
    trial_budget: int = 12,
    cost_assumptions: dict[str, float] | None = None,
    model_families: tuple[str, ...] = (),
) -> DiscoverySpecification:
    return DiscoverySpecification(
        hypothesis_id="hypothesis-vectorbt-phase3a",
        assets=assets,
        timeframe="30m",
        feature_families=("roc",),
        target_family="forward_return",
        model_families=model_families,
        signal_families=(),
        search_method="vectorbt",
        trial_budget=trial_budget,
        search_space=search_space or _search_space(),
        selection=SelectionPolicy(
            primary=MetricPreference(
                "total_return",
                SelectionDirection.MAXIMIZE,
            ),
            metric_basis=SelectionMetricBasis.TRADING,
            top_k=1,
            tie_breakers=(
                MetricPreference("turnover", SelectionDirection.MINIMIZE),
            ),
        ),
        eligibility=EligibilityPolicy(
            minimum_data=MinimumDataRequirements(
                minimum_observations=1,
                minimum_oos_rows=0,
                minimum_trades=1,
                minimum_coverage=0.0,
                maximum_missing_rate=0.50,
            ),
            metric_rules=(
                EligibilityRule(
                    metric="total_return",
                    operator=RuleOperator.GT,
                    threshold=-1.0,
                    rejection_reason="portfolio_loss_exceeds_bound",
                ),
            ),
            required_checks=(
                "causal_features",
                "target_signal_compatible",
                "data_quality",
                "timing_mapping_supported",
                "cost_mapping_supported",
                "long_only_supported",
                "screening_only",
            ),
        ),
        config_reference="config/experiments/synthetic_vectorbt_phase3a.yaml#frozen",
        config_hash=CONFIG_HASH,
        dataset_reference="snapshot:synthetic-vectorbt-phase3a-v1",
        dataset_fingerprint={"sha256": DATA_HASH, "rows": 14},
        evidence_reference=EvidenceReference(
            stage=EvidenceStage.DEVELOPMENT,
            evidence_role=EvidenceRole.DISCOVERY,
            artifact_reference="snapshots/synthetic-vectorbt-phase3a-v1/manifest.json",
            sample_reference="snapshot:synthetic-vectorbt-phase3a-v1",
        ),
        cost_assumptions=(
            cost_assumptions
            if cost_assumptions is not None
            else {
                "cost_per_turnover": 0.0005,
                "slippage_per_turnover": 0.0002,
            }
        ),
        validation_method="canonical_experiment",
        random_seed=17,
    )


def _signals(
    data: pd.DataFrame,
    parameters: dict[str, object],
) -> VectorBTSignalSet:
    entries = pd.Series(False, index=data.index, dtype=bool)
    exits = pd.Series(False, index=data.index, dtype=bool)
    entry_offset = int(parameters["lookback"])
    entries.iloc[entry_offset] = True
    exits.iloc[entry_offset + 4] = True
    return VectorBTSignalSet(
        entries=entries,
        exits=exits,
        target_fraction=1.0,
        checks={
            "causal_features": True,
            "target_signal_compatible": True,
        },
        metadata={"fixture": "synthetic_long_only"},
    )


def _single_parameter_space() -> SearchSpace:
    return SearchSpace(
        (
            ParameterSpec(
                name="lookback",
                kind=ParameterKind.FIXED,
                path="features.0.params.window",
                values=(1,),
            ),
            ParameterSpec(
                name="threshold",
                kind=ParameterKind.FIXED,
                path="signals.0.params.threshold",
                values=(0.2,),
            ),
        )
    )


def _executor(
    *,
    resources: VectorBTResourcePolicy | None = None,
    artifact_root: Path | None = None,
    signal_builder=_signals,
) -> VectorBTSearchExecutor:
    return VectorBTSearchExecutor(
        _market_data(),
        signal_builder,
        periods_per_year=365 * 48,
        resources=resources,
        artifact_root=artifact_root,
    )


def test_core_research_import_is_dependency_safe_and_backend_version_is_pinned() -> None:
    assert "vectorbt" not in sys.modules
    import src.research as research

    assert research.DiscoveryTrial.__name__ == DiscoveryTrial.__name__
    assert "vectorbt" not in sys.modules
    assert vectorbt_version() == VECTORBT_PIN == "0.28.5"
    assert "vectorbt" not in sys.modules


def test_unavailable_optional_dependency_has_an_actionable_error(monkeypatch) -> None:
    from src.research.backends.vectorbt import optional_dependency

    def missing_distribution(name: str):
        error = ModuleNotFoundError(f"No module named {name!r}")
        error.name = name
        raise error

    monkeypatch.setattr(optional_dependency, "import_module", missing_distribution)
    with pytest.raises(
        VectorBTDependencyError,
        match=r"VectorBT backend requires optional dependency.*0\.28\.5",
    ):
        optional_dependency.load_vectorbt()

    def forbidden_signal_builder(data, parameters):
        raise AssertionError("signal builder must not run without VectorBT")

    executor = VectorBTSearchExecutor(
        _market_data(),
        forbidden_signal_builder,
        periods_per_year=365 * 48,
        dependency_loader=optional_dependency.load_vectorbt,
    )
    with pytest.raises(VectorBTDependencyError, match="optional dependency"):
        executor.execute(
            _specification(),
            research_run_id="run-vectorbt-missing-dependency",
        )


def test_optional_dependency_rejects_version_drift_before_import(monkeypatch) -> None:
    from src.research.backends.vectorbt import optional_dependency

    monkeypatch.setattr(optional_dependency, "version", lambda name: "0.28.4")
    with pytest.raises(VectorBTDependencyError, match="reproducibility pin"):
        optional_dependency.load_vectorbt()


def test_finite_search_preserves_all_12_combinations_and_portable_trials() -> None:
    trials = _executor(
        resources=VectorBTResourcePolicy(max_combinations=12, batch_size=5)
    ).execute(_specification(), research_run_id="run-vectorbt-breadth")

    assert len(trials) == 12
    assert all(trial.status is TrialStatus.COMPLETED for trial in trials)
    assert [dict(trial.parameters) for trial in trials] == list(
        _search_space().iter_grid()
    )
    assert len({trial.trial_id for trial in trials}) == 12
    assert all(isinstance(trial, DiscoveryTrial) for trial in trials)
    assert all(trial.metrics["trade_count"] == 1 for trial in trials)
    assert all(
        trial.runtime_metadata["screening_metrics_are_canonical_evidence"] is False
        for trial in trials
    )
    json.dumps([trial.to_dict() for trial in trials], allow_nan=False)
    assert "Portfolio" not in json.dumps([trial.to_dict() for trial in trials])


def test_batching_does_not_change_parameter_order_trial_ids_or_metrics() -> None:
    specification = _specification()
    first = _executor(
        resources=VectorBTResourcePolicy(max_combinations=12, batch_size=3)
    ).execute(specification, research_run_id="run-vectorbt-deterministic")
    second = _executor(
        resources=VectorBTResourcePolicy(max_combinations=12, batch_size=12)
    ).execute(specification, research_run_id="run-vectorbt-deterministic")

    assert [trial.trial_id for trial in first] == [trial.trial_id for trial in second]
    assert [dict(trial.parameters) for trial in first] == [
        dict(trial.parameters) for trial in second
    ]
    assert [dict(trial.metrics) for trial in first] == [
        dict(trial.metrics) for trial in second
    ]


def test_resource_guard_fails_before_dependency_load_or_signal_allocation() -> None:
    calls = {"signals": 0, "dependency": 0}

    def signal_builder(data, parameters):
        calls["signals"] += 1
        return _signals(data, parameters)

    def dependency_loader():
        calls["dependency"] += 1
        raise AssertionError("dependency must not load after failed preflight")

    executor = VectorBTSearchExecutor(
        _market_data(),
        signal_builder,
        periods_per_year=365 * 48,
        resources=VectorBTResourcePolicy(max_combinations=4, batch_size=4),
        dependency_loader=dependency_loader,
    )
    with pytest.raises(VectorBTResourceLimitError, match="resource_limit"):
        executor.execute(_specification(), research_run_id="run-vectorbt-too-large")
    assert calls == {"signals": 0, "dependency": 0}


def test_peak_batch_memory_guard_fails_before_dependency_or_signal_work() -> None:
    calls = {"signals": 0, "dependency": 0}

    def signal_builder(data, parameters):
        calls["signals"] += 1
        return _signals(data, parameters)

    def dependency_loader():
        calls["dependency"] += 1
        raise AssertionError("dependency must not load after failed memory preflight")

    executor = VectorBTSearchExecutor(
        _market_data(),
        signal_builder,
        periods_per_year=365 * 48,
        resources=VectorBTResourcePolicy(
            max_combinations=12,
            batch_size=6,
            max_estimated_bytes=14 * 6 * 96 - 1,
        ),
        dependency_loader=dependency_loader,
    )
    with pytest.raises(VectorBTResourceLimitError, match="working set"):
        executor.execute(_specification(), research_run_id="run-vectorbt-memory-limit")
    assert calls == {"signals": 0, "dependency": 0}


def test_next_bar_mapping_rejects_same_close_and_preserves_native_fill_times() -> None:
    with pytest.raises(
        VectorBTUnsupportedSemanticsError,
        match="same-close fills are forbidden",
    ):
        VectorBTTimingPolicy(entry_delay_bars=0)

    trials = _executor().execute(
        _specification(search_space=_single_parameter_space(), trial_budget=1),
        research_run_id="run-vectorbt-timing",
    )
    trial = trials[0]
    index = _market_data().index
    assert trial.status is TrialStatus.COMPLETED
    assert trial.runtime_metadata["entry_timestamps"] == [index[2].isoformat()]
    assert trial.runtime_metadata["exit_timestamps"] == [index[6].isoformat()]
    assert trial.runtime_metadata["position_direction"] == "long_only"
    assert trial.metrics["trade_count"] == 1
    assert trial.runtime_metadata["timing_mapping"]["same_close_execution"] is False


def test_warmup_nan_policy_never_forward_fills_and_rejects_internal_gaps() -> None:
    data = _market_data()
    entries = pd.Series(False, index=data.index, dtype=object)
    exits = pd.Series(False, index=data.index, dtype=object)
    entries.iloc[:2] = np.nan
    exits.iloc[:1] = np.nan
    entries.iloc[2] = True
    exits.iloc[7] = True
    prepared = prepare_vectorbt_signals(
        VectorBTSignalSet(entries=entries, exits=exits),
        market_index=data.index,
        timing=VectorBTTimingPolicy(),
    )
    assert prepared.warmup_rows == 2
    assert not prepared.entries.iloc[:3].any()
    assert bool(prepared.entries.iloc[3]) is True
    assert prepared.entry_timestamps == (data.index[3].isoformat(),)

    entries.iloc[4] = np.nan
    with pytest.raises(VectorBTInputError, match="leading warmup prefix"):
        prepare_vectorbt_signals(
            VectorBTSignalSet(entries=entries, exits=exits),
            market_index=data.index,
            timing=VectorBTTimingPolicy(),
        )


def test_zero_trade_run_is_completed_with_finite_zero_metrics() -> None:
    def no_trade_signals(data, parameters):
        return VectorBTSignalSet(
            entries=pd.Series(False, index=data.index),
            exits=pd.Series(False, index=data.index),
            checks={
                "causal_features": True,
                "target_signal_compatible": True,
            },
        )

    trial = _executor(signal_builder=no_trade_signals).execute(
        _specification(search_space=_single_parameter_space(), trial_budget=1),
        research_run_id="run-vectorbt-zero-trade",
    )[0]
    assert trial.status is TrialStatus.COMPLETED
    assert trial.metrics["trade_count"] == 0
    assert trial.metrics["total_return"] == 0.0
    assert trial.metrics["sharpe"] == 0.0
    assert all(np.isfinite(float(value)) for value in trial.metrics.values())


def test_cost_mapping_is_explicit_and_ambiguous_semantics_fail_closed() -> None:
    mapping = VectorBTCostMapping.from_stf_assumptions(
        {
            "commission_bps_per_side": 2.0,
            "slippage_bps_per_side": 1.0,
            "fixed_fee_per_order": 0.0,
        }
    )
    assert mapping.fees == pytest.approx(0.0002)
    assert mapping.slippage == pytest.approx(0.0001)
    assert mapping.component_status["commission"].startswith("exact_")

    with pytest.raises(VectorBTUnsupportedSemanticsError, match="ambiguous"):
        VectorBTCostMapping.from_stf_assumptions({"spread_bps": 2.0})
    with pytest.raises(VectorBTUnsupportedSemanticsError, match="approximate"):
        VectorBTCostMapping.from_stf_assumptions({"spread_bps_per_side": 1.0})
    with pytest.raises(VectorBTUnsupportedSemanticsError, match="holding_cost"):
        VectorBTCostMapping.from_stf_assumptions(
            {"holding_cost_per_exposed_bar": 0.0001}
        )
    with pytest.raises(VectorBTUnsupportedSemanticsError, match="fully invested"):
        VectorBTSignalSet(
            entries=pd.Series([False, True]),
            exits=pd.Series([False, False]),
            target_fraction=0.5,
        )


def test_stf_and_vectorbt_have_next_open_gross_and_cost_accounting_parity() -> None:
    data = _market_data()
    specification = _specification(
        search_space=_single_parameter_space(),
        trial_budget=1,
        cost_assumptions={
            "cost_per_turnover": 0.0005,
            "slippage_per_turnover": 0.0002,
        },
    )
    signal_set = _signals(data, {"lookback": 1, "threshold": 0.2})
    prepared = prepare_vectorbt_signals(
        signal_set,
        market_index=data.index,
        timing=VectorBTTimingPolicy(),
    )
    canonical_frame = pd.DataFrame(
        {
            "position": prepared.target_positions,
            "open_to_open_return": data["open"].pct_change(),
        },
        index=data.index,
    )
    canonical = run_backtest(
        canonical_frame,
        signal_col="position",
        returns_col="open_to_open_return",
        missing_return_policy="fill_zero",
        cost_per_unit_turnover=0.0005,
        slippage_per_unit_turnover=0.0002,
        max_leverage=1.0,
        dd_guard=False,
        periods_per_year=365 * 48,
        liquidate_at_end=False,
        allow_short=False,
    )
    trial = _executor().execute(
        specification,
        research_run_id="run-vectorbt-cost-parity",
    )[0]

    canonical_gross_total = float((1.0 + canonical.gross_returns).prod() - 1.0)
    canonical_net_total = float((1.0 + canonical.returns).prod() - 1.0)
    assert trial.metrics["gross_total_return"] == pytest.approx(
        canonical_gross_total,
        abs=1e-12,
    )
    assert trial.metrics["total_return"] == pytest.approx(
        canonical_net_total,
        abs=COST_PARITY_ABS_TOLERANCE,
    )
    assert trial.metrics["total_cost"] == pytest.approx(
        canonical_gross_total - canonical_net_total,
        abs=COST_PARITY_ABS_TOLERANCE,
    )
    assert trial.runtime_metadata["entry_timestamps"] == [
        data.index[2].isoformat()
    ]
    assert trial.runtime_metadata["exit_timestamps"] == [
        data.index[6].isoformat()
    ]


def test_candidate_stops_pending_canonical_validation_and_writes_portable_artifacts(
    tmp_path: Path,
) -> None:
    specification = _specification()
    hypothesis = ResearchHypothesis(
        hypothesis_id=specification.hypothesis_id,
        name="Synthetic VectorBT screening",
        thesis="A causal long-only fixture is suitable for adapter contract testing.",
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
        research_run_id="run-vectorbt-lifecycle",
        request_id="request-vectorbt-lifecycle",
        started_at=NOW,
        completed_at=LATER,
    )

    assert result.research_run.backend == "vectorbt"
    assert result.research_run.backend_version == VECTORBT_PIN
    assert len(result.trials) == 12
    assert result.ranking.completed_trial_count == 12
    assert result.ranking.eligible_candidate_count == 12
    assert len(result.candidates) == len(result.validation_requests) == 1
    candidate = result.candidates[0]
    assert candidate.status is CandidateStatus.PENDING_CANONICAL_VALIDATION
    assert candidate.status is not CandidateStatus.VALIDATED
    assert (
        candidate.search_metadata["trial_runtime_metadata"][
            "screening_metrics_are_canonical_evidence"
        ]
        is False
    )
    assert result.research_run.provenance["trial_state_counts"] == {
        "completed": 12
    }
    assert result.research_run.provenance["selected_candidate_count"] == 1
    for name in (
        "vectorbt_backend.json",
        "vectorbt_timing_mapping.json",
        "vectorbt_cost_mapping.json",
        "vectorbt_search_summary.json",
    ):
        payload = json.loads((tmp_path / name).read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        assert "Portfolio" not in json.dumps(payload)


def test_unsupported_search_and_asset_semantics_fail_without_silent_fallback() -> None:
    continuous_space = SearchSpace(
        (
            ParameterSpec(
                name="threshold",
                kind=ParameterKind.FLOAT,
                low=0.1,
                high=0.9,
            ),
        )
    )
    with pytest.raises(VectorBTUnsupportedSemanticsError, match="finite enumerable"):
        _executor().execute(
            _specification(search_space=continuous_space),
            research_run_id="run-vectorbt-continuous",
        )
    with pytest.raises(VectorBTUnsupportedSemanticsError, match="one asset"):
        _executor().execute(
            _specification(assets=("ETHUSD", "BTCUSD")),
            research_run_id="run-vectorbt-multiasset",
        )
    with pytest.raises(ResearchContractError, match="Unknown discovery executor"):
        get_discovery_executor("vectorbt_or_grid")


def test_executor_factory_selects_vectorbt_explicitly() -> None:
    executor = get_discovery_executor(
        "vectorbt",
        market_data=_market_data(),
        signal_builder=_signals,
        periods_per_year=365 * 48,
    )
    assert executor.__class__.__name__ == "VectorBTSearchExecutor"
    assert executor.name == "vectorbt"
