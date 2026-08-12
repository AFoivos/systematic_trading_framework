from __future__ import annotations

from datetime import datetime
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.src_data.research_roles import EvidenceRole, SourceClassification
from src.src_data.research_snapshot import (
    ResearchSnapshotManifest,
    has_critical_quality_failure,
    load_research_snapshot_frame,
)


class ResearchAccessDenied(PermissionError):
    """Raised when data role, quarantine, or quality policy denies a load."""


@dataclass(frozen=True)
class SnapshotReference:
    snapshot_id: str
    manifest_path: Path
    expected_sha256: str
    evidence_role: EvidenceRole
    frozen_spec_sha256: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SnapshotReference:
        if not isinstance(payload, dict):
            raise ResearchAccessDenied("Snapshot reference must be a mapping.")
        required = {"snapshot_id", "manifest_path", "expected_sha256", "evidence_role"}
        allowed = required | {"frozen_spec_sha256"}
        missing = sorted(required.difference(payload))
        unexpected = sorted(set(payload).difference(allowed))
        if missing or unexpected:
            raise ResearchAccessDenied(
                f"Snapshot reference schema mismatch; missing={missing}, "
                f"unexpected={unexpected}."
            )
        return cls(
            snapshot_id=str(payload["snapshot_id"]),
            manifest_path=Path(str(payload["manifest_path"])),
            expected_sha256=str(payload["expected_sha256"]),
            evidence_role=EvidenceRole(payload["evidence_role"]),
            frozen_spec_sha256=(
                None
                if payload.get("frozen_spec_sha256") is None
                else str(payload["frozen_spec_sha256"])
            ),
        )


@dataclass(frozen=True)
class ProcessedArtifactOverride:
    enabled: bool = False
    warning_acknowledged: bool = False
    reason: str | None = None

    def validate(self) -> None:
        if not isinstance(self.enabled, bool) or not isinstance(
            self.warning_acknowledged, bool
        ):
            raise ResearchAccessDenied(
                "Processed-artifact override flags must be booleans."
            )
        if self.enabled and (
            not self.warning_acknowledged
            or not isinstance(self.reason, str)
            or not self.reason.strip()
        ):
            raise ResearchAccessDenied(
                "Processed-artifact override requires enabled=true, "
                "warning_acknowledged=true, and a non-empty reason."
            )


@dataclass(frozen=True)
class LoadedResearchData:
    frame: pd.DataFrame
    manifest: ResearchSnapshotManifest


