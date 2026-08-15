from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.research import (
    CandidateStatus,
    CanonicalValidationRecord,
    CheckStatus,
    DecisionKind,
    EvidenceRecord,
    EvidenceReference,
    EvidenceStage,
    MinimumEvidencePolicy,
    PromotionDecision,
    ResearchCandidate,
    ResearchContractError,
    ResearchHypothesis,
    ResearchResult,
    ResearchRun,
    ResearchRunStatus,
    RobustnessCheck,
    RobustnessRecord,
    SearchMetadata,
    SelectionDirection,
    SelectionRecord,
    apply_promotion_decision,
    candidate_from_research_result,
    deterministic_json_dumps,
    require_usable_final_holdout,
    transition_candidate,
)
from src.research.storage import CandidateStore, FilesystemResearchStore, ResearchStoreError
from src.src_data.research_roles import EvidenceRole


SPEC_HASH = "a" * 64
CONFIG_HASH = "b" * 64
DATA_HASH = "c" * 64
NOW = "2026-08-14T09:00:00+00:00"
LATER = "2026-08-14T09:10:00+00:00"


def _screened_candidate() -> ResearchCandidate:
    return ResearchCandidate(
        candidate_id="candidate-001",
        strategy_name="portable-screen",
        backend="dummy",
        config_reference="config/research.yaml#frozen",
        assets=("ETHUSD",),
        timeframe="30m",
        sample_reference="snapshot:discovery-v1",
        metrics={"rank_ic": 0.04, "turnover": 2.0},
        cost_assumptions={"spread_bps": 1.5},
        search_metadata={"trial": 2},
        status=CandidateStatus.SCREENED,
    )


def _development_reference() -> EvidenceReference:
    return EvidenceReference(
        stage=EvidenceStage.DEVELOPMENT,
        evidence_role=EvidenceRole.DISCOVERY,
        artifact_reference="artifacts/screen/result.json",
        sample_reference="snapshot:discovery-v1",
    )


def _run() -> ResearchRun:
    return ResearchRun(
        research_run_id="run-001",
        hypothesis_id="hypothesis-001",
        request_id="request-001",
        backend="dummy",
        backend_version="1.0",
        started_at=NOW,
        completed_at=LATER,
        status=ResearchRunStatus.COMPLETED,
        config_reference="config/research.yaml#frozen",
        config_hash=CONFIG_HASH,
        dataset_reference="snapshot:discovery-v1",
        dataset_fingerprint={"sha256": DATA_HASH, "rows": 1000},
        evidence_reference=_development_reference(),
        search_metadata=SearchMetadata(
            search_method="manual_grid",
            requested_trials=3,
            completed_trials=3,
            failed_trials=0,
            evaluated_alternatives=3,
            candidate_count=1,
            parameter_dimensions=("lookback", "threshold"),
            selection_metric="rank_ic",
            selection_direction=SelectionDirection.MAXIMIZE,
            random_seed=7,
        ),
        artifact_references=("artifacts/screen/result.json",),
        candidate_ids=("candidate-001",),
        git_revision="deadbeef",
        random_seed=7,
        runtime_mode="research",
        provenance={"source_identity_complete": True},
    )


def _selection() -> SelectionRecord:
    return SelectionRecord(
        selection_id="selection-001",
        research_run_id="run-001",
        candidate_id="candidate-001",
        evaluated_alternatives=3,
        selection_metric="rank_ic",
        selection_direction=SelectionDirection.MAXIMIZE,
        candidate_rank=1,
        tie_break_rule="lower_turnover",
        selected_at=LATER,
    )


