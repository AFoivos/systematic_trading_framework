#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.src_data.quality import DataQualityContract
from src.src_data.research_access import (
    DiscoveryDataAccess,
    ResearchAccessDenied,
    SnapshotReference,
    ValidationDataAccess,
)
from src.src_data.research_roles import EvidenceRole, SourceClassification
from src.src_data.research_snapshot import (
    create_research_snapshot,
    load_research_snapshot_manifest,
)
from src.utils.run_metadata import file_sha256


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a data-contract-only immutable snapshot smoke test."
    )
    parser.add_argument("--source", required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--quality-contract", required=True)
    parser.add_argument("--snapshot-root", required=True)
    parser.add_argument("--snapshot-id", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = Path(args.source).resolve()
    expected_sha256 = str(args.expected_source_sha256)
    actual_source_sha256 = file_sha256(source)
    if actual_source_sha256 != expected_sha256:
        raise RuntimeError(
            f"Upstream source SHA mismatch: expected {expected_sha256}, "
            f"found {actual_source_sha256}."
        )
    contract_payload = json.loads(
        Path(args.quality_contract).read_text(encoding="utf-8")
    )
    quality_contract = DataQualityContract.from_dict(contract_payload)
    manifest_path = create_research_snapshot(
        source,
        snapshot_root=args.snapshot_root,
        snapshot_id=args.snapshot_id,
        quality_contract=quality_contract,
        evidence_role=EvidenceRole.DISCOVERY,
        source_classification=SourceClassification.VALIDATED_MARKET_DATA,
        quote_semantics={
            "kind": "NO_BID_ASK_IN_SOURCE",
            "execution_cost_eligible": False,
        },
        config_version={
            "quality_contract_path": str(Path(args.quality_contract)),
            "quality_contract_schema_version": 1,
        },
    )
    manifest = load_research_snapshot_manifest(manifest_path)
    reference = SnapshotReference(
        snapshot_id=manifest.snapshot_id,
        manifest_path=manifest_path,
        expected_sha256=expected_sha256,
        evidence_role=EvidenceRole.DISCOVERY,
    )
    loaded = DiscoveryDataAccess().load_discovery(reference)
    validation_denied = False
    try:
        ValidationDataAccess().load_validation(reference)
    except ResearchAccessDenied:
        validation_denied = True
    if not validation_denied:
        raise AssertionError(
            "Role firewall failed: discovery snapshot loaded as validation."
        )
    result = {
        "smoke_test": "DATA_CONTRACT_ONLY",
        "alpha_calculation_performed": False,
        "source_sha256_verified": actual_source_sha256,
        "snapshot_id": manifest.snapshot_id,
        "snapshot_manifest": str(manifest_path),
        "snapshot_sha256_verified": loaded.manifest.sha256,
        "run_identity_sha256": loaded.manifest.run_identity_sha256,
        "row_count": len(loaded.frame),
        "quality_status": loaded.manifest.quality["status"],
        "quality_maximum_severity": loaded.manifest.quality["maximum_severity"],
        "quality_issue_count": len(loaded.manifest.quality["issues"]),
        "quality_report_json": str(manifest_path.parent / "quality_report.json"),
        "quality_report_markdown": str(manifest_path.parent / "quality_report.md"),
        "discovery_access_verified": True,
        "validation_role_mismatch_denied": validation_denied,
        "prospective_access_used": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
