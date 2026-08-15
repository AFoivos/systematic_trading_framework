"""Portable, preregisterable research-hypothesis metadata."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .contracts import (
    ResearchContractError,
    _require_exact_keys,
    _require_identifier,
    _require_json_array,
    _require_non_empty,
    _require_timestamp,
    _require_unique_strings,
)


@dataclass(frozen=True)
class ResearchHypothesis:
    """Backend-neutral statement recorded before result inspection.

    The append-only alpha-specific status/version history remains owned by
    :class:`src.experiments.alpha_registry.HypothesisRegistry`. This value is
    the portable definition referenced by a ``ResearchRun``; it is not a
    second lifecycle registry.
    """

    hypothesis_id: str
    name: str
    thesis: str
    assets: tuple[str, ...]
    created_at: str
    timeframe: str | None = None
    tags: tuple[str, ...] = ()
    feature_families: tuple[str, ...] = ()
    target_kind: str | None = None
    signal_family: str | None = None
    expected_mechanism: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "hypothesis_id",
            _require_identifier(self.hypothesis_id, field_name="hypothesis_id"),
        )
        for field_name in ("name", "thesis"):
            object.__setattr__(
                self,
                field_name,
                _require_non_empty(getattr(self, field_name), field_name=field_name),
            )
        object.__setattr__(
            self,
            "assets",
            _require_unique_strings(
                self.assets,
                field_name="assets",
                allow_empty=False,
            ),
        )
        object.__setattr__(
            self,
            "created_at",
            _require_timestamp(self.created_at, field_name="created_at"),
        )
        if self.timeframe is not None:
            object.__setattr__(
                self,
                "timeframe",
                _require_non_empty(self.timeframe, field_name="timeframe"),
            )
        object.__setattr__(
            self,
            "tags",
            _require_unique_strings(self.tags, field_name="tags"),
        )
        object.__setattr__(
            self,
            "feature_families",
            _require_unique_strings(
                self.feature_families,
                field_name="feature_families",
            ),
        )
        for field_name in ("target_kind", "signal_family", "expected_mechanism"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    _require_non_empty(value, field_name=field_name),
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "name": self.name,
            "thesis": self.thesis,
            "assets": list(self.assets),
            "created_at": self.created_at,
            "timeframe": self.timeframe,
            "tags": list(self.tags),
            "feature_families": list(self.feature_families),
            "target_kind": self.target_kind,
            "signal_family": self.signal_family,
            "expected_mechanism": self.expected_mechanism,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ResearchHypothesis:
        expected = {
            "hypothesis_id",
            "name",
            "thesis",
            "assets",
            "created_at",
            "timeframe",
            "tags",
            "feature_families",
            "target_kind",
            "signal_family",
            "expected_mechanism",
        }
        _require_exact_keys(
            payload,
            expected=expected,
            field_name="Research hypothesis",
        )
        try:
            return cls(
                hypothesis_id=payload["hypothesis_id"],
                name=payload["name"],
                thesis=payload["thesis"],
                assets=tuple(_require_json_array(payload["assets"], field_name="assets")),
                created_at=payload["created_at"],
                timeframe=payload["timeframe"],
                tags=tuple(_require_json_array(payload["tags"], field_name="tags")),
                feature_families=tuple(
                    _require_json_array(
                        payload["feature_families"],
                        field_name="feature_families",
                    )
                ),
                target_kind=payload["target_kind"],
                signal_family=payload["signal_family"],
                expected_mechanism=payload["expected_mechanism"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ResearchContractError):
                raise
            raise ResearchContractError(f"Invalid research hypothesis: {exc}") from exc


__all__ = ["ResearchHypothesis"]