def _validation() -> CanonicalValidationRecord:
    return CanonicalValidationRecord(
        validation_id="validation-001",
        candidate_id="candidate-001",
        experiment_config_reference="config/canonical.yaml#frozen",
        config_hash=CONFIG_HASH,
        specification_hash=SPEC_HASH,
        dataset_reference="snapshot:validation-v1",
        dataset_fingerprint={"sha256": DATA_HASH, "rows": 100},
        oos_rows=100,
        prediction_rows=95,
        oos_coverage=0.95,
        oos_marker="is_oos",
        cost_assumptions={"spread_bps": 1.5, "commission_bps": 0.5},
        timing_assumptions={"signal_time": "close", "entry_delay_bars": 1},
        metrics={"rank_ic": 0.03, "turnover": 1.8},
        status=CheckStatus.PASS,
        validated_at=LATER,
        test_references=("tests/test_no_lookahead.py",),
        artifact_references=("artifacts/canonical/summary.json",),
    )


def _robustness() -> RobustnessRecord:
    return RobustnessRecord(
        robustness_id="robustness-001",
        candidate_id="candidate-001",
        validation_id="validation-001",
        checks=(
            RobustnessCheck(
                name="cost_stress",
                status=CheckStatus.PASS,
                baseline_metric=0.03,
                stressed_metric=0.01,
                threshold=0.0,
                details={"cost_multiplier": 2.0},
            ),
            RobustnessCheck(
                name="subperiod_stability",
                status=CheckStatus.PASS,
                details={"passing_subperiods": 3},
            ),
        ),
        status=CheckStatus.PASS,
        recorded_at=LATER,
    )


def _final_evidence(*, used_for_tuning: bool = False) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id="evidence-final-001",
        candidate_id="candidate-001",
        evidence_reference=EvidenceReference(
            stage=EvidenceStage.FINAL_HOLDOUT,
            evidence_role=EvidenceRole.PROSPECTIVE_FINAL,
            artifact_reference="artifacts/final/summary.json",
            sample_reference="snapshot:prospective-final-v1",
        ),
        metrics={"rank_ic": 0.02},
        specification_hash=SPEC_HASH,
        recorded_at=LATER,
        artifact_references=("artifacts/final/summary.json",),
        cost_assumptions={"spread_bps": 1.5},
        timing_assumptions={"entry_delay_bars": 1},
        validation_checks={"data_quality": CheckStatus.PASS},
        used_for_tuning=used_for_tuning,
    )


def test_hypothesis_and_run_roundtrip_are_deterministic() -> None:
    hypothesis = ResearchHypothesis(
        hypothesis_id="hypothesis-001",
        name="Trend continuation after contraction",
        thesis="Conditional continuation should survive realistic execution costs.",
        assets=("ETHUSD",),
        timeframe="30m",
        created_at=NOW,
        tags=("trend", "volatility"),
        feature_families=("ema", "atr"),
        expected_mechanism="post-contraction information diffusion",
    )

    assert ResearchHypothesis.from_dict(hypothesis.to_dict()) == hypothesis
    assert ResearchRun.from_dict(_run().to_dict()) == _run()
    first = deterministic_json_dumps(_run())
    second = deterministic_json_dumps(ResearchRun.from_dict(json.loads(first)))
    assert first == second


def test_result_to_candidate_conversion_preserves_search_context_and_linkage() -> None:
    source = _screened_candidate()
    result = ResearchResult(
        request_id="request-001",
        backend="dummy",
        candidates=(source,),
    )

    candidate = candidate_from_research_result(
        result,
        research_run=_run(),
        selection=_selection(),
    )

    assert candidate.hypothesis_id == "hypothesis-001"
    assert candidate.research_run_id == "run-001"
    assert candidate.selection_id == "selection-001"
    assert candidate.search_metadata["evaluated_alternatives"] == 3
    assert candidate.search_metadata["candidate_rank"] == 1


