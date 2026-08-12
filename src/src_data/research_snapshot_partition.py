from __future__ import annotations

"""Immutable historical role partitioning for the AR-0001 parent snapshot."""

import csv
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from src.src_data.quality import DataQualityContract
from src.src_data.research_roles import EvidenceRole, SourceClassification
from src.src_data.research_snapshot import (
    ResearchSnapshotManifest,
    create_research_snapshot,
    load_research_snapshot_frame,
    verify_research_snapshot,
)


HISTORICAL_CUTOFF_UTC = "2025-07-01T00:00:00Z"
PARTITION_ASSIGNMENT_RULE = (
    "TIMESTAMP_LT_CUTOFF_DISCOVERY_ELSE_HISTORICAL_PSEUDO_OOS"
)


class HistoricalSnapshotPartitionError(RuntimeError):
    """Raised when parent-to-child role partitioning is not exact and auditable."""


@dataclass(frozen=True)
class HistoricalChildSnapshotSpec:
    snapshot_id: str
    evidence_role: EvidenceRole
    source_path: Path
    start_inclusive: str
    end_exclusive: str


@dataclass(frozen=True)
class HistoricalPartitionValidation:
    parent_snapshot_id: str
    parent_sha256: str
    cutoff_utc: str
    discovery_snapshot_id: str
    discovery_sha256: str
    discovery_rows: int
    discovery_first_timestamp: str
    discovery_last_timestamp: str
    historical_pseudo_oos_snapshot_id: str
    historical_pseudo_oos_sha256: str
    historical_pseudo_oos_rows: int
    historical_pseudo_oos_first_timestamp: str
    historical_pseudo_oos_last_timestamp: str
    total_child_rows: int
    parent_rows: int
    exact_parent_row_reconstruction: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            field: getattr(self, field)
            for field in self.__dataclass_fields__
        }


def _utc_timestamp(value: object, *, field: str) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise HistoricalSnapshotPartitionError(
            f"{field} must be a valid timestamp."
        ) from exc
    if timestamp.tzinfo is None:
        raise HistoricalSnapshotPartitionError(f"{field} must be timezone-aware.")
    return timestamp.tz_convert("UTC")


