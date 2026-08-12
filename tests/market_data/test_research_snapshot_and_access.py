from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.src_data.quality import DataQualityContract
from src.src_data.research_access import (
    DiscoveryDataAccess,
    ProcessedArtifactOverride,
    ProspectiveAccessAuthorization,
    ProspectiveFinalDataAccess,
    ResearchAccessDenied,
    SnapshotReference,
    ValidationDataAccess,
)
from src.src_data.research_roles import EvidenceRole, SourceClassification
from src.src_data.research_snapshot import (
    ResearchSnapshotError,
    create_research_snapshot,
    load_research_snapshot_manifest,
    verify_research_snapshot,
)
from src.utils.run_metadata import file_sha256


def _frame(*, processed: bool = False) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=4, freq="30min", tz="UTC"),
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [101.0, 102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0, 102.0],
            "close": [100.5, 101.5, 102.5, 103.5],
            "volume": [10.0, 11.0, 12.0, 13.0],
        }
    )
    if processed:
        frame["pred_prob"] = [0.1, 0.2, 0.3, 0.4]
    return frame


def _contract(*, processed: bool = False) -> DataQualityContract:
    units = {
        "timestamp": "datetime_utc",
        "open": "price",
        "high": "price",
        "low": "price",
        "close": "price",
        "volume": "base_units",
    }
    if processed:
        units["pred_prob"] = "probability"
    return DataQualityContract(
        asset="TEST",
        timeframe="30m",
        timezone="UTC",
        cadence="30min",
        column_units=units,
        volume_semantics="provider_base_asset_volume",
    )


def _create(
    tmp_path: Path,
    *,
    snapshot_id: str,
    role: EvidenceRole,
    classification: SourceClassification = SourceClassification.VALIDATED_MARKET_DATA,
    processed: bool = False,
) -> tuple[Path, str]:
    source = tmp_path / f"{snapshot_id}-source.csv"
    frame = _frame(processed=processed)
    if role is EvidenceRole.PROSPECTIVE_FINAL:
        for column in ("open", "high", "low", "close"):
            frame[column] = frame[column] + 10.0
    frame.to_csv(source, index=False)
    digest = file_sha256(source)
    manifest = create_research_snapshot(
        source,
        snapshot_root=tmp_path / "snapshots",
        snapshot_id=snapshot_id,
        quality_contract=_contract(processed=processed),
        evidence_role=role,
        source_classification=classification,
        quote_semantics={"kind": "NO_BID_ASK"},
        config_version={"contract": 1},
        code_version={"commit": "test", "is_dirty": False},
        created_at="2026-01-02T00:00:00+00:00",
    )
    return manifest, digest


def _reference(manifest: Path, digest: str, role: EvidenceRole) -> SnapshotReference:
    payload = load_research_snapshot_manifest(manifest)
    return SnapshotReference(
        snapshot_id=payload.snapshot_id,
        manifest_path=manifest,
        expected_sha256=digest,
        evidence_role=role,
    )


def test_snapshot_is_write_once_and_discovery_reload_enforces_sha(
    tmp_path: Path,
) -> None:
    manifest, digest = _create(
        tmp_path,
        snapshot_id="test-discovery-v1",
        role=EvidenceRole.DISCOVERY,
    )
    verified = verify_research_snapshot(manifest, expected_sha256=digest)
    loaded = DiscoveryDataAccess().load_discovery(
        _reference(manifest, digest, EvidenceRole.DISCOVERY)
    )

    assert verified.sha256 == digest
    assert verified.run_identity_sha256
    assert len(loaded.frame) == 4
    with pytest.raises(ResearchSnapshotError, match="will not be overwritten"):
        create_research_snapshot(
            tmp_path / "test-discovery-v1-source.csv",
            snapshot_root=tmp_path / "snapshots",
            snapshot_id="test-discovery-v1",
            quality_contract=_contract(),
            evidence_role=EvidenceRole.DISCOVERY,
            source_classification=SourceClassification.VALIDATED_MARKET_DATA,
            quote_semantics={"kind": "NO_BID_ASK"},
            code_version={"commit": "test"},
        )


