from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from src.src_data.research_roles import EvidenceRole

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


class HypothesisRegistryError(ValueError):
    """Raised when the append-only hypothesis lifecycle is violated."""


class HypothesisStatus(str, Enum):
    PROPOSED = "PROPOSED"
    SCREENED = "SCREENED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    SIGNAL_PREREGISTERED = "SIGNAL_PREREGISTERED"
    PROSPECTIVE_READY = "PROSPECTIVE_READY"
    PROSPECTIVE_PASSED = "PROSPECTIVE_PASSED"
    PROSPECTIVE_FAILED = "PROSPECTIVE_FAILED"


_ALLOWED_TRANSITIONS: dict[HypothesisStatus, frozenset[HypothesisStatus]] = {
    HypothesisStatus.PROPOSED: frozenset(
        {HypothesisStatus.SCREENED, HypothesisStatus.REJECTED}
    ),
    HypothesisStatus.SCREENED: frozenset(
        {HypothesisStatus.VALIDATED, HypothesisStatus.REJECTED}
    ),
    HypothesisStatus.VALIDATED: frozenset(
        {HypothesisStatus.SIGNAL_PREREGISTERED, HypothesisStatus.REJECTED}
    ),
    HypothesisStatus.SIGNAL_PREREGISTERED: frozenset(
        {HypothesisStatus.PROSPECTIVE_READY, HypothesisStatus.REJECTED}
    ),
    HypothesisStatus.PROSPECTIVE_READY: frozenset(
        {HypothesisStatus.PROSPECTIVE_PASSED, HypothesisStatus.PROSPECTIVE_FAILED}
    ),
    HypothesisStatus.REJECTED: frozenset(),
    HypothesisStatus.PROSPECTIVE_PASSED: frozenset(),
    HypothesisStatus.PROSPECTIVE_FAILED: frozenset(),
}


def _record_key(
    research_id: str,
    hypothesis_id: str,
    version: int,
) -> tuple[str, str, int]:
    if not isinstance(research_id, str) or not research_id.strip():
        raise HypothesisRegistryError("research_id must be non-empty.")
    if not isinstance(hypothesis_id, str) or not hypothesis_id.strip():
        raise HypothesisRegistryError("hypothesis_id must be non-empty.")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise HypothesisRegistryError("version must be an integer >= 1.")
    return research_id, hypothesis_id, version


