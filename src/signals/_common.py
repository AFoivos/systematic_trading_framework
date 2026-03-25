from __future__ import annotations


ALLOWED_DIRECTIONAL_MODES = frozenset(
    {"long_only", "short_only", "long_short", "long_short_hold"}
)


def resolve_signal_output_name(
    *,
    signal_col: str | None,
    default: str,
) -> str:
    return str(signal_col or default)


__all__ = [
    "ALLOWED_DIRECTIONAL_MODES",
    "resolve_signal_output_name",
]
