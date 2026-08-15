"""Strict deterministic JSON serialization for research metadata."""

from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any, Protocol

from .contracts import ResearchContractError, _require_json_compatible


class SerializableResearchRecord(Protocol):
    def to_dict(self) -> dict[str, Any]: ...


def deterministic_json_dumps(
    value: Mapping[str, Any] | SerializableResearchRecord,
    *,
    trailing_newline: bool = False,
) -> str:
    """Serialize without fallback coercions that could leak backend objects."""

    payload = value.to_dict() if hasattr(value, "to_dict") else dict(value)
    if not isinstance(payload, Mapping):
        raise ResearchContractError("Research serialization requires a JSON object.")
    _require_json_compatible(payload, field_name="research_record")
    rendered = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return rendered + ("\n" if trailing_newline else "")


def deterministic_json_loads(payload: str) -> dict[str, Any]:
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ResearchContractError(f"Invalid research JSON: {exc}") from exc
    if not isinstance(decoded, dict):
        raise ResearchContractError("Research JSON must contain an object.")
    _require_json_compatible(decoded, field_name="research_record")
    return decoded


__all__ = ["deterministic_json_dumps", "deterministic_json_loads"]
