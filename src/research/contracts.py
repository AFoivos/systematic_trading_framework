"""Framework-owned contracts shared by future research backends."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from math import isfinite
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from src.src_data.research_roles import EvidenceRole

if TYPE_CHECKING:
    from .candidate import ResearchCandidate


class ResearchContractError(ValueError):
    """Raised when a backend-neutral research contract is invalid."""


class EvidenceStage(str, Enum):
    """User-facing research stages mapped onto the existing evidence roles."""

    DEVELOPMENT = "development"
    VALIDATION = "validation"
    FINAL_HOLDOUT = "final_holdout"


EVIDENCE_ROLE_BY_STAGE: Mapping[EvidenceStage, EvidenceRole] = MappingProxyType(
    {
        EvidenceStage.DEVELOPMENT: EvidenceRole.DISCOVERY,
        EvidenceStage.VALIDATION: EvidenceRole.VALIDATION,
        EvidenceStage.FINAL_HOLDOUT: EvidenceRole.PROSPECTIVE_FINAL,
    }
)


def _require_non_empty(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResearchContractError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _require_identifier(value: object, *, field_name: str) -> str:
    identifier = _require_non_empty(value, field_name=field_name)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}", identifier):
        raise ResearchContractError(
            f"{field_name} must contain only letters, digits, '.', '_', ':', or '-'."
        )
    return identifier


def _require_sha256(value: object, *, field_name: str) -> str:
    digest = _require_non_empty(value, field_name=field_name)
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ResearchContractError(
            f"{field_name} must be a lowercase 64-character SHA-256."
        )
    return digest


def _require_timestamp(value: object, *, field_name: str) -> str:
    timestamp = _require_non_empty(value, field_name=field_name)
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResearchContractError(f"{field_name} must be ISO-8601.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ResearchContractError(f"{field_name} must include a timezone.")
    return timestamp


def _require_exact_keys(
    payload: Mapping[str, Any],
    *,
    expected: set[str],
    field_name: str,
    optional: set[str] | None = None,
) -> None:
    if not isinstance(payload, Mapping):
        raise ResearchContractError(f"{field_name} must be a mapping.")
    optional_keys = optional or set()
    missing = sorted(expected.difference(payload))
    unexpected = sorted(set(payload).difference(expected | optional_keys))
    if missing or unexpected:
        raise ResearchContractError(
            f"{field_name} keys mismatch; missing={missing}, unexpected={unexpected}."
        )


def _require_unique_strings(
    values: Sequence[str],
    *,
    field_name: str,
    allow_empty: bool = True,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, bytearray)):
        raise ResearchContractError(f"{field_name} must be a sequence of strings.")
    normalized = tuple(
        _require_non_empty(item, field_name=f"{field_name} item") for item in values
    )
    if not allow_empty and not normalized:
        raise ResearchContractError(f"{field_name} cannot be empty.")
    if len(set(normalized)) != len(normalized):
        raise ResearchContractError(f"{field_name} cannot contain duplicates.")
    return normalized


def _require_json_array(value: object, *, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ResearchContractError(f"{field_name} must be a JSON array.")
    return value


def _require_json_compatible(value: Any, *, field_name: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not isfinite(value):
            raise ResearchContractError(f"{field_name} cannot contain NaN or infinity.")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _require_non_empty(key, field_name=f"{field_name} key")
            _require_json_compatible(item, field_name=f"{field_name}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _require_json_compatible(item, field_name=f"{field_name}[{index}]")
        return
    raise ResearchContractError(
        f"{field_name} must contain only JSON-compatible values, not {type(value).__name__}."
    )


def _freeze_json_mapping(value: Mapping[str, Any], *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ResearchContractError(f"{field_name} must be a mapping.")
    copied = deepcopy(dict(value))
    _require_json_compatible(copied, field_name=field_name)
    return MappingProxyType(copied)


@dataclass(frozen=True)
class EvidenceReference:
    """Reference to evidence whose immutable role matches its research stage.

    Historical pseudo-OOS data intentionally has no stage mapping: existing
    inspected history may remain useful diagnostics, but it cannot be relabeled
    as final holdout evidence.
    """

    stage: EvidenceStage
    evidence_role: EvidenceRole
    artifact_reference: str
    sample_reference: str

    def __post_init__(self) -> None:
        try:
            stage = EvidenceStage(self.stage)
            role = EvidenceRole(self.evidence_role)
        except (TypeError, ValueError) as exc:
            raise ResearchContractError(str(exc)) from exc
        expected_role = EVIDENCE_ROLE_BY_STAGE[stage]
        if role is not expected_role:
            raise ResearchContractError(
                f"Evidence stage {stage.value!r} requires role {expected_role.value!r}, "
                f"not {role.value!r}."
            )
        object.__setattr__(self, "stage", stage)
        object.__setattr__(self, "evidence_role", role)
        object.__setattr__(
            self,
            "artifact_reference",
            _require_non_empty(self.artifact_reference, field_name="artifact_reference"),
        )
        object.__setattr__(
            self,
            "sample_reference",
            _require_non_empty(self.sample_reference, field_name="sample_reference"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "stage": self.stage.value,
            "evidence_role": self.evidence_role.value,
            "artifact_reference": self.artifact_reference,
            "sample_reference": self.sample_reference,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> EvidenceReference:
        _require_exact_keys(
            payload,
            expected={
                "stage",
                "evidence_role",
                "artifact_reference",
                "sample_reference",
            },
            field_name="Evidence reference",
        )
        return cls(
            stage=EvidenceStage(payload["stage"]),
            evidence_role=EvidenceRole(payload["evidence_role"]),
            artifact_reference=payload["artifact_reference"],
            sample_reference=payload["sample_reference"],
        )


@dataclass(frozen=True)
class ResearchRequest:
    """Portable input to a screening backend.

    ``config_reference`` identifies framework-owned configuration or a frozen
    artifact. ``parameters`` must remain serializable and must not contain
    backend-native runtime objects.
    """

    request_id: str
    config_reference: str
    assets: tuple[str, ...]
    timeframe: str
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _require_non_empty(self.request_id, field_name="request_id")
        )
        object.__setattr__(
            self,
            "config_reference",
            _require_non_empty(self.config_reference, field_name="config_reference"),
        )
        if isinstance(self.assets, (str, bytes, bytearray)):
            raise ResearchContractError("assets must be a sequence of asset identifiers.")
        assets = tuple(
            _require_non_empty(item, field_name="assets item") for item in self.assets
        )
        if not assets:
            raise ResearchContractError("assets must contain at least one asset.")
        if len(set(assets)) != len(assets):
            raise ResearchContractError("assets cannot contain duplicates.")
        object.__setattr__(self, "assets", assets)
        object.__setattr__(
            self, "timeframe", _require_non_empty(self.timeframe, field_name="timeframe")
        )
        object.__setattr__(
            self,
            "parameters",
            _freeze_json_mapping(self.parameters, field_name="parameters"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "config_reference": self.config_reference,
            "assets": list(self.assets),
            "timeframe": self.timeframe,
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ResearchRequest:
        _require_exact_keys(
            payload,
            expected={
                "request_id",
                "config_reference",
                "assets",
                "timeframe",
                "parameters",
            },
            field_name="Research request",
        )
        return cls(
            request_id=payload["request_id"],
            config_reference=payload["config_reference"],
            assets=tuple(_require_json_array(payload["assets"], field_name="assets")),
            timeframe=payload["timeframe"],
            parameters=payload["parameters"],
        )


@dataclass(frozen=True)
class ResearchResult:
    """Portable backend output; never final evidence by itself."""

    request_id: str
    backend: str
    candidates: tuple[ResearchCandidate, ...] = ()
    artifact_references: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        from .candidate import ResearchCandidate

        request_id = _require_non_empty(self.request_id, field_name="request_id")
        backend = _require_non_empty(self.backend, field_name="backend")
        if isinstance(self.candidates, (str, bytes, bytearray)):
            raise ResearchContractError("candidates must be a sequence of candidates.")
        candidates = tuple(self.candidates)
        for candidate in candidates:
            if not isinstance(candidate, ResearchCandidate):
                raise ResearchContractError(
                    "candidates must contain only ResearchCandidate values."
                )
            if candidate.backend != backend:
                raise ResearchContractError(
                    f"Candidate backend {candidate.backend!r} does not match result backend "
                    f"{backend!r}."
                )
        candidate_ids = tuple(candidate.candidate_id for candidate in candidates)
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ResearchContractError(
                "ResearchResult candidates cannot contain duplicate candidate_id values."
            )
        if isinstance(self.artifact_references, (str, bytes, bytearray)):
            raise ResearchContractError(
                "artifact_references must be a sequence of artifact identifiers."
            )
        artifact_references = tuple(
            _require_non_empty(item, field_name="artifact_references item")
            for item in self.artifact_references
        )
        if len(set(artifact_references)) != len(artifact_references):
            raise ResearchContractError("artifact_references cannot contain duplicates.")
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "backend", backend)
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "artifact_references", artifact_references)
        object.__setattr__(
            self,
            "metadata",
            _freeze_json_mapping(self.metadata, field_name="metadata"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "backend": self.backend,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "artifact_references": list(self.artifact_references),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ResearchResult:
        from .candidate import ResearchCandidate

        _require_exact_keys(
            payload,
            expected={
                "request_id",
                "backend",
                "candidates",
                "artifact_references",
                "metadata",
            },
            field_name="Research result",
        )
        return cls(
            request_id=payload["request_id"],
            backend=payload["backend"],
            candidates=tuple(
                ResearchCandidate.from_dict(item)
                for item in _require_json_array(
                    payload["candidates"], field_name="candidates"
                )
            ),
            artifact_references=tuple(
                _require_json_array(
                    payload["artifact_references"],
                    field_name="artifact_references",
                )
            ),
            metadata=payload["metadata"],
        )


__all__ = [
    "EVIDENCE_ROLE_BY_STAGE",
    "EvidenceReference",
    "EvidenceStage",
    "ResearchContractError",
    "ResearchRequest",
    "ResearchResult",
]