def test_contracts_reject_duplicate_references_and_backend_objects() -> None:
    with pytest.raises(ResearchContractError, match="duplicates"):
        ResearchHypothesis(
            hypothesis_id="hypothesis-001",
            name="duplicate asset",
            thesis="invalid",
            assets=("ETHUSD", "ETHUSD"),
            created_at=NOW,
        )
    with pytest.raises(ResearchContractError, match="JSON-compatible"):
        EvidenceRecord(
            evidence_id="evidence-001",
            candidate_id="candidate-001",
            evidence_reference=_development_reference(),
            metrics={"rank_ic": 0.1},
            specification_hash=SPEC_HASH,
            recorded_at=NOW,
            timing_assumptions={"backend_object": object()},
        )
    with pytest.raises(ResearchContractError, match="finite"):
        RobustnessCheck(
            name="cost_stress",
            status=CheckStatus.FAIL,
            stressed_metric=float("inf"),
        )
    with pytest.raises(ResearchContractError, match="duplicate candidate_id"):
        ResearchResult(
            request_id="request-001",
            backend="dummy",
            candidates=(_screened_candidate(), _screened_candidate()),
        )
    malformed = _screened_candidate().to_dict()
    malformed["assets"] = "ETHUSD"
    with pytest.raises(ResearchContractError, match="JSON array"):
        ResearchCandidate.from_dict(malformed)


def test_final_holdout_cannot_be_tuning_data_or_survive_specification_change() -> None:
    with pytest.raises(ResearchContractError, match="used_for_tuning"):
        _final_evidence(used_for_tuning=True)

    evidence = _final_evidence()
    with pytest.raises(ResearchContractError, match="different specification hash"):
        require_usable_final_holdout(
            evidence,
            current_specification_hash="d" * 64,
        )
    with pytest.raises(ResearchContractError, match="material specification changes"):
        require_usable_final_holdout(
            evidence,
            current_specification_hash=SPEC_HASH,
            material_changes_after_evaluation=("FEATURE_WINDOWS",),
        )


def test_candidate_cannot_skip_validation_or_validate_without_required_evidence() -> None:
    candidate = _screened_candidate()
    with pytest.raises(ResearchContractError, match="Invalid candidate transition"):
        transition_candidate(
            candidate,
            CandidateStatus.VALIDATED,
            current_specification_hash=SPEC_HASH,
        )

    pending = transition_candidate(
        candidate,
        CandidateStatus.PENDING_CANONICAL_VALIDATION,
    )
    with pytest.raises(ResearchContractError, match="canonical OOS validation"):
        transition_candidate(
            pending,
            CandidateStatus.CANONICALLY_VALIDATED,
            current_specification_hash=SPEC_HASH,
        )


def test_full_evidence_gated_lifecycle_and_promotion_decisions() -> None:
    policy = MinimumEvidencePolicy(
        require_robustness=True,
        required_robustness_checks=("cost_stress", "subperiod_stability"),
        require_final_holdout=True,
    )
    validation = _validation()
    robustness = _robustness()
    final_evidence = _final_evidence()
    candidate = transition_candidate(
        _screened_candidate(), CandidateStatus.PENDING_CANONICAL_VALIDATION
    )
    candidate = transition_candidate(
        candidate,
        CandidateStatus.CANONICALLY_VALIDATED,
        validations=(validation,),
        current_specification_hash=SPEC_HASH,
    )
    candidate = transition_candidate(candidate, CandidateStatus.ROBUSTNESS_PENDING)
    candidate = transition_candidate(
        candidate,
        CandidateStatus.ROBUSTNESS_PASSED,
        policy=policy,
        validations=(validation,),
        robustness_records=(robustness,),
        current_specification_hash=SPEC_HASH,
    )
    candidate = transition_candidate(candidate, CandidateStatus.FINAL_HOLDOUT_PENDING)
    candidate = transition_candidate(
        candidate,
        CandidateStatus.FINAL_HOLDOUT_PASSED,
        policy=policy,
        evidence_records=(final_evidence,),
        current_specification_hash=SPEC_HASH,
    )
    decision = PromotionDecision(
        decision_id="decision-validate-001",
        candidate_id=candidate.candidate_id,
        from_status=CandidateStatus.FINAL_HOLDOUT_PASSED,
        to_status=CandidateStatus.VALIDATED,
        decision=DecisionKind.PROMOTE,
        reason="All configured evidence-completeness gates passed.",
        evidence_references=(
            validation.validation_id,
            robustness.robustness_id,
            final_evidence.evidence_id,
        ),
        decided_at=LATER,
    )
    validated = apply_promotion_decision(
        candidate,
        decision,
        policy=policy,
        validations=(validation,),
        robustness_records=(robustness,),
        evidence_records=(final_evidence,),
        current_specification_hash=SPEC_HASH,
    )
    assert validated.status is CandidateStatus.VALIDATED


