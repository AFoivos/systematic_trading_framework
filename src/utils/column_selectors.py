from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any


COLUMN_SELECTOR_OPERATORS = {"exact", "startswith", "endswith", "contains", "regex"}


def _as_non_empty_string_list(value: Any, *, field: str) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        values = list(value)
    else:
        raise TypeError(f"{field} must be a non-empty string or list[str].")

    out: list[str] = []
    for idx, raw in enumerate(values):
        if not isinstance(raw, str) or not raw.strip():
            raise TypeError(f"{field}[{idx}] must be a non-empty string.")
        out.append(raw)
    if not out:
        raise ValueError(f"{field} must not be empty.")
    return out


def match_column_selector(
    columns: Sequence[str],
    *,
    operator: str,
    values: Sequence[str],
) -> list[str]:
    if operator == "exact":
        return [col for col in values if col in columns]
    if operator == "startswith":
        return [col for col in columns if any(col.startswith(prefix) for prefix in values)]
    if operator == "endswith":
        return [col for col in columns if any(col.endswith(suffix) for suffix in values)]
    if operator == "contains":
        return [col for col in columns if any(token in col for token in values)]
    if operator == "regex":
        patterns = [re.compile(pattern) for pattern in values]
        return [col for col in columns if any(pattern.search(col) for pattern in patterns)]
    raise ValueError(f"Unsupported column selector operator: {operator}")


def resolve_single_column_selector(
    columns: Sequence[str],
    selector: Mapping[str, Any],
    *,
    field: str,
) -> str:
    """
    Resolve a selector that must point to exactly one already-computed column.

    This is intentionally strict. Feature-window tuning can change output column names; resolving
    selectors after feature computation keeps configs stable while preventing ambiguous matches.
    """
    if not isinstance(selector, Mapping):
        raise TypeError(f"{field} must be a selector mapping.")
    if len(selector) != 1:
        allowed = ", ".join(sorted(COLUMN_SELECTOR_OPERATORS))
        raise ValueError(f"{field} must contain exactly one selector operator: {allowed}.")

    operator, raw_value = next(iter(selector.items()))
    if operator not in COLUMN_SELECTOR_OPERATORS:
        allowed = ", ".join(sorted(COLUMN_SELECTOR_OPERATORS))
        raise ValueError(f"{field}.{operator} is not supported. Allowed operators: {allowed}.")

    values = _as_non_empty_string_list(raw_value, field=f"{field}.{operator}")
    matches = match_column_selector([str(col) for col in columns], operator=str(operator), values=values)
    if not matches:
        raise KeyError(f"{field} matched no columns.")
    if len(matches) != 1:
        raise ValueError(f"{field} must match exactly one column, got {matches}.")
    return matches[0]


__all__ = [
    "COLUMN_SELECTOR_OPERATORS",
    "match_column_selector",
    "resolve_single_column_selector",
]
