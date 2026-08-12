from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any, Iterable

from src.src_data.research_roles import (
    EvidenceRole,
    LegacyDataClassification,
    SourceClassification,
    evidence_role_schema,
    require_role_transition_allowed,
)


class ResearchContractError(ValueError):
    """Raised when an alpha-research integrity contract is violated."""


class MaterialSpecificationChange(str, Enum):
    FEATURE_DEFINITIONS = "FEATURE_DEFINITIONS"
    FEATURE_WINDOWS = "FEATURE_WINDOWS"
    BINS = "BINS"
    HORIZONS = "HORIZONS"
    COSTS = "COSTS"
    HYPOTHESIS_CONDITIONS = "HYPOTHESIS_CONDITIONS"
    PROMOTION_GATES = "PROMOTION_GATES"
    EXECUTION_SEMANTICS = "EXECUTION_SEMANTICS"


class BarEvent(IntEnum):
    """Causal event order within one bar."""

    OPEN = 0
    CLOSE = 1

    @classmethod
    def from_value(cls, value: str | BarEvent) -> BarEvent:
        if isinstance(value, cls):
            return value
        try:
            return cls[str(value).strip().upper()]
        except KeyError as exc:
            allowed = ", ".join(item.name for item in cls)
            raise ResearchContractError(
                f"Unknown bar event {value!r}; expected one of: {allowed}."
            ) from exc


@dataclass(frozen=True, order=True)
class AvailableAt:
    """Point-in-time availability relative to the feature's reference bar.

    ``AvailableAt(0, CLOSE)`` means close[t]. ``AvailableAt(1, OPEN)`` means
    open[t+1]. Ordering follows time: open[t] < close[t] < open[t+1].
    """

    bar_offset: int
    event: BarEvent

    def __post_init__(self) -> None:
        if isinstance(self.bar_offset, bool) or not isinstance(self.bar_offset, int):
            raise ResearchContractError("available_at.bar_offset must be an integer.")
        if self.bar_offset < 0:
            raise ResearchContractError("available_at.bar_offset must be >= 0.")
        object.__setattr__(self, "event", BarEvent.from_value(self.event))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AvailableAt:
        if not isinstance(payload, dict):
            raise ResearchContractError("available_at must be a mapping.")
        unexpected = sorted(set(payload).difference({"bar_offset", "event"}))
        if unexpected:
            raise ResearchContractError(f"Unexpected available_at keys: {unexpected}.")
        if "bar_offset" not in payload or "event" not in payload:
            raise ResearchContractError("available_at requires bar_offset and event.")
        return cls(
            bar_offset=payload["bar_offset"],
            event=BarEvent.from_value(payload["event"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"bar_offset": self.bar_offset, "event": self.event.name}

    def is_available_by(self, consumption_time: AvailableAt) -> bool:
        return _available_at_sort_key(self) <= _available_at_sort_key(consumption_time)

    def require_available_by(
        self,
        consumption_time: AvailableAt,
        *,
        feature_name: str,
    ) -> None:
        if not self.is_available_by(consumption_time):
            raise ResearchContractError(
                f"Feature '{feature_name}' is available at {self.to_dict()} but "
                f"would be consumed at {consumption_time.to_dict()}."
            )


def _available_at_sort_key(value: AvailableAt) -> tuple[int, int]:
    return value.bar_offset, int(value.event)


@dataclass(frozen=True)
class FeatureAvailability:
    name: str
    available_at: AvailableAt

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ResearchContractError("Feature name must be a non-empty string.")
        if not isinstance(self.available_at, AvailableAt):
            raise ResearchContractError(
                "Feature available_at must be an AvailableAt value."
            )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> FeatureAvailability:
        if not isinstance(payload, dict):
            raise ResearchContractError("Feature availability must be a mapping.")
        unexpected = sorted(set(payload).difference({"name", "available_at"}))
        if unexpected:
            raise ResearchContractError(
                f"Unexpected feature availability keys: {unexpected}."
            )
        if "name" not in payload or "available_at" not in payload:
            raise ResearchContractError(
                "Feature availability requires name and available_at."
            )
        return cls(
            name=payload["name"],
            available_at=AvailableAt.from_dict(payload["available_at"]),
        )

    def require_consumable_at(self, consumption_time: AvailableAt) -> None:
        self.available_at.require_available_by(
            consumption_time,
            feature_name=self.name,
        )


def validation_is_contaminated_after_change(
    *,
    validation_results_viewed: bool,
    changed_fields: Iterable[MaterialSpecificationChange | str],
) -> bool:
    changes = tuple(MaterialSpecificationChange(item) for item in changed_fields)
    return bool(validation_results_viewed and changes)


def prospective_clock_must_restart(
    changed_fields: Iterable[MaterialSpecificationChange | str],
) -> bool:
    return bool(tuple(MaterialSpecificationChange(item) for item in changed_fields))


def available_at_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Point-in-time availability",
        "type": "object",
        "additionalProperties": False,
        "required": ["bar_offset", "event"],
        "properties": {
            "bar_offset": {"type": "integer", "minimum": 0},
            "event": {"type": "string", "enum": [event.name for event in BarEvent]},
        },
    }


__all__ = [
    "AvailableAt",
    "BarEvent",
    "EvidenceRole",
    "FeatureAvailability",
    "LegacyDataClassification",
    "MaterialSpecificationChange",
    "ResearchContractError",
    "SourceClassification",
    "available_at_schema",
    "evidence_role_schema",
    "prospective_clock_must_restart",
    "require_role_transition_allowed",
    "validation_is_contaminated_after_change",
]