def test_rejection_is_first_class_and_filesystem_store_is_immutable(tmp_path: Path) -> None:
    store: CandidateStore = FilesystemResearchStore(tmp_path / "research_records")
    candidate = _screened_candidate()
    store.save_candidate(candidate)
    candidate_path = tmp_path / "research_records" / "candidates" / "candidate-001.json"
    original_candidate_bytes = candidate_path.read_bytes()

    decision = PromotionDecision(
        decision_id="decision-reject-001",
        candidate_id=candidate.candidate_id,
        from_status=CandidateStatus.SCREENED,
        to_status=CandidateStatus.REJECTED,
        decision=DecisionKind.REJECT,
        reason="Cost stress eliminated the observed effect.",
        evidence_references=(),
        decided_at=LATER,
    )
    assert isinstance(store, FilesystemResearchStore)
    store.save_decision(decision)

    assert store.load_candidate(candidate.candidate_id).status is CandidateStatus.REJECTED
    assert store.list_decisions(candidate_id=candidate.candidate_id) == (decision,)
    assert candidate_path.read_bytes() == original_candidate_bytes
    with pytest.raises(ResearchStoreError, match="already exists"):
        store.save_candidate(candidate)


def test_filesystem_store_roundtrip_and_invalid_record_detection(tmp_path: Path) -> None:
    store = FilesystemResearchStore(tmp_path / "research_records")
    store.save_run(_run())
    store.save_selection(_selection())
    linked = candidate_from_research_result(
        ResearchResult(
            request_id="request-001",
            backend="dummy",
            candidates=(_screened_candidate(),),
        ),
        research_run=_run(),
        selection=_selection(),
    )
    store.save_candidate(linked)
    store.save_validation(_validation())
    store.save_robustness(_robustness())
    store.save_evidence(_final_evidence())

    assert store.load_run("run-001") == _run()
    assert store.load_selection("selection-001") == _selection()
    assert store.load_validation("validation-001") == _validation()
    assert store.load_robustness("robustness-001") == _robustness()
    assert store.load_evidence("evidence-final-001") == _final_evidence()

    run_path = tmp_path / "research_records" / "runs" / "run-001.json"
    rendered = run_path.read_text(encoding="utf-8")
    assert rendered == deterministic_json_dumps(json.loads(rendered), trailing_newline=True)
    run_path.write_text(rendered.replace('"schema_version":1', '"schema_version":2'))
    with pytest.raises(ResearchStoreError, match="schema version"):
        store.load_run("run-001")


def test_filesystem_store_cannot_persist_evidence_bypassing_promotion(tmp_path: Path) -> None:
    store = FilesystemResearchStore(tmp_path / "research_records")
    store.save_candidate(_screened_candidate())
    store.save_decision(
        PromotionDecision(
            decision_id="decision-pending-001",
            candidate_id="candidate-001",
            from_status=CandidateStatus.SCREENED,
            to_status=CandidateStatus.PENDING_CANONICAL_VALIDATION,
            decision=DecisionKind.PROMOTE,
            reason="Candidate selected for canonical replay.",
            evidence_references=(),
            decided_at=NOW,
        )
    )
    with pytest.raises(ResearchStoreError, match="evidence-gated lifecycle"):
        store.save_decision(
            PromotionDecision(
                decision_id="decision-canonical-001",
                candidate_id="candidate-001",
                from_status=CandidateStatus.PENDING_CANONICAL_VALIDATION,
                to_status=CandidateStatus.CANONICALLY_VALIDATED,
                decision=DecisionKind.PROMOTE,
                reason="Invalid attempt without canonical evidence.",
                evidence_references=(),
                decided_at=LATER,
            )
        )
