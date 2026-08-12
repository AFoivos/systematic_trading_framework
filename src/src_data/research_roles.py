from __future__ import annotations

from enum import Enum
from typing import Any


class ResearchRoleError(ValueError):
    """Raised when an immutable evidence-role contract is violated."""


class EvidenceRole(str, Enum):
    """Immutable scientific role assigned to one research snapshot."""

    DISCOVERY = "DISCOVERY"
    VALIDATION = "VALIDATION"
    HISTORICAL_PSEUDO_OOS = "HISTORICAL_PSEUDO_OOS"
    PROSPECTIVE_FINAL = "PROSPECTIVE_FINAL"


class SourceClassification(str, Enum):
    """Origin classification used by the processed-data quarantine."""

    VALIDATED_MARKET_DATA = "VALIDATED_MARKET_DATA"
    PROCESSED_EXPERIMENT_ARTIFACT = "PROCESSED_EXPERIMENT_ARTIFACT"
    LEGACY_MARKET_DATA = "LEGACY_MARKET_DATA"
    UNKNOWN = "UNKNOWN"


class LegacyDataClassification(str, Enum):
    VALID = "VALID"
    REGENERATE_REQUIRED = "REGENERATE_REQUIRED"
    LEGACY_AMBIGUOUS_UNITS = "LEGACY_AMBIGUOUS_UNITS"
    NOT_RESEARCH_SOURCE = "NOT_RESEARCH_SOURCE"


def require_role_transition_allowed(
    current: EvidenceRole | str,
    requested: EvidenceRole | str,
) -> None:
    """Forbid relabeling; a different role requires a separately frozen snapshot."""

    current_role = EvidenceRole(current)
    requested_role = EvidenceRole(requested)
    if current_role is not requested_role:
        raise ResearchRoleError(
            f"Evidence role is immutable: {current_role.value} cannot become "
            f"{requested_role.value}. Use a separately sourced data partition and "
            "freeze it under the intended role instead."
        )


def evidence_role_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Alpha Research Evidence Role",
        "type": "string",
        "enum": [role.value for role in EvidenceRole],
        "x-role-rules": {
            EvidenceRole.DISCOVERY.value: "hypothesis discovery and fitted exploratory state",
            EvidenceRole.VALIDATION.value: "frozen-hypothesis validation only",
            EvidenceRole.HISTORICAL_PSEUDO_OOS.value: "inspected historical diagnostics; never FINAL",
            EvidenceRole.PROSPECTIVE_FINAL.value: "post-freeze data with separate explicit access",
        },
    }


__all__ = [
    "EvidenceRole",
    "LegacyDataClassification",
    "ResearchRoleError",
    "SourceClassification",
    "evidence_role_schema",
    "require_role_transition_allowed",
]