def test_snapshot_created_at_requires_an_explicit_timezone(tmp_path: Path) -> None:
    source = tmp_path / "naive-created-at.csv"
    _frame().to_csv(source, index=False)

    with pytest.raises(
        ResearchSnapshotError, match="created_at must include a timezone"
    ):
        create_research_snapshot(
            source,
            snapshot_root=tmp_path / "snapshots",
            snapshot_id="naive-created-at-v1",
            quality_contract=_contract(),
            evidence_role=EvidenceRole.DISCOVERY,
            source_classification=SourceClassification.VALIDATED_MARKET_DATA,
            quote_semantics={"kind": "NO_BID_ASK"},
            code_version={"commit": "test"},
            created_at="2026-01-02T00:00:00",
        )


def test_actual_byte_sha_mismatch_is_blocking(tmp_path: Path) -> None:
    manifest, digest = _create(
        tmp_path,
        snapshot_id="test-tamper-v1",
        role=EvidenceRole.DISCOVERY,
    )
    data_path = manifest.parent / "data.csv"
    data_path.write_bytes(data_path.read_bytes() + b"\n")

    with pytest.raises(ResearchSnapshotError, match="bytes changed"):
        verify_research_snapshot(manifest, expected_sha256=digest)
    with pytest.raises(ResearchSnapshotError, match="Configured SHA-256"):
        verify_research_snapshot(manifest, expected_sha256="0" * 64)


def test_manifest_schema_change_is_detected_even_when_data_sha_matches(
    tmp_path: Path,
) -> None:
    manifest, digest = _create(
        tmp_path,
        snapshot_id="test-schema-v1",
        role=EvidenceRole.DISCOVERY,
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["schema"]["column_names"].append("silently_added")
    payload["schema"]["column_dtypes"]["silently_added"] = "float64"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ResearchSnapshotError, match="schema/dtypes"):
        verify_research_snapshot(manifest, expected_sha256=digest)


def test_manifest_cannot_coerce_serialized_quality_policy(tmp_path: Path) -> None:
    manifest, digest = _create(
        tmp_path,
        snapshot_id="test-policy-v1",
        role=EvidenceRole.DISCOVERY,
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["quality_contract"]["require_all_column_units"] = "false"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ResearchSnapshotError, match="must be boolean"):
        verify_research_snapshot(manifest, expected_sha256=digest)


def test_manifest_cannot_relax_valid_quality_policy_without_identity_change(
    tmp_path: Path,
) -> None:
    manifest, digest = _create(
        tmp_path,
        snapshot_id="test-policy-identity-v1",
        role=EvidenceRole.DISCOVERY,
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["quality_contract"]["maximum_gap_multiple"] = 999.0
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ResearchSnapshotError, match="run identity"):
        verify_research_snapshot(manifest, expected_sha256=digest)


def test_role_firewall_denies_validation_and_prospective_to_discovery(
    tmp_path: Path,
) -> None:
    validation_manifest, validation_sha = _create(
        tmp_path,
        snapshot_id="test-validation-v1",
        role=EvidenceRole.VALIDATION,
    )
    validation_ref = _reference(
        validation_manifest,
        validation_sha,
        EvidenceRole.VALIDATION,
    )
    with pytest.raises(ResearchAccessDenied, match="only accepts DISCOVERY"):
        DiscoveryDataAccess().load_discovery(validation_ref)
    assert len(ValidationDataAccess().load_validation(validation_ref).frame) == 4

    prospective_manifest, prospective_sha = _create(
        tmp_path,
        snapshot_id="test-prospective-v1",
        role=EvidenceRole.PROSPECTIVE_FINAL,
    )
    prospective_ref = _reference(
        prospective_manifest,
        prospective_sha,
        EvidenceRole.PROSPECTIVE_FINAL,
    )
    with pytest.raises(ResearchAccessDenied, match="only accepts DISCOVERY"):
        DiscoveryDataAccess().load_discovery(prospective_ref)
    with pytest.raises(ResearchAccessDenied, match="not explicitly authorized"):
        ProspectiveFinalDataAccess(
            ProspectiveAccessAuthorization(
                explicitly_authorized=False,
                approved_by="reviewer",
                approved_at="2026-01-02T00:00:00Z",
                frozen_spec_sha256="a" * 64,
                purpose="synthetic contract test",
            )
        )
    authorized = ProspectiveFinalDataAccess(
        ProspectiveAccessAuthorization(
            explicitly_authorized=True,
            approved_by="reviewer",
            approved_at="2026-01-02T00:00:00Z",
            frozen_spec_sha256="a" * 64,
            purpose="synthetic denial-before-load contract test",
        )
    )
    with pytest.raises(ResearchAccessDenied, match="must bind the exact authorized"):
        authorized.load_prospective_final(prospective_ref)