@dataclass(frozen=True)
class ProspectiveAccessAuthorization:
    explicitly_authorized: bool
    approved_by: str
    approved_at: str
    frozen_spec_sha256: str
    purpose: str

    def validate(self) -> None:
        if not isinstance(self.explicitly_authorized, bool):
            raise ResearchAccessDenied(
                "Prospective explicitly_authorized flag must be boolean."
            )
        if not self.explicitly_authorized:
            raise ResearchAccessDenied(
                "Prospective-final access was not explicitly authorized."
            )
        for field_name in (
            "approved_by",
            "approved_at",
            "frozen_spec_sha256",
            "purpose",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ResearchAccessDenied(
                    f"Prospective authorization requires non-empty {field_name}."
                )
        if not re.fullmatch(r"[0-9a-f]{64}", self.frozen_spec_sha256):
            raise ResearchAccessDenied(
                "Prospective authorization frozen_spec_sha256 must be a lowercase SHA-256."
            )
        try:
            approved_at = datetime.fromisoformat(
                self.approved_at.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise ResearchAccessDenied(
                "Prospective authorization approved_at must be an ISO-8601 timestamp."
            ) from exc
        if approved_at.tzinfo is None or approved_at.utcoffset() is None:
            raise ResearchAccessDenied(
                "Prospective authorization approved_at must include a timezone."
            )


class _RoleBoundDataAccess:
    _allowed_role: EvidenceRole

    def __init__(
        self,
        *,
        processed_artifact_override: ProcessedArtifactOverride | None = None,
    ) -> None:
        self._processed_override = (
            processed_artifact_override or ProcessedArtifactOverride()
        )
        self._processed_override.validate()

    def _load_role(self, reference: SnapshotReference) -> LoadedResearchData:
        if reference.evidence_role is not self._allowed_role:
            raise ResearchAccessDenied(
                f"{type(self).__name__} only accepts {self._allowed_role.value}; "
                f"reference requested {reference.evidence_role.value}."
            )
        frame, manifest = load_research_snapshot_frame(
            reference.manifest_path,
            expected_sha256=reference.expected_sha256,
        )
        if manifest.snapshot_id != reference.snapshot_id:
            raise ResearchAccessDenied(
                f"Snapshot ID mismatch: reference={reference.snapshot_id}, "
                f"manifest={manifest.snapshot_id}."
            )
        if manifest.evidence_role is not reference.evidence_role:
            raise ResearchAccessDenied(
                f"Immutable evidence-role mismatch: reference={reference.evidence_role.value}, "
                f"manifest={manifest.evidence_role.value}."
            )
        if has_critical_quality_failure(manifest):
            raise ResearchAccessDenied(
                "CRITICAL data-quality failure prevents research use."
            )
        if not bool(manifest.quality.get("research_eligible", False)):
            raise ResearchAccessDenied(
                "Snapshot quality report is not research eligible (ERROR or CRITICAL issue)."
            )

        classification = manifest.source_classification
        if classification is SourceClassification.PROCESSED_EXPERIMENT_ARTIFACT:
            if not self._processed_override.enabled:
                raise ResearchAccessDenied(
                    "Processed experiment/backtest artifacts are quarantined by default."
                )
            warnings.warn(
                "Processed experiment artifact override is active; this source may contain "
                "features, targets, predictions, signals, or OOS markers. Reason: "
                f"{self._processed_override.reason}",
                RuntimeWarning,
                stacklevel=2,
            )
        elif classification is not SourceClassification.VALIDATED_MARKET_DATA:
            raise ResearchAccessDenied(
                f"Source classification {classification.value} is not eligible for research access."
            )
        return LoadedResearchData(frame=frame, manifest=manifest)


class DiscoveryDataAccess(_RoleBoundDataAccess):
    """The only data interface accepted by the future discovery pipeline."""

    _allowed_role = EvidenceRole.DISCOVERY

    def load_discovery(self, reference: SnapshotReference) -> LoadedResearchData:
        return self._load_role(reference)


class ValidationDataAccess(_RoleBoundDataAccess):
    """Separate validation-only access; it cannot relabel data as discovery."""

    _allowed_role = EvidenceRole.VALIDATION

    def load_validation(self, reference: SnapshotReference) -> LoadedResearchData:
        return self._load_role(reference)


class HistoricalPseudoOOSDataAccess(_RoleBoundDataAccess):
    """Diagnostic historical evidence that can never become final evidence."""

    _allowed_role = EvidenceRole.HISTORICAL_PSEUDO_OOS

    def load_historical_diagnostic(
        self,
        reference: SnapshotReference,
    ) -> LoadedResearchData:
        return self._load_role(reference)


class ProspectiveFinalDataAccess(_RoleBoundDataAccess):
    """Explicitly authorized, separately instantiated prospective-only access."""

    _allowed_role = EvidenceRole.PROSPECTIVE_FINAL

    def __init__(self, authorization: ProspectiveAccessAuthorization) -> None:
        authorization.validate()
        super().__init__()
        self._authorization = authorization

    def load_prospective_final(
        self, reference: SnapshotReference
    ) -> LoadedResearchData:
        if reference.frozen_spec_sha256 != self._authorization.frozen_spec_sha256:
            raise ResearchAccessDenied(
                "Prospective snapshot reference must bind the exact authorized frozen spec SHA."
            )
        loaded = self._load_role(reference)
        manifest_spec_sha = loaded.manifest.config_version.get(
            "frozen_specification_sha256"
        )
        if manifest_spec_sha != self._authorization.frozen_spec_sha256:
            raise ResearchAccessDenied(
                "Prospective snapshot manifest is not bound to the authorized frozen spec SHA."
            )
        return loaded


__all__ = [
    "DiscoveryDataAccess",
    "HistoricalPseudoOOSDataAccess",
    "LoadedResearchData",
    "ProcessedArtifactOverride",
    "ProspectiveAccessAuthorization",
    "ProspectiveFinalDataAccess",
    "ResearchAccessDenied",
    "SnapshotReference",
    "ValidationDataAccess",
]
