from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.src_data.research_access import (
    DiscoveryDataAccess,
    ResearchAccessDenied,
    SnapshotReference,
)
from src.src_data.research_roles import EvidenceRole
from src.src_data.research_snapshot_partition import (
    HISTORICAL_CUTOFF_UTC,
    validate_historical_child_partition,
)

CONFIG = Path("config/research/alpha_discovery/AR-0001_ethusd_30m.yaml")


def _cfg() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def test_ar0001_child_snapshots_exactly_reconstruct_frozen_parent() -> None:
    """The two immutable children must be a lossless, non-overlapping role split."""

    cfg = _cfg()
    parent = cfg["historical_partition"]
    discovery = cfg["snapshot_reference"]
    pseudo = cfg["historical_pseudo_oos_reference"]

    result = validate_historical_child_partition(
        parent["parent_manifest_path"],
        parent_expected_sha256=parent["parent_expected_sha256"],
        discovery_manifest_path=discovery["manifest_path"],
        discovery_expected_sha256=discovery["expected_sha256"],
        historical_pseudo_oos_manifest_path=pseudo["manifest_path"],
        historical_pseudo_oos_expected_sha256=pseudo["expected_sha256"],
    )

    assert result.cutoff_utc == HISTORICAL_CUTOFF_UTC
    assert result.parent_snapshot_id == parent["parent_snapshot_id"]
    assert result.parent_sha256 == parent["parent_expected_sha256"]

    assert result.discovery_snapshot_id == discovery["snapshot_id"]
    assert result.discovery_sha256 == discovery["expected_sha256"]
    assert result.discovery_rows == discovery["expected_row_count"] == 95_018
    assert result.discovery_first_timestamp == discovery["expected_first_timestamp"]
    assert result.discovery_last_timestamp == discovery["expected_last_timestamp"]

    assert result.historical_pseudo_oos_snapshot_id == pseudo["snapshot_id"]
    assert result.historical_pseudo_oos_sha256 == pseudo["expected_sha256"]
    assert result.historical_pseudo_oos_rows == pseudo["expected_row_count"] == 16_465
    assert (
        result.historical_pseudo_oos_first_timestamp
        == pseudo["expected_first_timestamp"]
    )
    assert result.historical_pseudo_oos_last_timestamp == pseudo["expected_last_timestamp"]

    assert result.parent_rows == 111_483
    assert result.total_child_rows == 111_483
    assert result.discovery_rows + result.historical_pseudo_oos_rows == result.parent_rows
    assert result.exact_parent_row_reconstruction is True


def test_historical_pseudo_oos_child_is_denied_by_discovery_access() -> None:
    """Historical pseudo-OOS bytes must never be loadable through discovery access."""

    cfg = _cfg()
    pseudo = cfg["historical_pseudo_oos_reference"]

    correctly_typed_reference = SnapshotReference(
        snapshot_id=pseudo["snapshot_id"],
        manifest_path=Path(pseudo["manifest_path"]),
        expected_sha256=pseudo["expected_sha256"],
        evidence_role=EvidenceRole.HISTORICAL_PSEUDO_OOS,
    )
    with pytest.raises(ResearchAccessDenied, match="only accepts DISCOVERY"):
        DiscoveryDataAccess().load_discovery(correctly_typed_reference)

    # Even a caller that lies in the reference cannot relabel the immutable
    # child: the manifest role is re-read and compared after SHA verification.
    forged_discovery_reference = SnapshotReference(
        snapshot_id=pseudo["snapshot_id"],
        manifest_path=Path(pseudo["manifest_path"]),
        expected_sha256=pseudo["expected_sha256"],
        evidence_role=EvidenceRole.DISCOVERY,
    )
    with pytest.raises(ResearchAccessDenied, match="Immutable evidence-role mismatch"):
        DiscoveryDataAccess().load_discovery(forged_discovery_reference)
