"""Neutral robustness checks and evidence-completeness policy."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Any

from .contracts import (
    ResearchContractError,
    _freeze_json_mapping,
    _require_exact_keys,
    _require_identifier,
    _require_json_array,
    _require_non_empty,
    _require_timestamp,
    _require_unique_strings,
)
from .evidence import CheckStatus


def _optional_finite(value: int | float | None, *, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(
        float(value)
    ):
        raise ResearchContractError(f"{field_name} must be finite or null.")
    return float(value)


@dataclass(frozen=True)
class RobustnessCheck:
    name: str
    status: CheckStatus
    baseline_metric: int | float | None = None
    stressed_metric: int | float | None = None
    threshold: int | float | None = None
    details: Mapping[str, Any] = field(default_factory=dict)
    artifact_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "name",
            _require_non_empty(self.name, field_name="name"),
        )
        try:
            status = CheckStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise ResearchContractError(str(exc)) from exc
        object.__setattr__(self, "status", status)
        for field_name in ("baseline_metric", "stressed_metric", "threshold"):
            object.__setattr__(
                self,
                field_name,
                _optional_finite(getattr(self, field_name), field_name=field_name),
            )
        object.__setattr__(
            self,
            "details",
            _freeze_json_mapping(self.details, field_name="details"),
        )
        object.__setattr__(
            self,
            "artifact_references",
            _require_unique_strings(
                self.artifact_references,
                field_name="artifact_references",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "baseline_metric": self.baseline_metric,
            "stressed_metric": self.stressed_metric,
            "threshold": self.threshold,
            "details": dict(self.details),
            "artifact_references": list(self.artifact_references),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RobustnessCheck:
        expected = {
            "name",
            "status",
            "baseline_metric",
            "stressed_metric",
            "threshold",
            "details",
            "artifact_references",
        }
        _require_exact_keys(payload, expected=expected, field_name="Robustness check")
        return cls(
            name=payload["name"],
            status=CheckStatus(payload["status"]),
            baseline_metric=payload["baseline_metric"],
            stressed_metric=payload["stressed_metric"],
            threshold=payload["threshold"],
            details=payload["details"],
            artifact_references=tuple(
                _require_json_array(
                    payload["artifact_references"],
                    field_name="artifact_references",
                )
            ),
        )


@dataclass(frozen=True)
class RobustnessRecord:
    robustness_id: str
    candidate_id: str
    validation_id: str
    checks: tuple[RobustnessCheck, ...]
    status: CheckStatus
    recorded_at: str
    artifact_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("robustness_id", "candidate_id", "validation_id"):
            object.__setattr__(
                self,
                field_name,
                _require_identifier(getattr(self, field_name), field_name=field_name),
            )
        if isinstance(self.checks, (str, bytes, bytearray)):
            raise ResearchContractError("checks must be a sequence of RobustnessCheck.")
        checks = tuple(self.checks)
        if not checks or any(not isinstance(item, RobustnessCheck) for item in checks):
            raise ResearchContractError(
                "checks must contain at least one RobustnessCheck."
            )
        names = tuple(item.name for item in checks)
        if len(set(names)) != len(names):
            raise ResearchContractError("Robustness check names cannot be duplicated.")
        object.__setattr__(self, "checks", checks)
        try:
            status = CheckStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise ResearchContractError(str(exc)) from exc
        object.__setattr__(self, "status", status)
        check_statuses = {item.status for item in checks}
        if status is CheckStatus.PASS and check_statuses.intersection(
            {CheckStatus.FAIL, CheckStatus.NOT_RUN}
        ):
            raise ResearchContractError(
                "A passed robustness record cannot contain failed or not-run checks."
            )
        if status is CheckStatus.FAIL and CheckStatus.FAIL not in check_statuses:
            raise ResearchContractError(
                "A failed robustness record must contain a failed check."
            )
        if status is CheckStatus.NOT_RUN and check_statuses != {CheckStatus.NOT_RUN}:
            raise ResearchContractError(
                "A not-run robustness record may contain only not-run checks."
            )
        object.__setattr__(
            self,
            "recorded_at",
            _require_timestamp(self.recorded_at, field_name="recorded_at"),
        )
        object.__setattr__(
            self,
            "artifact_references",
            _require_unique_strings(
                self.artifact_references,
                field_name="artifact_references",
            ),
        )

    def check_by_name(self, name: str) -> RobustnessCheck | None:
        return next((item for item in self.checks if item.name == name), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "robustness_id": self.robustness_id,
            "candidate_id": self.candidate_id,
            "validation_id": self.validation_id,
            "checks": [item.to_dict() for item in self.checks],
            "status": self.status.value,
            "recorded_at": self.recorded_at,
            "artifact_references": list(self.artifact_references),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RobustnessRecord:
        expected = {
            "robustness_id",
            "candidate_id",
            "validation_id",
            "checks",
            "status",
            "recorded_at",
            "artifact_references",
        }
        _require_exact_keys(payload, expected=expected, field_name="Robustness record")
        return cls(
            robustness_id=payload["robustness_id"],
            candidate_id=payload["candidate_id"],
            validation_id=payload["validation_id"],
            checks=tuple(
                RobustnessCheck.from_dict(item)
                for item in _require_json_array(payload["checks"], field_name="checks")
            ),
            status=CheckStatus(payload["status"]),
            recorded_at=payload["recorded_at"],
            artifact_references=tuple(
                _require_json_array(
                    payload["artifact_references"],
                    field_name="artifact_references",
                )
            ),
        )


@dataclass(frozen=True)
class MinimumEvidencePolicy:
    """Configuration-driven completeness requirements, never financial cutoffs."""

    require_robustness: bool = True
    required_robustness_checks: tuple[str, ...] = ()
    require_final_holdout: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.require_robustness, bool) or not isinstance(
            self.require_final_holdout, bool
        ):
            raise ResearchContractError(
                "Evidence-policy requirement flags must be booleans."
            )
        checks = _require_unique_strings(
            self.required_robustness_checks,
            field_name="required_robustness_checks",
        )
        if checks and not self.require_robustness:
            raise ResearchContractError(
                "required_robustness_checks requires require_robustness=true."
            )
        object.__setattr__(self, "required_robustness_checks", checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "require_robustness": self.require_robustness,
            "required_robustness_checks": list(self.required_robustness_checks),
            "require_final_holdout": self.require_final_holdout,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> MinimumEvidencePolicy:
        expected = {
            "require_robustness",
            "required_robustness_checks",
            "require_final_holdout",
        }
        _require_exact_keys(
            payload,
            expected=expected,
            field_name="Minimum evidence policy",
        )
        return cls(
            require_robustness=payload["require_robustness"],
            required_robustness_checks=tuple(
                _require_json_array(
                    payload["required_robustness_checks"],
                    field_name="required_robustness_checks",
                )
            ),
            require_final_holdout=payload["require_final_holdout"],
        )


__all__ = [
    "MinimumEvidencePolicy",
    "RobustnessCheck",
    "RobustnessRecord",
]
