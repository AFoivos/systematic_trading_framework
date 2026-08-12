from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.experiments.alpha_registry import (
    HypothesisRegistry,
    HypothesisRegistryError,
    HypothesisStatus,
)
from src.src_data.research_roles import EvidenceRole


def _create(registry: HypothesisRegistry):
    return registry.create(
        research_id="AR-TEST",
        hypothesis_id="H-0001",
        version=1,
        spec_hash="a" * 64,
        snapshot_ids=["discovery-v1"],
        data_roles=[EvidenceRole.DISCOVERY],
        notes="hand-authored hypothesis",
        created_at="2026-01-01T00:00:00+00:00",
    )


def test_explicit_lifecycle_is_append_only_and_auditable(tmp_path: Path) -> None:
    registry = HypothesisRegistry(tmp_path / "registry.jsonl")
    _create(registry)
    screened = registry.transition(
        research_id="AR-TEST",
        hypothesis_id="H-0001",
        version=1,
        new_status=HypothesisStatus.SCREENED,
        reason="screen contract passed",
        changed_at="2026-01-02T00:00:00+00:00",
    )
    validated = registry.transition(
        research_id="AR-TEST",
        hypothesis_id="H-0001",
        version=1,
        new_status=HypothesisStatus.VALIDATED,
        reason="frozen validation passed",
        changed_at="2026-01-03T00:00:00+00:00",
    )

    assert screened.status is HypothesisStatus.SCREENED
    assert validated.status is HypothesisStatus.VALIDATED
    assert len(validated.status_history) == 3
    assert (
        len((tmp_path / "registry.jsonl").read_text(encoding="utf-8").splitlines()) == 3
    )
    assert (
        registry.get(research_id="AR-TEST", hypothesis_id="H-0001", version=1)
        == validated
    )


def test_invalid_transition_is_rejected(tmp_path: Path) -> None:
    registry = HypothesisRegistry(tmp_path / "registry.jsonl")
    _create(registry)

    with pytest.raises(HypothesisRegistryError, match="Invalid hypothesis transition"):
        registry.transition(
            research_id="AR-TEST",
            hypothesis_id="H-0001",
            version=1,
            new_status=HypothesisStatus.PROSPECTIVE_READY,
            reason="attempted skip",
        )

    with pytest.raises(
        HypothesisRegistryError, match="timestamps must be chronological"
    ):
        registry.transition(
            research_id="AR-TEST",
            hypothesis_id="H-0001",
            version=1,
            new_status=HypothesisStatus.SCREENED,
            reason="backdated transition",
            changed_at="2025-12-31T23:59:59+00:00",
        )


def test_rejected_hypothesis_is_preserved_and_terminal(tmp_path: Path) -> None:
    registry = HypothesisRegistry(tmp_path / "registry.jsonl")
    _create(registry)
    rejected = registry.transition(
        research_id="AR-TEST",
        hypothesis_id="H-0001",
        version=1,
        new_status=HypothesisStatus.REJECTED,
        reason="failed preregistered screen",
        changed_at="2026-01-02T00:00:00+00:00",
    )

    assert rejected.rejection_reason == "failed preregistered screen"
    assert registry.list_records() == (rejected,)
    with pytest.raises(HypothesisRegistryError, match="Invalid hypothesis transition"):
        registry.transition(
            research_id="AR-TEST",
            hypothesis_id="H-0001",
            version=1,
            new_status=HypothesisStatus.SCREENED,
            reason="attempt resurrection",
        )


def test_registry_rejects_non_integer_version_and_tampered_immutable_fields(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.jsonl"
    registry = HypothesisRegistry(registry_path)
    with pytest.raises(HypothesisRegistryError, match="integer"):
        registry.create(
            research_id="AR-TEST",
            hypothesis_id="H-0001",
            version=1.5,
            spec_hash="a" * 64,
            snapshot_ids=["discovery-v1"],
            data_roles=[EvidenceRole.DISCOVERY],
        )

    _create(registry)
    registry.transition(
        research_id="AR-TEST",
        hypothesis_id="H-0001",
        version=1,
        new_status=HypothesisStatus.SCREENED,
        reason="screen contract passed",
        changed_at="2026-01-02T00:00:00+00:00",
    )
    events = [json.loads(line) for line in registry_path.read_text().splitlines()]
    events[1]["record"]["spec_hash"] = "b" * 64
    registry_path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(HypothesisRegistryError, match="Immutable hypothesis fields"):
        registry.get(research_id="AR-TEST", hypothesis_id="H-0001", version=1)
