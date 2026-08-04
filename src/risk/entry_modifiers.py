from __future__ import annotations

import re
from typing import Any, Mapping

import numpy as np
import pandas as pd


_RULE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_ALLOWED_KINDS = {"column_range", "local_hour", "previous_stop"}
_ALLOWED_SIDES = {"both", "long", "short"}
_ALLOWED_COMBINE = {"min", "multiply"}


def _finite_multiplier(value: object, *, field: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite number in [0, 1].") from exc
    if not np.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{field} must be a finite number in [0, 1].")
    return numeric


def _is_stop_exit_reason(reason: object) -> bool:
    normalized = str(reason or "").strip().lower()
    return bool(
        normalized in {"stop", "stop_loss", "same_bar_stop"}
        or normalized.endswith("_stop")
        or "stop_first" in normalized
    )


def normalize_entry_risk_modifiers(config: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate and normalize causal entry-risk modifier rules.

    The rules only inspect information available at the signal timestamp plus the
    exit reason of the last *completed* trade. They can reduce or reject a new
    entry, but they can never increase configured risk.
    """
    raw = dict(config or {})
    enabled = bool(raw.get("enabled", False))
    combine = str(raw.get("combine", "min") or "min").strip().lower()
    if combine not in _ALLOWED_COMBINE:
        raise ValueError(f"entry_risk_modifiers.combine must be one of {sorted(_ALLOWED_COMBINE)}.")
    raw_rules = raw.get("rules", []) or []
    if not isinstance(raw_rules, list):
        raise ValueError("entry_risk_modifiers.rules must be a list.")

    rules: list[dict[str, Any]] = []
    names: set[str] = set()
    for idx, raw_rule in enumerate(raw_rules):
        field = f"entry_risk_modifiers.rules[{idx}]"
        if not isinstance(raw_rule, Mapping):
            raise ValueError(f"{field} must be a mapping.")
        rule = dict(raw_rule)
        name = str(rule.get("name", "") or "").strip()
        if not _RULE_NAME_RE.fullmatch(name):
            raise ValueError(
                f"{field}.name must match {_RULE_NAME_RE.pattern!r}; received {name!r}."
            )
        if name in names:
            raise ValueError(f"entry_risk_modifiers rule names must be unique; duplicate {name!r}.")
        names.add(name)

        kind = str(rule.get("kind", "") or "").strip().lower()
        if kind not in _ALLOWED_KINDS:
            raise ValueError(f"{field}.kind must be one of {sorted(_ALLOWED_KINDS)}.")
        side = str(rule.get("side", "both") or "both").strip().lower()
        if side not in _ALLOWED_SIDES:
            raise ValueError(f"{field}.side must be one of {sorted(_ALLOWED_SIDES)}.")

        normalized: dict[str, Any] = {
            "name": name,
            "kind": kind,
            "side": side,
            "multiplier": _finite_multiplier(rule.get("multiplier"), field=f"{field}.multiplier"),
        }
        if kind == "column_range":
            col = str(rule.get("col", "") or "").strip()
            if not col:
                raise ValueError(f"{field}.col must be a non-empty string.")
            if rule.get("min") is None and rule.get("max") is None:
                raise ValueError(f"{field} must define at least one of min or max.")
            lower = float(rule["min"]) if rule.get("min") is not None else None
            upper = float(rule["max"]) if rule.get("max") is not None else None
            if lower is not None and not np.isfinite(lower):
                raise ValueError(f"{field}.min must be finite when provided.")
            if upper is not None and not np.isfinite(upper):
                raise ValueError(f"{field}.max must be finite when provided.")
            if lower is not None and upper is not None and lower > upper:
                raise ValueError(f"{field}.min must be <= {field}.max.")
            normalized.update({"col": col, "min": lower, "max": upper})
        elif kind == "local_hour":
            hours = rule.get("hours")
            if not isinstance(hours, list) or not hours:
                raise ValueError(f"{field}.hours must be a non-empty list.")
            normalized_hours: list[int] = []
            for hour in hours:
                if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour <= 23:
                    raise ValueError(f"{field}.hours entries must be integers in [0, 23].")
                normalized_hours.append(int(hour))
            timezone = str(rule.get("timezone", "UTC") or "UTC").strip()
            if not timezone:
                raise ValueError(f"{field}.timezone must be a non-empty string.")
            normalized.update(
                {
                    "hours": sorted(set(normalized_hours)),
                    "timezone": timezone,
                    "invert": bool(rule.get("invert", False)),
                }
            )
        rules.append(normalized)

    if enabled and not rules:
        raise ValueError("entry_risk_modifiers.rules must not be empty when enabled=true.")
    return {"enabled": enabled, "combine": combine, "rules": rules}


def required_entry_risk_modifier_columns(config: Mapping[str, Any] | None) -> list[str]:
    normalized = normalize_entry_risk_modifiers(config)
    return sorted(
        {
            str(rule["col"])
            for rule in normalized["rules"]
            if rule["kind"] == "column_range"
        }
    )


def entry_risk_modifier_for_candidate(
    row: pd.Series,
    *,
    timestamp: object,
    signal: float,
    previous_exit_reason: object | None,
    config: Mapping[str, Any] | None,
) -> tuple[float, list[str]]:
    """Return the causal risk multiplier and matched rule names for one candidate."""
    normalized = normalize_entry_risk_modifiers(config)
    if not normalized["enabled"]:
        return 1.0, []

    candidate_side = "short" if float(signal) < 0.0 else "long"
    matched: list[tuple[str, float]] = []
    for rule in normalized["rules"]:
        if rule["side"] not in {"both", candidate_side}:
            continue
        applies = False
        if rule["kind"] == "previous_stop":
            applies = _is_stop_exit_reason(previous_exit_reason)
        elif rule["kind"] == "column_range":
            value = pd.to_numeric(pd.Series([row.get(rule["col"])]), errors="coerce").iloc[0]
            if pd.notna(value):
                applies = bool(
                    (rule["min"] is None or float(value) >= float(rule["min"]))
                    and (rule["max"] is None or float(value) <= float(rule["max"]))
                )
        elif rule["kind"] == "local_hour":
            current = pd.Timestamp(timestamp)
            if current.tzinfo is None:
                current = current.tz_localize("UTC")
            local_hour = int(current.tz_convert(str(rule["timezone"])).hour)
            applies = local_hour in set(rule["hours"])
            if bool(rule["invert"]):
                applies = not applies
        if applies:
            matched.append((str(rule["name"]), float(rule["multiplier"])))

    if not matched:
        return 1.0, []
    if normalized["combine"] == "multiply":
        multiplier = float(np.prod([value for _, value in matched]))
    else:
        multiplier = min(value for _, value in matched)
    return multiplier, [name for name, _ in matched]


__all__ = [
    "entry_risk_modifier_for_candidate",
    "normalize_entry_risk_modifiers",
    "required_entry_risk_modifier_columns",
]
