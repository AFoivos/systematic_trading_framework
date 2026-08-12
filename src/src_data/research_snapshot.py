from __future__ import annotations

import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from src.src_data.quality import (
    DataQualityContract,
    DataQualityReport,
    QualitySeverity,
    run_data_quality_checks,
    write_quality_report,
)
from src.src_data.research_roles import EvidenceRole, SourceClassification
from src.utils.run_metadata import (
    collect_git_metadata,
    compute_config_hash,
    file_sha256,
)

SNAPSHOT_MANIFEST_SCHEMA_VERSION = 1
_SNAPSHOT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_MANIFEST_KEYS = {
    "schema_version",
    "snapshot_id",
    "created_at",
    "source_path",
    "data_file",
    "asset",
    "timeframe",
    "timezone",
    "row_count",
    "first_timestamp",
    "last_timestamp",
    "sha256",
    "schema",
    "column_units",
    "quote_semantics",
    "volume_semantics",
    "cadence",
    "quality_contract",
    "quality",
    "evidence_role",
    "source_classification",
    "research_role_eligibility",
    "code_version",
    "config_version",
    "run_identity_sha256",
}
_PROCESSED_EXACT_COLUMNS = {
    "label",
    "target",
    "prediction",
    "position",
    "positions",
    "signal",
    "is_oos",
    "oos_marker",
}
_PROCESSED_PREFIXES = ("pred_", "target_", "signal_", "feature_")


class ResearchSnapshotError(RuntimeError):
    """Raised when a research snapshot is mutable, inconsistent, or ineligible."""