def test_historical_bytes_cannot_be_refrozen_as_prospective_final(
    tmp_path: Path,
) -> None:
    historical_manifest, _ = _create(
        tmp_path,
        snapshot_id="historical-v1",
        role=EvidenceRole.HISTORICAL_PSEUDO_OOS,
    )
    historical_source = tmp_path / "historical-v1-source.csv"

    with pytest.raises(ResearchSnapshotError, match="relabeling by duplicate snapshot"):
        create_research_snapshot(
            historical_source,
            snapshot_root=historical_manifest.parent.parent,
            snapshot_id="false-prospective-v1",
            quality_contract=_contract(),
            evidence_role=EvidenceRole.PROSPECTIVE_FINAL,
            source_classification=SourceClassification.VALIDATED_MARKET_DATA,
            quote_semantics={"kind": "NO_BID_ASK"},
            code_version={"commit": "test"},
        )


def test_processed_artifact_is_quarantined_and_cannot_masquerade_as_raw(
    tmp_path: Path,
) -> None:
    source = tmp_path / "processed-source.csv"
    _frame(processed=True).to_csv(source, index=False)
    with pytest.raises(ResearchSnapshotError, match="processed-artifact markers"):
        create_research_snapshot(
            source,
            snapshot_root=tmp_path / "invalid-snapshots",
            snapshot_id="processed-lie-v1",
            quality_contract=_contract(processed=True),
            evidence_role=EvidenceRole.DISCOVERY,
            source_classification=SourceClassification.VALIDATED_MARKET_DATA,
            quote_semantics={"kind": "NO_BID_ASK"},
            code_version={"commit": "test"},
        )

    manifest, digest = _create(
        tmp_path,
        snapshot_id="processed-explicit-v1",
        role=EvidenceRole.DISCOVERY,
        classification=SourceClassification.PROCESSED_EXPERIMENT_ARTIFACT,
        processed=True,
    )
    reference = _reference(manifest, digest, EvidenceRole.DISCOVERY)
    with pytest.raises(ResearchAccessDenied, match="quarantined"):
        DiscoveryDataAccess().load_discovery(reference)
    override = ProcessedArtifactOverride(
        enabled=True,
        warning_acknowledged=True,
        reason="synthetic diagnostic-only contract test",
    )
    with pytest.warns(RuntimeWarning, match="override is active"):
        loaded = DiscoveryDataAccess(
            processed_artifact_override=override
        ).load_discovery(reference)
    assert "pred_prob" in loaded.frame.columns


def test_access_authorization_flags_are_not_truthy_coerced() -> None:
    with pytest.raises(ResearchAccessDenied, match="flags must be booleans"):
        DiscoveryDataAccess(
            processed_artifact_override=ProcessedArtifactOverride(
                enabled="false",  # type: ignore[arg-type]
                warning_acknowledged="false",  # type: ignore[arg-type]
                reason="must not activate",
            )
        )

    with pytest.raises(ResearchAccessDenied, match="flag must be boolean"):
        ProspectiveFinalDataAccess(
            ProspectiveAccessAuthorization(
                explicitly_authorized="false",  # type: ignore[arg-type]
                approved_by="reviewer",
                approved_at="2026-01-02T00:00:00+00:00",
                frozen_spec_sha256="a" * 64,
                purpose="synthetic contract test",
            )
        )

    with pytest.raises(ResearchAccessDenied, match="lowercase SHA-256"):
        ProspectiveFinalDataAccess(
            ProspectiveAccessAuthorization(
                explicitly_authorized=True,
                approved_by="reviewer",
                approved_at="2026-01-02T00:00:00+00:00",
                frozen_spec_sha256="not-a-hash",
                purpose="synthetic contract test",
            )
        )