def _row_digest_update(digest: Any, fieldnames: list[str], row: Mapping[str, str]) -> None:
    serialized = json.dumps(
        [row.get(field, "") for field in fieldnames],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    digest.update(serialized.encode("utf-8"))
    digest.update(b"\n")


def write_historical_partition_sources(
    parent_manifest_path: str | Path,
    *,
    parent_expected_sha256: str,
    output_directory: str | Path,
    cutoff_utc: str = HISTORICAL_CUTOFF_UTC,
) -> tuple[HistoricalChildSnapshotSpec, HistoricalChildSnapshotSpec, dict[str, Any]]:
    """Split canonical CSV rows once without filtering incomplete bars or gaps."""

    parent_path = Path(parent_manifest_path).expanduser().resolve()
    parent = verify_research_snapshot(
        parent_path,
        expected_sha256=parent_expected_sha256,
    )
    parent_data_path = parent_path.parent / parent.data_file
    if parent_data_path.suffix.lower() != ".csv":
        raise HistoricalSnapshotPartitionError(
            "Historical child partitioning currently requires a canonical CSV parent."
        )
    cutoff = _utc_timestamp(cutoff_utc, field="cutoff_utc")
    if cutoff != _utc_timestamp(HISTORICAL_CUTOFF_UTC, field="frozen cutoff"):
        raise HistoricalSnapshotPartitionError(
            f"Historical cutoff must remain frozen at {HISTORICAL_CUTOFF_UTC}."
        )
    output = Path(output_directory).expanduser().resolve()
    if output.exists():
        raise HistoricalSnapshotPartitionError(
            f"Partition source directory is write-once and already exists: {output}"
        )
    output.mkdir(parents=True, exist_ok=False)
    discovery_path = output / "discovery.csv"
    pseudo_path = output / "historical_pseudo_oos.csv"

    parent_digest = sha256()
    discovery_digest = sha256()
    pseudo_digest = sha256()
    discovery_rows = 0
    pseudo_rows = 0
    previous: pd.Timestamp | None = None
    first_parent: pd.Timestamp | None = None
    last_parent: pd.Timestamp | None = None
    first_discovery: pd.Timestamp | None = None
    last_discovery: pd.Timestamp | None = None
    first_pseudo: pd.Timestamp | None = None
    last_pseudo: pd.Timestamp | None = None

    try:
        with (
            parent_data_path.open("r", encoding="utf-8", newline="") as source,
            discovery_path.open("x", encoding="utf-8", newline="") as discovery_file,
            pseudo_path.open("x", encoding="utf-8", newline="") as pseudo_file,
        ):
            reader = csv.DictReader(source)
            if not reader.fieldnames or "timestamp" not in reader.fieldnames:
                raise HistoricalSnapshotPartitionError(
                    "Canonical parent CSV must contain a timestamp column."
                )
            fieldnames = [str(value) for value in reader.fieldnames]
            discovery_writer = csv.DictWriter(
                discovery_file,
                fieldnames=fieldnames,
                extrasaction="raise",
                lineterminator="\n",
            )
            pseudo_writer = csv.DictWriter(
                pseudo_file,
                fieldnames=fieldnames,
                extrasaction="raise",
                lineterminator="\n",
            )
            discovery_writer.writeheader()
            pseudo_writer.writeheader()
            for row_number, row in enumerate(reader, start=2):
                timestamp = _utc_timestamp(
                    row.get("timestamp"),
                    field=f"parent row {row_number} timestamp",
                )
                if previous is not None and timestamp <= previous:
                    raise HistoricalSnapshotPartitionError(
                        "Parent timestamps must be strictly increasing before partitioning."
                    )
                previous = timestamp
                if first_parent is None:
                    first_parent = timestamp
                last_parent = timestamp
                _row_digest_update(parent_digest, fieldnames, row)
                if timestamp < cutoff:
                    discovery_writer.writerow(row)
                    _row_digest_update(discovery_digest, fieldnames, row)
                    discovery_rows += 1
                    if first_discovery is None:
                        first_discovery = timestamp
                    last_discovery = timestamp
                else:
                    pseudo_writer.writerow(row)
                    _row_digest_update(pseudo_digest, fieldnames, row)
                    pseudo_rows += 1
                    if first_pseudo is None:
                        first_pseudo = timestamp
                    last_pseudo = timestamp
    except Exception:
        for path in (discovery_path, pseudo_path):
            path.unlink(missing_ok=True)
        try:
            output.rmdir()
        except OSError:
            pass
        raise

    if discovery_rows <= 0 or pseudo_rows <= 0:
        raise HistoricalSnapshotPartitionError(
            "Both immutable historical child partitions must contain observations."
        )
    if discovery_rows + pseudo_rows != parent.row_count:
        raise HistoricalSnapshotPartitionError(
            "Child row counts do not reconstruct the canonical parent row count."
        )
    if last_discovery is None or not last_discovery < cutoff:
        raise HistoricalSnapshotPartitionError("Discovery partition crosses cutoff.")
    if first_pseudo is None or first_pseudo < cutoff:
        raise HistoricalSnapshotPartitionError(
            "Historical pseudo-OOS partition starts before cutoff."
        )

    discovery = HistoricalChildSnapshotSpec(
        snapshot_id="ETHUSD-30M-DISCOVERY-PRE-2025-07-01-V1",
        evidence_role=EvidenceRole.DISCOVERY,
        source_path=discovery_path,
        start_inclusive="2020-01-01T00:00:00Z",
        end_exclusive=HISTORICAL_CUTOFF_UTC,
    )
    pseudo = HistoricalChildSnapshotSpec(
        snapshot_id="ETHUSD-30M-HISTORICAL-PSEUDO-OOS-POST-2025-07-01-V1",
        evidence_role=EvidenceRole.HISTORICAL_PSEUDO_OOS,
        source_path=pseudo_path,
        start_inclusive=HISTORICAL_CUTOFF_UTC,
        end_exclusive="2026-06-10T00:00:00Z",
    )
    audit = {
        "schema_version": 1,
        "parent_snapshot_id": parent.snapshot_id,
        "parent_sha256": parent.sha256,
        "parent_run_identity_sha256": parent.run_identity_sha256,
        "parent_row_count": parent.row_count,
        "parent_first_timestamp": first_parent.isoformat() if first_parent else None,
        "parent_last_timestamp": last_parent.isoformat() if last_parent else None,
        "parent_canonical_row_digest": parent_digest.hexdigest(),
        "cutoff_utc": HISTORICAL_CUTOFF_UTC,
        "assignment_rule": PARTITION_ASSIGNMENT_RULE,
        "discovery_row_count": discovery_rows,
        "discovery_first_timestamp": first_discovery.isoformat(),
        "discovery_last_timestamp": last_discovery.isoformat(),
        "discovery_canonical_row_digest": discovery_digest.hexdigest(),
        "historical_pseudo_oos_row_count": pseudo_rows,
        "historical_pseudo_oos_first_timestamp": first_pseudo.isoformat(),
        "historical_pseudo_oos_last_timestamp": last_pseudo.isoformat(),
        "historical_pseudo_oos_canonical_row_digest": pseudo_digest.hexdigest(),
    }
    return discovery, pseudo, audit


def create_historical_child_snapshots(
    parent_manifest_path: str | Path,
    *,
    parent_expected_sha256: str,
    partition_source_directory: str | Path,
    snapshot_root: str | Path,
    code_version: Mapping[str, Any] | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    """Create separately role-bound immutable children from the frozen parent."""

    parent_path = Path(parent_manifest_path).expanduser().resolve()
    parent = verify_research_snapshot(
        parent_path,
        expected_sha256=parent_expected_sha256,
    )
    discovery, pseudo, audit = write_historical_partition_sources(
        parent_path,
        parent_expected_sha256=parent_expected_sha256,
        output_directory=partition_source_directory,
    )
    quality_contract = DataQualityContract.from_dict(parent.quality_contract)

    def freeze(spec: HistoricalChildSnapshotSpec, row_count: int) -> Path:
        lineage = {
            "historical_partition": {
                "schema_version": 1,
                "parent_snapshot_id": parent.snapshot_id,
                "parent_sha256": parent.sha256,
                "parent_run_identity_sha256": parent.run_identity_sha256,
                "cutoff_utc": HISTORICAL_CUTOFF_UTC,
                "assignment_rule": PARTITION_ASSIGNMENT_RULE,
                "partition_role": spec.evidence_role.value,
                "partition_start_inclusive": spec.start_inclusive,
                "partition_end_exclusive": spec.end_exclusive,
                "row_count": row_count,
                "parent_canonical_row_digest": audit[
                    "parent_canonical_row_digest"
                ],
            }
        }
        return create_research_snapshot(
            spec.source_path,
            snapshot_root=snapshot_root,
            snapshot_id=spec.snapshot_id,
            quality_contract=quality_contract,
            evidence_role=spec.evidence_role,
            source_classification=SourceClassification.VALIDATED_MARKET_DATA,
            quote_semantics=parent.quote_semantics,
            config_version=lineage,
            code_version=code_version,
        )

    discovery_manifest = freeze(discovery, int(audit["discovery_row_count"]))
    pseudo_manifest = freeze(
        pseudo,
        int(audit["historical_pseudo_oos_row_count"]),
    )
    return discovery_manifest, pseudo_manifest, audit


def _validate_lineage(
    manifest: ResearchSnapshotManifest,
    *,
    parent: ResearchSnapshotManifest,
    expected_role: EvidenceRole,
    expected_start: str,
    expected_end: str,
) -> None:
    lineage = manifest.config_version.get("historical_partition")
    if not isinstance(lineage, Mapping):
        raise HistoricalSnapshotPartitionError(
            f"Child {manifest.snapshot_id} is missing historical partition lineage."
        )
    expected = {
        "schema_version": 1,
        "parent_snapshot_id": parent.snapshot_id,
        "parent_sha256": parent.sha256,
        "parent_run_identity_sha256": parent.run_identity_sha256,
        "cutoff_utc": HISTORICAL_CUTOFF_UTC,
        "assignment_rule": PARTITION_ASSIGNMENT_RULE,
        "partition_role": expected_role.value,
        "partition_start_inclusive": expected_start,
        "partition_end_exclusive": expected_end,
        "row_count": manifest.row_count,
    }
    for key, value in expected.items():
        if lineage.get(key) != value:
            raise HistoricalSnapshotPartitionError(
                f"Child {manifest.snapshot_id} lineage mismatch for {key}."
            )
    digest = lineage.get("parent_canonical_row_digest")
    if not isinstance(digest, str) or len(digest) != 64:
        raise HistoricalSnapshotPartitionError(
            f"Child {manifest.snapshot_id} lacks a parent canonical-row digest."
        )


def validate_historical_child_partition(
    parent_manifest_path: str | Path,
    *,
    parent_expected_sha256: str,
    discovery_manifest_path: str | Path,
    discovery_expected_sha256: str,
    historical_pseudo_oos_manifest_path: str | Path,
    historical_pseudo_oos_expected_sha256: str,
) -> HistoricalPartitionValidation:
    """Read-only verification that both children exactly reconstruct the parent."""

    parent_frame, parent = load_research_snapshot_frame(
        parent_manifest_path,
        expected_sha256=parent_expected_sha256,
    )
    discovery_frame, discovery = load_research_snapshot_frame(
        discovery_manifest_path,
        expected_sha256=discovery_expected_sha256,
    )
    pseudo_frame, pseudo = load_research_snapshot_frame(
        historical_pseudo_oos_manifest_path,
        expected_sha256=historical_pseudo_oos_expected_sha256,
    )
    if discovery.evidence_role is not EvidenceRole.DISCOVERY:
        raise HistoricalSnapshotPartitionError(
            "Discovery child manifest has the wrong immutable evidence role."
        )
    if pseudo.evidence_role is not EvidenceRole.HISTORICAL_PSEUDO_OOS:
        raise HistoricalSnapshotPartitionError(
            "Historical pseudo-OOS child manifest has the wrong immutable evidence role."
        )
    _validate_lineage(
        discovery,
        parent=parent,
        expected_role=EvidenceRole.DISCOVERY,
        expected_start="2020-01-01T00:00:00Z",
        expected_end=HISTORICAL_CUTOFF_UTC,
    )
    _validate_lineage(
        pseudo,
        parent=parent,
        expected_role=EvidenceRole.HISTORICAL_PSEUDO_OOS,
        expected_start=HISTORICAL_CUTOFF_UTC,
        expected_end="2026-06-10T00:00:00Z",
    )

    cutoff = _utc_timestamp(HISTORICAL_CUTOFF_UTC, field="cutoff")
    discovery_timestamps = pd.to_datetime(
        discovery_frame["timestamp"], utc=True, errors="raise"
    )
    pseudo_timestamps = pd.to_datetime(pseudo_frame["timestamp"], utc=True, errors="raise")
    if not discovery_timestamps.lt(cutoff).all():
        raise HistoricalSnapshotPartitionError("Discovery child crosses cutoff.")
    if not pseudo_timestamps.ge(cutoff).all():
        raise HistoricalSnapshotPartitionError(
            "Historical pseudo-OOS child starts before cutoff."
        )
    combined = pd.concat([discovery_frame, pseudo_frame], ignore_index=True)
    try:
        pd.testing.assert_frame_equal(
            combined,
            parent_frame.reset_index(drop=True),
            check_dtype=True,
            check_exact=True,
        )
    except AssertionError as exc:
        raise HistoricalSnapshotPartitionError(
            "Child partitions do not exactly reconstruct the canonical parent frame."
        ) from exc
    if len(combined) != parent.row_count:
        raise HistoricalSnapshotPartitionError(
            "Child row-count sum differs from the canonical parent."
        )

    return HistoricalPartitionValidation(
        parent_snapshot_id=parent.snapshot_id,
        parent_sha256=parent.sha256,
        cutoff_utc=HISTORICAL_CUTOFF_UTC,
        discovery_snapshot_id=discovery.snapshot_id,
        discovery_sha256=discovery.sha256,
        discovery_rows=discovery.row_count,
        discovery_first_timestamp=str(discovery.first_timestamp),
        discovery_last_timestamp=str(discovery.last_timestamp),
        historical_pseudo_oos_snapshot_id=pseudo.snapshot_id,
        historical_pseudo_oos_sha256=pseudo.sha256,
        historical_pseudo_oos_rows=pseudo.row_count,
        historical_pseudo_oos_first_timestamp=str(pseudo.first_timestamp),
        historical_pseudo_oos_last_timestamp=str(pseudo.last_timestamp),
        total_child_rows=len(combined),
        parent_rows=parent.row_count,
        exact_parent_row_reconstruction=True,
    )


__all__ = [
    "HISTORICAL_CUTOFF_UTC",
    "PARTITION_ASSIGNMENT_RULE",
    "HistoricalChildSnapshotSpec",
    "HistoricalPartitionValidation",
    "HistoricalSnapshotPartitionError",
    "create_historical_child_snapshots",
    "validate_historical_child_partition",
    "write_historical_partition_sources",
]