@dataclass(frozen=True)
class ResearchSnapshotManifest:
    schema_version: int
    snapshot_id: str
    created_at: str
    source_path: str
    data_file: str
    asset: str
    timeframe: str
    timezone: str
    row_count: int
    first_timestamp: str | None
    last_timestamp: str | None
    sha256: str
    schema: dict[str, Any]
    column_units: dict[str, str]
    quote_semantics: dict[str, Any]
    volume_semantics: str | None
    cadence: str | None
    quality_contract: dict[str, Any]
    quality: dict[str, Any]
    evidence_role: EvidenceRole
    source_classification: SourceClassification
    research_role_eligibility: dict[str, Any]
    code_version: dict[str, Any]
    config_version: dict[str, Any]
    run_identity_sha256: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ResearchSnapshotManifest:
        if not isinstance(payload, Mapping):
            raise ResearchSnapshotError("Snapshot manifest must be a JSON object.")
        missing = sorted(_MANIFEST_KEYS.difference(payload))
        unexpected = sorted(set(payload).difference(_MANIFEST_KEYS))
        if missing or unexpected:
            raise ResearchSnapshotError(
                f"Snapshot manifest schema mismatch; missing={missing}, unexpected={unexpected}."
            )
        try:
            manifest = cls(
                schema_version=int(payload["schema_version"]),
                snapshot_id=str(payload["snapshot_id"]),
                created_at=str(payload["created_at"]),
                source_path=str(payload["source_path"]),
                data_file=str(payload["data_file"]),
                asset=str(payload["asset"]),
                timeframe=str(payload["timeframe"]),
                timezone=str(payload["timezone"]),
                row_count=int(payload["row_count"]),
                first_timestamp=payload["first_timestamp"],
                last_timestamp=payload["last_timestamp"],
                sha256=str(payload["sha256"]),
                schema=dict(payload["schema"]),
                column_units={
                    str(k): str(v) for k, v in dict(payload["column_units"]).items()
                },
                quote_semantics=dict(payload["quote_semantics"]),
                volume_semantics=(
                    None
                    if payload["volume_semantics"] is None
                    else str(payload["volume_semantics"])
                ),
                cadence=None if payload["cadence"] is None else str(payload["cadence"]),
                quality_contract=dict(payload["quality_contract"]),
                quality=dict(payload["quality"]),
                evidence_role=EvidenceRole(payload["evidence_role"]),
                source_classification=SourceClassification(
                    payload["source_classification"]
                ),
                research_role_eligibility=dict(payload["research_role_eligibility"]),
                code_version=dict(payload["code_version"]),
                config_version=dict(payload["config_version"]),
                run_identity_sha256=str(payload["run_identity_sha256"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ResearchSnapshotError(f"Invalid snapshot manifest: {exc}") from exc
        manifest.validate()
        return manifest

    def validate(self) -> None:
        if self.schema_version != SNAPSHOT_MANIFEST_SCHEMA_VERSION:
            raise ResearchSnapshotError(
                f"Unsupported snapshot manifest schema_version={self.schema_version}."
            )
        _validate_snapshot_id(self.snapshot_id)
        _validate_created_at(self.created_at)
        if (
            not self.asset.strip()
            or not self.timeframe.strip()
            or not self.timezone.strip()
        ):
            raise ResearchSnapshotError(
                "asset, timeframe, and timezone must be non-empty."
            )
        if self.row_count < 0:
            raise ResearchSnapshotError("row_count must be >= 0.")
        _validate_sha256(self.sha256, field="sha256")
        _validate_sha256(self.run_identity_sha256, field="run_identity_sha256")
        columns = self.schema.get("column_names")
        dtypes = self.schema.get("column_dtypes")
        if not isinstance(columns, list) or not isinstance(dtypes, dict):
            raise ResearchSnapshotError(
                "schema must contain column_names (list) and column_dtypes (mapping)."
            )
        if set(map(str, columns)) != set(map(str, dtypes)):
            raise ResearchSnapshotError(
                "schema column_names and column_dtypes disagree."
            )
        if not isinstance(self.quality.get("research_eligible"), bool):
            raise ResearchSnapshotError("quality.research_eligible must be boolean.")
        try:
            serialized_contract = DataQualityContract.from_dict(self.quality_contract)
        except ValueError as exc:
            raise ResearchSnapshotError(str(exc)) from exc
        if (
            serialized_contract.asset != self.asset
            or serialized_contract.timeframe != self.timeframe
        ):
            raise ResearchSnapshotError(
                "quality_contract asset/timeframe differs from the manifest."
            )
        if (
            serialized_contract.timezone != self.timezone
            or serialized_contract.cadence != self.cadence
        ):
            raise ResearchSnapshotError(
                "quality_contract timezone/cadence differs from the manifest."
            )
        if dict(serialized_contract.column_units) != self.column_units:
            raise ResearchSnapshotError(
                "quality_contract column units differ from the manifest."
            )
        if not isinstance(self.research_role_eligibility.get("eligible"), bool):
            raise ResearchSnapshotError(
                "research_role_eligibility.eligible must be boolean."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at,
            "source_path": self.source_path,
            "data_file": self.data_file,
            "asset": self.asset,
            "timeframe": self.timeframe,
            "timezone": self.timezone,
            "row_count": self.row_count,
            "first_timestamp": self.first_timestamp,
            "last_timestamp": self.last_timestamp,
            "sha256": self.sha256,
            "schema": dict(self.schema),
            "column_units": dict(self.column_units),
            "quote_semantics": dict(self.quote_semantics),
            "volume_semantics": self.volume_semantics,
            "cadence": self.cadence,
            "quality_contract": dict(self.quality_contract),
            "quality": dict(self.quality),
            "evidence_role": self.evidence_role.value,
            "source_classification": self.source_classification.value,
            "research_role_eligibility": dict(self.research_role_eligibility),
            "code_version": dict(self.code_version),
            "config_version": dict(self.config_version),
            "run_identity_sha256": self.run_identity_sha256,
        }


def _validate_snapshot_id(snapshot_id: str) -> None:
    if not isinstance(snapshot_id, str) or not _SNAPSHOT_ID_PATTERN.fullmatch(
        snapshot_id
    ):
        raise ResearchSnapshotError(
            "snapshot_id must match ^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$."
        )


def _validate_sha256(value: str, *, field: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ResearchSnapshotError(
            f"{field} must be a lowercase 64-character SHA-256."
        )


def _validate_created_at(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ResearchSnapshotError(
            "created_at must be a non-empty ISO-8601 timestamp."
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResearchSnapshotError(
            "created_at must be an ISO-8601 timestamp."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ResearchSnapshotError("created_at must include a timezone.")


def _read_snapshot_source(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ResearchSnapshotError(
        f"Unsupported research snapshot format '{suffix}'. Supported: CSV, Parquet."
    )


def _schema_payload(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "column_names": [str(column) for column in frame.columns],
        "column_dtypes": {
            str(column): str(dtype) for column, dtype in frame.dtypes.items()
        },
    }


def detect_processed_artifact_markers(
    source_path: str | Path,
    frame: pd.DataFrame,
) -> list[str]:
    """Detect strong processed/model/backtest markers without guessing alpha content."""

    path = Path(source_path)
    markers: list[str] = []
    lowered_parts = {part.lower() for part in path.parts}
    if lowered_parts.intersection(
        {"processed", "artifacts", "predictions", "backtests"}
    ):
        markers.append("path_classification")
    for raw_column in frame.columns:
        column = str(raw_column).strip().lower()
        if (
            column in _PROCESSED_EXACT_COLUMNS
            or column.startswith(_PROCESSED_PREFIXES)
            or column.endswith("_is_oos")
        ):
            markers.append(f"column:{raw_column}")
    return sorted(set(markers))


def _research_role_eligibility(
    *,
    quality_report: DataQualityReport,
    source_classification: SourceClassification,
    evidence_role: EvidenceRole,
) -> dict[str, Any]:
    reasons: list[str] = []
    if not quality_report.research_eligible:
        reasons.append("DATA_QUALITY_BLOCKING_ISSUES")
    if source_classification is not SourceClassification.VALIDATED_MARKET_DATA:
        reasons.append(f"SOURCE_CLASSIFICATION_{source_classification.value}")
    if evidence_role is EvidenceRole.PROSPECTIVE_FINAL:
        reasons.append("SEPARATE_PROSPECTIVE_ACCESS_REQUIRED")
    return {
        "eligible": not reasons,
        "eligible_roles": [evidence_role.value] if not reasons else [],
        "reasons": reasons,
    }


def _run_identity_payload(
    *,
    snapshot_id: str,
    sha256: str,
    evidence_role: EvidenceRole,
    source_classification: SourceClassification,
    quality_contract: Mapping[str, Any],
    quote_semantics: Mapping[str, Any],
    code_version: Mapping[str, Any],
    config_version: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    return compute_config_hash(
        {
            "snapshot_id": snapshot_id,
            "expected_sha256": sha256,
            "evidence_role": evidence_role.value,
            "source_classification": source_classification.value,
            "quality_contract": dict(quality_contract),
            "quote_semantics": dict(quote_semantics),
            "code_version": dict(code_version),
            "config_version": dict(config_version),
        }
    )


def _require_unique_snapshot_bytes(
    *,
    snapshot_root: Path,
    source_sha256: str,
    requested_role: EvidenceRole,
) -> None:
    """Prevent the same known bytes from being reassigned to another evidence role."""

    for existing_path in sorted(snapshot_root.glob("*/manifest.json")):
        existing = load_research_snapshot_manifest(existing_path)
        existing_data_path = (existing_path.parent / existing.data_file).resolve()
        try:
            existing_data_path.relative_to(existing_path.parent.resolve())
        except ValueError as exc:
            raise ResearchSnapshotError(
                f"Existing snapshot {existing.snapshot_id} escapes its snapshot directory."
            ) from exc
        if not existing_data_path.is_file():
            raise ResearchSnapshotError(
                f"Existing snapshot {existing.snapshot_id} is missing its frozen data file."
            )
        existing_actual_sha256 = file_sha256(existing_data_path)
        if existing_actual_sha256 != existing.sha256:
            raise ResearchSnapshotError(
                f"Existing snapshot {existing.snapshot_id} has mutated bytes; "
                "new snapshot creation is blocked until the registry is repaired."
            )
        if existing_actual_sha256 != source_sha256:
            continue
        if existing.evidence_role is not requested_role:
            raise ResearchSnapshotError(
                "Evidence-role relabeling by duplicate snapshot is forbidden: source bytes "
                f"already belong to snapshot {existing.snapshot_id} with role "
                f"{existing.evidence_role.value}, not {requested_role.value}."
            )


def create_research_snapshot(
    source_path: str | Path,
    *,
    snapshot_root: str | Path,
    snapshot_id: str,
    quality_contract: DataQualityContract,
    evidence_role: EvidenceRole | str,
    source_classification: SourceClassification | str,
    quote_semantics: Mapping[str, Any],
    config_version: Mapping[str, Any] | None = None,
    code_version: Mapping[str, Any] | None = None,
    created_at: str | None = None,
) -> Path:
    """Freeze source bytes and their reviewed contract without overwriting.

    The snapshot directory is write-once. Failed quality is still recorded for
    audit, but role access remains blocked. The source bytes are copied exactly;
    no parsing, sorting, or normalization is applied during freezing.
    """

    _validate_snapshot_id(snapshot_id)
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Research snapshot source not found: {source}")
    role = EvidenceRole(evidence_role)
    classification = SourceClassification(source_classification)
    root = Path(snapshot_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = root / snapshot_id
    if target.exists():
        raise ResearchSnapshotError(
            f"Immutable snapshot already exists and will not be overwritten: {target}"
        )

    source_sha256 = file_sha256(source)
    _require_unique_snapshot_bytes(
        snapshot_root=root,
        source_sha256=source_sha256,
        requested_role=role,
    )
    frame = _read_snapshot_source(source)
    processed_markers = detect_processed_artifact_markers(source, frame)
    if (
        classification is SourceClassification.VALIDATED_MARKET_DATA
        and processed_markers
    ):
        raise ResearchSnapshotError(
            "Refusing VALIDATED_MARKET_DATA classification because processed-artifact "
            f"markers were detected: {processed_markers}."
        )
    quality_report = run_data_quality_checks(frame, quality_contract)
    eligibility = _research_role_eligibility(
        quality_report=quality_report,
        source_classification=classification,
        evidence_role=role,
    )
    resolved_config_version = dict(config_version or {})
    resolved_code_version = dict(code_version or collect_git_metadata())
    run_identity_sha256, _ = _run_identity_payload(
        snapshot_id=snapshot_id,
        sha256=source_sha256,
        evidence_role=role,
        source_classification=classification,
        quality_contract=quality_contract.to_dict(),
        quote_semantics=quote_semantics,
        code_version=resolved_code_version,
        config_version=resolved_config_version,
    )

    suffix = source.suffix.lower()
    data_filename = f"data{suffix}"
    timestamp = created_at or datetime.now(timezone.utc).isoformat()
    manifest = ResearchSnapshotManifest(
        schema_version=SNAPSHOT_MANIFEST_SCHEMA_VERSION,
        snapshot_id=snapshot_id,
        created_at=timestamp,
        source_path=str(source),
        data_file=data_filename,
        asset=quality_contract.asset,
        timeframe=quality_contract.timeframe,
        timezone=quality_contract.timezone,
        row_count=int(len(frame)),
        first_timestamp=quality_report.metrics.get("first_timestamp"),
        last_timestamp=quality_report.metrics.get("last_timestamp"),
        sha256=source_sha256,
        schema=_schema_payload(frame),
        column_units={str(k): str(v) for k, v in quality_contract.column_units.items()},
        quote_semantics={str(k): v for k, v in dict(quote_semantics).items()},
        volume_semantics=quality_contract.volume_semantics,
        cadence=quality_contract.cadence,
        quality_contract=quality_contract.to_dict(),
        quality=quality_report.to_dict(),
        evidence_role=role,
        source_classification=classification,
        research_role_eligibility=eligibility,
        code_version=resolved_code_version,
        config_version=resolved_config_version,
        run_identity_sha256=run_identity_sha256,
    )
    manifest.validate()

    temporary = Path(tempfile.mkdtemp(prefix=f".{snapshot_id}.", dir=root))
    try:
        frozen_data = temporary / data_filename
        shutil.copyfile(source, frozen_data)
        copied_sha256 = file_sha256(frozen_data)
        if copied_sha256 != source_sha256:
            raise ResearchSnapshotError(
                "Snapshot copy SHA-256 differs from the source bytes; freeze aborted."
            )
        (temporary / "manifest.json").write_text(
            json.dumps(manifest.to_dict(), indent=2, sort_keys=True, default=str)
            + "\n",
            encoding="utf-8",
        )
        write_quality_report(
            quality_report,
            json_path=temporary / "quality_report.json",
            markdown_path=temporary / "quality_report.md",
        )
        temporary.rename(target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target / "manifest.json"


def load_research_snapshot_manifest(
    manifest_path: str | Path,
) -> ResearchSnapshotManifest:
    path = Path(manifest_path).expanduser().resolve()
    if path.is_dir():
        path = path / "manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"Research snapshot manifest not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResearchSnapshotError(
            f"Invalid snapshot manifest JSON at {path}: {exc}"
        ) from exc
    return ResearchSnapshotManifest.from_dict(payload)


def verify_research_snapshot(
    manifest_path: str | Path,
    *,
    expected_sha256: str,
) -> ResearchSnapshotManifest:
    """Enforce config SHA, copied-byte SHA, schema, dtype, and row-count identity."""

    _validate_sha256(expected_sha256, field="expected_sha256")
    path = Path(manifest_path).expanduser().resolve()
    if path.is_dir():
        path = path / "manifest.json"
    manifest = load_research_snapshot_manifest(path)
    if manifest.sha256 != expected_sha256:
        raise ResearchSnapshotError(
            f"Configured SHA-256 {expected_sha256} does not match snapshot manifest "
            f"SHA-256 {manifest.sha256}."
        )
    data_path = (path.parent / manifest.data_file).resolve()
    try:
        data_path.relative_to(path.parent)
    except ValueError as exc:
        raise ResearchSnapshotError(
            "Snapshot data_file escapes the snapshot directory."
        ) from exc
    if not data_path.is_file():
        raise ResearchSnapshotError(
            f"Frozen snapshot data file is missing: {data_path}"
        )
    actual_sha256 = file_sha256(data_path)
    if actual_sha256 != expected_sha256:
        raise ResearchSnapshotError(
            f"Frozen snapshot bytes changed: expected {expected_sha256}, found {actual_sha256}."
        )

    frame = _read_snapshot_source(data_path)
    actual_schema = _schema_payload(frame)
    if actual_schema != manifest.schema:
        raise ResearchSnapshotError(
            "Frozen snapshot schema/dtypes differ from the immutable manifest."
        )
    if len(frame) != manifest.row_count:
        raise ResearchSnapshotError(
            f"Frozen snapshot row count changed: expected {manifest.row_count}, found {len(frame)}."
        )
    try:
        quality_contract = DataQualityContract.from_dict(manifest.quality_contract)
    except ValueError as exc:
        raise ResearchSnapshotError(str(exc)) from exc
    actual_quality = run_data_quality_checks(frame, quality_contract).to_dict()
    if actual_quality != manifest.quality:
        raise ResearchSnapshotError(
            "Frozen snapshot quality report differs from a fresh evaluation of its "
            "serialized quality contract."
        )
    expected_run_identity, _ = _run_identity_payload(
        snapshot_id=manifest.snapshot_id,
        sha256=manifest.sha256,
        evidence_role=manifest.evidence_role,
        source_classification=manifest.source_classification,
        quality_contract=manifest.quality_contract,
        quote_semantics=manifest.quote_semantics,
        code_version=manifest.code_version,
        config_version=manifest.config_version,
    )
    if expected_run_identity != manifest.run_identity_sha256:
        raise ResearchSnapshotError(
            "Snapshot run identity does not match its immutable contract."
        )
    return manifest


def load_research_snapshot_frame(
    manifest_path: str | Path,
    *,
    expected_sha256: str,
) -> tuple[pd.DataFrame, ResearchSnapshotManifest]:
    path = Path(manifest_path).expanduser().resolve()
    if path.is_dir():
        path = path / "manifest.json"
    manifest = verify_research_snapshot(path, expected_sha256=expected_sha256)
    return _read_snapshot_source(path.parent / manifest.data_file), manifest


def has_critical_quality_failure(manifest: ResearchSnapshotManifest) -> bool:
    issues = manifest.quality.get("issues", [])
    return any(
        isinstance(issue, Mapping)
        and issue.get("severity") == QualitySeverity.CRITICAL.value
        for issue in issues
    )


__all__ = [
    "ResearchSnapshotError",
    "ResearchSnapshotManifest",
    "SNAPSHOT_MANIFEST_SCHEMA_VERSION",
    "create_research_snapshot",
    "detect_processed_artifact_markers",
    "has_critical_quality_failure",
    "load_research_snapshot_frame",
    "load_research_snapshot_manifest",
    "verify_research_snapshot",
]
