"""Immutable JSON persistence under a caller-provided artifact directory."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any, TypeVar

from ..candidate import CandidateStatus, ResearchCandidate
from ..contracts import ResearchContractError, _require_identifier
from ..decisions import DecisionKind, PromotionDecision
from ..evidence import CanonicalValidationRecord, EvidenceRecord
from ..lifecycle import apply_promotion_decision, require_transition_allowed
from ..robustness import MinimumEvidencePolicy, RobustnessRecord
from ..run import ResearchRun
from ..selection import SelectionRecord
from ..serialization import deterministic_json_dumps


class ResearchStoreError(RuntimeError):
    """Raised when immutable research metadata is missing, corrupt, or rewritten."""


RecordT = TypeVar("RecordT")


_COLLECTIONS = {
    "candidates",
    "runs",
    "selections",
    "evidence",
    "validations",
    "robustness",
    "decisions",
}


class FilesystemResearchStore:
    """Deterministic record store compatible with existing artifact directories.

    Candidate identity is written once. Current status is reconstructed from
    immutable decision records, so no candidate JSON is ever overwritten and a
    rejection remains part of the audit trail.
    """

    schema_version = 1

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        if self.root.exists() and not self.root.is_dir():
            raise ResearchStoreError(f"Research store root is not a directory: {self.root}")

    def save_candidate(self, candidate: ResearchCandidate) -> None:
        if not isinstance(candidate, ResearchCandidate):
            raise ResearchStoreError("candidate must be a ResearchCandidate.")
        if candidate.status not in {
            CandidateStatus.SCREENED,
            CandidateStatus.PENDING_CANONICAL_VALIDATION,
        }:
            raise ResearchStoreError(
                "A persisted candidate must start at SCREENED or "
                "PENDING_CANONICAL_VALIDATION; later states belong in decisions."
            )
        self._save_record(
            "candidates",
            candidate.candidate_id,
            "ResearchCandidate",
            candidate,
        )

    def load_candidate(self, candidate_id: str) -> ResearchCandidate:
        candidate = self._load_record(
            "candidates",
            candidate_id,
            "ResearchCandidate",
            ResearchCandidate.from_dict,
        )
        current = candidate
        for decision in self.list_decisions(candidate_id=candidate.candidate_id):
            if decision.from_status is not current.status:
                raise ResearchStoreError(
                    f"Decision history for {candidate.candidate_id} is discontinuous at "
                    f"{decision.decision_id}."
                )
            if decision.decision is DecisionKind.HOLD:
                continue
            try:
                require_transition_allowed(current.status, decision.to_status)
            except ResearchContractError as exc:
                raise ResearchStoreError(
                    f"Stored invalid candidate transition in {decision.decision_id}: {exc}"
                ) from exc
            current = replace(current, status=decision.to_status)
        return current

    def list_candidates(self) -> tuple[ResearchCandidate, ...]:
        return tuple(
            self.load_candidate(record_id)
            for record_id in self._list_record_ids("candidates")
        )

    def save_run(self, run: ResearchRun) -> None:
        self._save_record("runs", run.research_run_id, "ResearchRun", run)

    def load_run(self, research_run_id: str) -> ResearchRun:
        return self._load_record(
            "runs", research_run_id, "ResearchRun", ResearchRun.from_dict
        )

    def list_runs(self) -> tuple[ResearchRun, ...]:
        return tuple(
            self.load_run(record_id) for record_id in self._list_record_ids("runs")
        )

    def save_selection(self, selection: SelectionRecord) -> None:
        self._require_run(selection.research_run_id)
        self._save_record(
            "selections",
            selection.selection_id,
            "SelectionRecord",
            selection,
        )

    def load_selection(self, selection_id: str) -> SelectionRecord:
        return self._load_record(
            "selections",
            selection_id,
            "SelectionRecord",
            SelectionRecord.from_dict,
        )

    def list_selections(self) -> tuple[SelectionRecord, ...]:
        return tuple(
            self.load_selection(record_id)
            for record_id in self._list_record_ids("selections")
        )

    def save_evidence(self, evidence: EvidenceRecord) -> None:
        self._require_candidate(evidence.candidate_id)
        self._save_record(
            "evidence", evidence.evidence_id, "EvidenceRecord", evidence
        )

    def load_evidence(self, evidence_id: str) -> EvidenceRecord:
        return self._load_record(
            "evidence", evidence_id, "EvidenceRecord", EvidenceRecord.from_dict
        )

    def list_evidence(self, *, candidate_id: str | None = None) -> tuple[EvidenceRecord, ...]:
        records = tuple(
            self.load_evidence(record_id)
            for record_id in self._list_record_ids("evidence")
        )
        return self._filter_candidate(records, candidate_id)

    def save_validation(self, validation: CanonicalValidationRecord) -> None:
        self._require_candidate(validation.candidate_id)
        self._save_record(
            "validations",
            validation.validation_id,
            "CanonicalValidationRecord",
            validation,
        )

    def load_validation(self, validation_id: str) -> CanonicalValidationRecord:
        return self._load_record(
            "validations",
            validation_id,
            "CanonicalValidationRecord",
            CanonicalValidationRecord.from_dict,
        )

    def list_validations(
        self, *, candidate_id: str | None = None
    ) -> tuple[CanonicalValidationRecord, ...]:
        records = tuple(
            self.load_validation(record_id)
            for record_id in self._list_record_ids("validations")
        )
        return self._filter_candidate(records, candidate_id)

    def save_robustness(self, robustness: RobustnessRecord) -> None:
        self._require_candidate(robustness.candidate_id)
        validation = self.load_validation(robustness.validation_id)
        if validation.candidate_id != robustness.candidate_id:
            raise ResearchStoreError(
                "RobustnessRecord validation belongs to a different candidate."
            )
        self._save_record(
            "robustness",
            robustness.robustness_id,
            "RobustnessRecord",
            robustness,
        )

    def load_robustness(self, robustness_id: str) -> RobustnessRecord:
        return self._load_record(
            "robustness",
            robustness_id,
            "RobustnessRecord",
            RobustnessRecord.from_dict,
        )

    def list_robustness(
        self, *, candidate_id: str | None = None
    ) -> tuple[RobustnessRecord, ...]:
        records = tuple(
            self.load_robustness(record_id)
            for record_id in self._list_record_ids("robustness")
        )
        return self._filter_candidate(records, candidate_id)

    def save_decision(
        self,
        decision: PromotionDecision,
        *,
        policy: MinimumEvidencePolicy | None = None,
        current_specification_hash: str | None = None,
        material_changes_after_final: tuple[str, ...] = (),
    ) -> None:
        if not isinstance(decision, PromotionDecision):
            raise ResearchStoreError("decision must be a PromotionDecision.")
        candidate = self.load_candidate(decision.candidate_id)
        if decision.from_status is not candidate.status:
            raise ResearchStoreError(
                "Decision from_status does not match the stored candidate status."
            )
        previous = self.list_decisions(candidate_id=decision.candidate_id)
        if previous and self._decision_sort_key(decision) <= self._decision_sort_key(
            previous[-1]
        ):
            raise ResearchStoreError(
                "Decision timestamps/ids must advance monotonically for one candidate."
            )
        validations = self.list_validations(candidate_id=decision.candidate_id)
        robustness_records = self.list_robustness(candidate_id=decision.candidate_id)
        evidence_records = self.list_evidence(candidate_id=decision.candidate_id)
        referenced_hashes = {
            record.specification_hash
            for record in (*validations, *evidence_records)
            if self._record_identifier(record) in decision.evidence_references
        }
        if len(referenced_hashes) > 1:
            raise ResearchStoreError(
                "Decision references records from different specification hashes."
            )
        if (
            current_specification_hash is not None
            and referenced_hashes
            and current_specification_hash not in referenced_hashes
        ):
            raise ResearchStoreError(
                "current_specification_hash differs from decision-linked evidence."
            )
        resolved_specification_hash = current_specification_hash
        if resolved_specification_hash is None and referenced_hashes:
            resolved_specification_hash = next(iter(referenced_hashes))
        try:
            apply_promotion_decision(
                candidate,
                decision,
                policy=policy or MinimumEvidencePolicy(),
                validations=validations,
                robustness_records=robustness_records,
                evidence_records=evidence_records,
                current_specification_hash=resolved_specification_hash,
                material_changes_after_final=material_changes_after_final,
            )
        except ResearchContractError as exc:
            raise ResearchStoreError(
                f"Decision failed the evidence-gated lifecycle: {exc}"
            ) from exc
        self._save_record(
            "decisions",
            decision.decision_id,
            "PromotionDecision",
            decision,
        )

    def load_decision(self, decision_id: str) -> PromotionDecision:
        return self._load_record(
            "decisions",
            decision_id,
            "PromotionDecision",
            PromotionDecision.from_dict,
        )

    def list_decisions(
        self, *, candidate_id: str | None = None
    ) -> tuple[PromotionDecision, ...]:
        records = tuple(
            self.load_decision(record_id)
            for record_id in self._list_record_ids("decisions")
        )
        filtered = self._filter_candidate(records, candidate_id)
        return tuple(sorted(filtered, key=self._decision_sort_key))

    def _save_record(
        self,
        collection: str,
        record_id: str,
        record_type: str,
        record: Any,
    ) -> None:
        path = self._record_path(collection, record_id)
        envelope = {
            "record": record.to_dict(),
            "record_type": record_type,
            "schema_version": self.schema_version,
        }
        rendered = deterministic_json_dumps(envelope, trailing_newline=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{record_id}.", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(rendered)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                raise ResearchStoreError(
                    f"Immutable research record already exists: {path}"
                ) from exc
        finally:
            temporary.unlink(missing_ok=True)

    def _load_record(
        self,
        collection: str,
        record_id: str,
        record_type: str,
        parser: Callable[[dict[str, Any]], RecordT],
    ) -> RecordT:
        path = self._record_path(collection, record_id)
        if not path.is_file():
            raise ResearchStoreError(f"Unknown {record_type} id {record_id!r}.")
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(envelope, dict) or set(envelope) != {
                "record",
                "record_type",
                "schema_version",
            }:
                raise ResearchStoreError("Invalid research-record envelope.")
            if envelope["schema_version"] != self.schema_version:
                raise ResearchStoreError("Unsupported research-store schema version.")
            if envelope["record_type"] != record_type:
                raise ResearchStoreError(
                    f"Expected {record_type}, found {envelope['record_type']!r}."
                )
            record = parser(envelope["record"])
            actual_id = self._record_identifier(record)
            if actual_id != record_id:
                raise ResearchStoreError(
                    f"Record id {actual_id!r} does not match filename {record_id!r}."
                )
            canonical = deterministic_json_dumps(envelope, trailing_newline=True)
            if canonical != path.read_text(encoding="utf-8"):
                raise ResearchStoreError(
                    "Research record is not in canonical deterministic JSON form."
                )
            return record
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ResearchStoreError):
                raise
            raise ResearchStoreError(f"Invalid research record at {path}: {exc}") from exc

    def _record_path(self, collection: str, record_id: str) -> Path:
        if collection not in _COLLECTIONS:
            raise ResearchStoreError(f"Unknown research collection {collection!r}.")
        try:
            safe_id = _require_identifier(record_id, field_name=f"{collection} id")
        except ResearchContractError as exc:
            raise ResearchStoreError(str(exc)) from exc
        return self.root / collection / f"{safe_id}.json"

    def _list_record_ids(self, collection: str) -> tuple[str, ...]:
        directory = self.root / collection
        if not directory.is_dir():
            return ()
        return tuple(path.stem for path in sorted(directory.glob("*.json")))

    def _require_candidate(self, candidate_id: str) -> None:
        self.load_candidate(candidate_id)

    def _require_run(self, research_run_id: str) -> None:
        self.load_run(research_run_id)

    @staticmethod
    def _record_identifier(record: Any) -> str:
        primary_id_fields = (
            (PromotionDecision, "decision_id"),
            (RobustnessRecord, "robustness_id"),
            (CanonicalValidationRecord, "validation_id"),
            (EvidenceRecord, "evidence_id"),
            (SelectionRecord, "selection_id"),
            (ResearchRun, "research_run_id"),
            (ResearchCandidate, "candidate_id"),
        )
        for record_class, field_name in primary_id_fields:
            if isinstance(record, record_class):
                return getattr(record, field_name)
        raise ResearchStoreError(f"Unsupported record type {type(record).__name__}.")

    @staticmethod
    def _filter_candidate(
        records: tuple[RecordT, ...],
        candidate_id: str | None,
    ) -> tuple[RecordT, ...]:
        if candidate_id is None:
            return records
        try:
            normalized = _require_identifier(candidate_id, field_name="candidate_id")
        except ResearchContractError as exc:
            raise ResearchStoreError(str(exc)) from exc
        return tuple(
            item for item in records if getattr(item, "candidate_id", None) == normalized
        )

    @staticmethod
    def _decision_sort_key(decision: PromotionDecision) -> tuple[datetime, str]:
        parsed = datetime.fromisoformat(decision.decided_at.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc), decision.decision_id


__all__ = ["FilesystemResearchStore", "ResearchStoreError"]