def _audit_timestamp(value: Any, *, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise HypothesisRegistryError(f"{field_name} must be non-empty.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HypothesisRegistryError(f"{field_name} must be ISO-8601.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HypothesisRegistryError(f"{field_name} must include a timezone.")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class StatusHistoryEntry:
    status: HypothesisStatus
    changed_at: str
    previous_status: HypothesisStatus | None
    reason: str | None

    def validate(self) -> None:
        if not isinstance(self.status, HypothesisStatus):
            raise HypothesisRegistryError("History status must be a HypothesisStatus.")
        _audit_timestamp(self.changed_at, field_name="History changed_at")
        if self.previous_status is not None and not isinstance(
            self.previous_status, HypothesisStatus
        ):
            raise HypothesisRegistryError(
                "History previous_status must be a HypothesisStatus or null."
            )
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise HypothesisRegistryError(
                "Every history entry requires a non-empty reason."
            )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> StatusHistoryEntry:
        if not isinstance(payload, dict):
            raise HypothesisRegistryError("Status history entry must be a mapping.")
        expected = {"status", "changed_at", "previous_status", "reason"}
        missing = sorted(expected.difference(payload))
        unexpected = sorted(set(payload).difference(expected))
        if missing or unexpected:
            raise HypothesisRegistryError(
                f"Status history keys mismatch; missing={missing}, unexpected={unexpected}."
            )
        try:
            entry = cls(
                status=HypothesisStatus(payload["status"]),
                changed_at=payload["changed_at"],
                previous_status=(
                    None
                    if payload["previous_status"] is None
                    else HypothesisStatus(payload["previous_status"])
                ),
                reason=payload["reason"],
            )
        except (TypeError, ValueError) as exc:
            raise HypothesisRegistryError(
                f"Invalid status history entry: {exc}"
            ) from exc
        entry.validate()
        return entry

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "changed_at": self.changed_at,
            "previous_status": (
                None if self.previous_status is None else self.previous_status.value
            ),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class HypothesisRecord:
    research_id: str
    hypothesis_id: str
    version: int
    parent_hypothesis: str | None
    spec_hash: str
    snapshot_ids: tuple[str, ...]
    data_roles: tuple[EvidenceRole, ...]
    created_at: str
    status: HypothesisStatus
    status_history: tuple[StatusHistoryEntry, ...]
    rejection_reason: str | None
    notes: str

    def validate(self) -> None:
        for field_name in ("research_id", "hypothesis_id", "created_at"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise HypothesisRegistryError(f"{field_name} must be non-empty.")
        if (
            isinstance(self.version, bool)
            or not isinstance(self.version, int)
            or self.version < 1
        ):
            raise HypothesisRegistryError("version must be an integer >= 1.")
        if self.parent_hypothesis is not None and (
            not isinstance(self.parent_hypothesis, str)
            or not self.parent_hypothesis.strip()
        ):
            raise HypothesisRegistryError(
                "parent_hypothesis must be non-empty or null."
            )
        if not re.fullmatch(r"[0-9a-f]{64}", self.spec_hash):
            raise HypothesisRegistryError("spec_hash must be a lowercase SHA-256.")
        if not self.snapshot_ids or any(
            not isinstance(value, str) or not value.strip()
            for value in self.snapshot_ids
        ):
            raise HypothesisRegistryError(
                "snapshot_ids must contain non-empty identifiers."
            )
        if len(set(self.snapshot_ids)) != len(self.snapshot_ids):
            raise HypothesisRegistryError("snapshot_ids cannot contain duplicates.")
        if not self.data_roles:
            raise HypothesisRegistryError("data_roles cannot be empty.")
        if any(not isinstance(role, EvidenceRole) for role in self.data_roles):
            raise HypothesisRegistryError(
                "data_roles must contain EvidenceRole values."
            )
        if len(set(self.data_roles)) != len(self.data_roles):
            raise HypothesisRegistryError("data_roles cannot contain duplicates.")
        if not isinstance(self.notes, str):
            raise HypothesisRegistryError("notes must be a string.")
        if not self.status_history or self.status_history[-1].status is not self.status:
            raise HypothesisRegistryError(
                "status_history must end at the current status."
            )
        for entry in self.status_history:
            entry.validate()
        first = self.status_history[0]
        if (
            first.status is not HypothesisStatus.PROPOSED
            or first.previous_status is not None
            or first.changed_at != self.created_at
        ):
            raise HypothesisRegistryError(
                "status_history must begin with PROPOSED at created_at and no previous status."
            )
        for previous, current in zip(self.status_history, self.status_history[1:]):
            if current.previous_status is not previous.status:
                raise HypothesisRegistryError(
                    "status_history previous_status does not match the prior entry."
                )
            if current.status not in _ALLOWED_TRANSITIONS[previous.status]:
                raise HypothesisRegistryError(
                    f"Stored invalid history transition {previous.status.value} -> "
                    f"{current.status.value}."
                )
            if _audit_timestamp(
                current.changed_at,
                field_name="History changed_at",
            ) < _audit_timestamp(
                previous.changed_at,
                field_name="History changed_at",
            ):
                raise HypothesisRegistryError(
                    "status_history timestamps must be chronological."
                )
        if self.status is HypothesisStatus.REJECTED and not self.rejection_reason:
            raise HypothesisRegistryError(
                "REJECTED hypotheses require rejection_reason."
            )
        if (
            self.status is not HypothesisStatus.REJECTED
            and self.rejection_reason is not None
        ):
            raise HypothesisRegistryError(
                "rejection_reason is only valid for REJECTED status."
            )
        if (
            self.status is HypothesisStatus.REJECTED
            and self.rejection_reason != self.status_history[-1].reason
        ):
            raise HypothesisRegistryError(
                "rejection_reason must equal the terminal rejection history reason."
            )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> HypothesisRecord:
        if not isinstance(payload, dict):
            raise HypothesisRegistryError("Hypothesis record must be a mapping.")
        expected = {
            "research_id",
            "hypothesis_id",
            "version",
            "parent_hypothesis",
            "spec_hash",
            "snapshot_ids",
            "data_roles",
            "created_at",
            "status",
            "status_history",
            "rejection_reason",
            "notes",
        }
        missing = sorted(expected.difference(payload))
        unexpected = sorted(set(payload).difference(expected))
        if missing or unexpected:
            raise HypothesisRegistryError(
                f"Hypothesis record keys mismatch; missing={missing}, unexpected={unexpected}."
            )
        try:
            if not isinstance(payload["snapshot_ids"], list):
                raise TypeError("snapshot_ids must be a list")
            if not isinstance(payload["data_roles"], list):
                raise TypeError("data_roles must be a list")
            if not isinstance(payload["status_history"], list):
                raise TypeError("status_history must be a list")
            record = cls(
                research_id=payload["research_id"],
                hypothesis_id=payload["hypothesis_id"],
                version=payload["version"],
                parent_hypothesis=(
                    None
                    if payload["parent_hypothesis"] is None
                    else payload["parent_hypothesis"]
                ),
                spec_hash=payload["spec_hash"],
                snapshot_ids=tuple(payload["snapshot_ids"]),
                data_roles=tuple(
                    EvidenceRole(value) for value in payload["data_roles"]
                ),
                created_at=payload["created_at"],
                status=HypothesisStatus(payload["status"]),
                status_history=tuple(
                    StatusHistoryEntry.from_dict(item)
                    for item in payload["status_history"]
                ),
                rejection_reason=(
                    None
                    if payload["rejection_reason"] is None
                    else payload["rejection_reason"]
                ),
                notes=payload["notes"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HypothesisRegistryError(f"Invalid hypothesis record: {exc}") from exc
        record.validate()
        return record

    def to_dict(self) -> dict[str, Any]:
        return {
            "research_id": self.research_id,
            "hypothesis_id": self.hypothesis_id,
            "version": self.version,
            "parent_hypothesis": self.parent_hypothesis,
            "spec_hash": self.spec_hash,
            "snapshot_ids": list(self.snapshot_ids),
            "data_roles": [role.value for role in self.data_roles],
            "created_at": self.created_at,
            "status": self.status.value,
            "status_history": [entry.to_dict() for entry in self.status_history],
            "rejection_reason": self.rejection_reason,
            "notes": self.notes,
        }


class HypothesisRegistry:
    """Append-only JSONL registry; no record or rejection is rewritten or deleted."""

    schema_version = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def create(
        self,
        *,
        research_id: str,
        hypothesis_id: str,
        version: int,
        spec_hash: str,
        snapshot_ids: Iterable[str],
        data_roles: Iterable[EvidenceRole | str],
        parent_hypothesis: str | None = None,
        notes: str = "",
        created_at: str | None = None,
    ) -> HypothesisRecord:
        timestamp = created_at or datetime.now(timezone.utc).isoformat()
        if isinstance(snapshot_ids, (str, bytes)):
            raise HypothesisRegistryError(
                "snapshot_ids must be an iterable of identifiers."
            )
        if isinstance(data_roles, (str, bytes)):
            raise HypothesisRegistryError("data_roles must be an iterable of roles.")
        record = HypothesisRecord(
            research_id=research_id,
            hypothesis_id=hypothesis_id,
            version=version,
            parent_hypothesis=parent_hypothesis,
            spec_hash=spec_hash,
            snapshot_ids=tuple(snapshot_ids),
            data_roles=tuple(EvidenceRole(value) for value in data_roles),
            created_at=timestamp,
            status=HypothesisStatus.PROPOSED,
            status_history=(
                StatusHistoryEntry(
                    status=HypothesisStatus.PROPOSED,
                    changed_at=timestamp,
                    previous_status=None,
                    reason="hypothesis_registered",
                ),
            ),
            rejection_reason=None,
            notes=notes,
        )
        record.validate()
        with self._locked_file() as handle:
            records = self._records_from_handle(handle)
            key = _record_key(
                record.research_id,
                record.hypothesis_id,
                record.version,
            )
            if key in records:
                raise HypothesisRegistryError(
                    f"Hypothesis version already exists: {key}."
                )
            self._append_event(
                handle, event_type="CREATED", record=record, event_at=timestamp
            )
        return record

    def transition(
        self,
        *,
        research_id: str,
        hypothesis_id: str,
        version: int,
        new_status: HypothesisStatus | str,
        reason: str,
        changed_at: str | None = None,
    ) -> HypothesisRecord:
        target_status = HypothesisStatus(new_status)
        if not isinstance(reason, str) or not reason.strip():
            raise HypothesisRegistryError(
                "Every transition requires a non-empty reason."
            )
        timestamp = changed_at or datetime.now(timezone.utc).isoformat()
        key = _record_key(research_id, hypothesis_id, version)
        with self._locked_file() as handle:
            records = self._records_from_handle(handle)
            if key not in records:
                raise HypothesisRegistryError(f"Unknown hypothesis version: {key}.")
            current = records[key]
            if target_status not in _ALLOWED_TRANSITIONS[current.status]:
                raise HypothesisRegistryError(
                    f"Invalid hypothesis transition {current.status.value} -> "
                    f"{target_status.value}."
                )
            history = current.status_history + (
                StatusHistoryEntry(
                    status=target_status,
                    changed_at=timestamp,
                    previous_status=current.status,
                    reason=reason,
                ),
            )
            updated = replace(
                current,
                status=target_status,
                status_history=history,
                rejection_reason=(
                    reason if target_status is HypothesisStatus.REJECTED else None
                ),
            )
            updated.validate()
            self._append_event(
                handle,
                event_type="STATUS_TRANSITION",
                record=updated,
                event_at=timestamp,
            )
        return updated

    def get(
        self,
        *,
        research_id: str,
        hypothesis_id: str,
        version: int,
    ) -> HypothesisRecord:
        key = _record_key(research_id, hypothesis_id, version)
        if not self.path.is_file():
            raise HypothesisRegistryError(f"Registry does not exist: {self.path}")
        with self.path.open("r", encoding="utf-8") as handle:
            records = self._records_from_handle(handle)
        if key not in records:
            raise HypothesisRegistryError(f"Unknown hypothesis version: {key}.")
        return records[key]

    def list_records(self) -> tuple[HypothesisRecord, ...]:
        if not self.path.is_file():
            return ()
        with self.path.open("r", encoding="utf-8") as handle:
            records = self._records_from_handle(handle)
        return tuple(records[key] for key in sorted(records))

    def _locked_file(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+", encoding="utf-8")
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)

        class _LockContext:
            def __enter__(self_nonlocal):
                return handle

            def __exit__(self_nonlocal, exc_type, exc, traceback):
                try:
                    if fcntl is not None:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                finally:
                    handle.close()
                return False

        return _LockContext()

    def _records_from_handle(
        self, handle
    ) -> dict[tuple[str, str, int], HypothesisRecord]:
        handle.seek(0)
        records: dict[tuple[str, str, int], HypothesisRecord] = {}
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                event = json.loads(raw_line)
                if not isinstance(event, dict):
                    raise HypothesisRegistryError("Registry event must be a mapping.")
                expected_event_keys = {
                    "schema_version",
                    "event_type",
                    "event_at",
                    "record",
                }
                missing = sorted(expected_event_keys.difference(event))
                unexpected = sorted(set(event).difference(expected_event_keys))
                if missing or unexpected:
                    raise HypothesisRegistryError(
                        f"Registry event keys mismatch; missing={missing}, "
                        f"unexpected={unexpected}."
                    )
                if (
                    isinstance(event["schema_version"], bool)
                    or event["schema_version"] != self.schema_version
                ):
                    raise HypothesisRegistryError(
                        "Unsupported registry schema version."
                    )
                if (
                    not isinstance(event["event_at"], str)
                    or not event["event_at"].strip()
                ):
                    raise HypothesisRegistryError("event_at must be non-empty.")
                record = HypothesisRecord.from_dict(event["record"])
                if event["event_at"] != record.status_history[-1].changed_at:
                    raise HypothesisRegistryError(
                        "event_at must equal the latest status-history timestamp."
                    )
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise HypothesisRegistryError(
                    f"Invalid registry event at line {line_number}: {exc}"
                ) from exc
            key = (record.research_id, record.hypothesis_id, record.version)
            previous = records.get(key)
            event_type = event.get("event_type")
            if previous is None:
                if event_type != "CREATED" or len(record.status_history) != 1:
                    raise HypothesisRegistryError(
                        f"First event for {key} must be CREATED at line {line_number}."
                    )
            else:
                if event_type != "STATUS_TRANSITION":
                    raise HypothesisRegistryError(
                        f"Subsequent event for {key} must be STATUS_TRANSITION."
                    )
                if record.status_history[:-1] != previous.status_history:
                    raise HypothesisRegistryError(
                        f"Status history was rewritten for {key} at line {line_number}."
                    )
                immutable_fields = (
                    "research_id",
                    "hypothesis_id",
                    "version",
                    "parent_hypothesis",
                    "spec_hash",
                    "snapshot_ids",
                    "data_roles",
                    "created_at",
                    "notes",
                )
                rewritten_fields = [
                    field_name
                    for field_name in immutable_fields
                    if getattr(record, field_name) != getattr(previous, field_name)
                ]
                if rewritten_fields:
                    raise HypothesisRegistryError(
                        f"Immutable hypothesis fields were rewritten for {key} at "
                        f"line {line_number}: {rewritten_fields}."
                    )
                if record.status not in _ALLOWED_TRANSITIONS[previous.status]:
                    raise HypothesisRegistryError(
                        f"Stored invalid transition for {key} at line {line_number}."
                    )
            records[key] = record
        return records

    def _append_event(
        self,
        handle,
        *,
        event_type: str,
        record: HypothesisRecord,
        event_at: str,
    ) -> None:
        event = {
            "schema_version": self.schema_version,
            "event_type": event_type,
            "event_at": event_at,
            "record": record.to_dict(),
        }
        handle.seek(0, os.SEEK_END)
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def hypothesis_registry_schema() -> dict[str, Any]:
    return {
        "schema_version": HypothesisRegistry.schema_version,
        "status_enum": [status.value for status in HypothesisStatus],
        "allowed_transitions": {
            status.value: sorted(target.value for target in targets)
            for status, targets in _ALLOWED_TRANSITIONS.items()
        },
        "storage": "append_only_jsonl",
    }


__all__ = [
    "HypothesisRecord",
    "HypothesisRegistry",
    "HypothesisRegistryError",
    "HypothesisStatus",
    "StatusHistoryEntry",
    "hypothesis_registry_schema",
]
