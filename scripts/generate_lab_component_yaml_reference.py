"""Generate the registry-backed YAML reference used by lab experiments.

Run from the repository root:

    python scripts/generate_lab_component_yaml_reference.py

The generated file is documentation, not a runnable experiment.  Callable
signatures are the source of truth for feature/helper/signal parameters.  Model
and target builders accept nested configuration dictionaries, so their detailed
parameter contracts remain linked to the hand-maintained catalogs.
"""

from __future__ import annotations

import inspect
from pathlib import Path
import sys
from typing import Any, Mapping

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.features.helpers.registry import NORMALIZATION_HELPERS, TRANSFORM_HELPERS
from src.features.registry import FEATURE_COMPATIBILITY_REGISTRY, FEATURE_REGISTRY
from src.models.registry import MODEL_REGISTRY
from src.signals.registry import DEPRECATED_SIGNAL_ALIASES, SIGNAL_REGISTRY
from src.targets.registry import TARGET_REGISTRY


OUTPUT = ROOT / "docs" / "lab_components_reference.yaml"


def _yaml_value(value: Any) -> Any:
    if value is inspect.Parameter.empty:
        return "<required>"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_yaml_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _yaml_value(item) for key, item in value.items()}
    return repr(value)


def _signature_params(fn: Any, *, excluded: set[str]) -> tuple[dict[str, Any], bool]:
    params: dict[str, Any] = {}
    has_dynamic_kwargs = False
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return params, True
    for name, parameter in signature.parameters.items():
        if name in excluded:
            continue
        if parameter.kind is inspect.Parameter.VAR_KEYWORD:
            has_dynamic_kwargs = True
            continue
        if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            continue
        params[name] = _yaml_value(parameter.default)
    return params, has_dynamic_kwargs


def _feature_entries(registry: Mapping[str, Any], *, compatibility: bool) -> list[dict[str, Any]]:
    entries = []
    for name, fn in registry.items():
        params, dynamic = _signature_params(fn, excluded={"df"})
        entry: dict[str, Any] = {
            "step": name,
            "enabled": False,
            "params": params,
        }
        if compatibility:
            entry["status"] = "compatibility_only"
        if dynamic:
            entry["parameters_note"] = "See docs/catalog/features.md for dynamic **params."
        entries.append(entry)
    return entries


def _helper_entries(registry: Mapping[str, Any], *, section: str) -> dict[str, Any]:
    entries: dict[str, Any] = {}
    for name, fn in registry.items():
        params, dynamic = _signature_params(fn, excluded={"df"})
        item: dict[str, Any] = {"enabled": False, "params": params}
        if dynamic:
            item["parameters_note"] = "See docs/catalog/helpers.md for dynamic **params."
        entries[name] = item
    return entries


def _signal_entries(registry: Mapping[str, Any], *, deprecated: bool = False) -> list[dict[str, Any]]:
    entries = []
    for name, fn in registry.items():
        params, dynamic = _signature_params(fn, excluded={"df"})
        entry: dict[str, Any] = {
            "kind": name,
            "enabled": False,
            "params": params,
        }
        if deprecated:
            entry["status"] = "deprecated_alias"
        if dynamic:
            entry["parameters_note"] = (
                "The callable uses **params; the complete nested contract and example "
                "are in docs/catalog/signals.md."
            )
        entries.append(entry)
    return entries


def _nested_config_entries(
    registry: Mapping[str, Any],
    *,
    owner: str,
    catalog: str,
) -> list[dict[str, Any]]:
    return [
        {
            "kind": name,
            "enabled": False,
            "params": {},
            "parameters_note": (
                f"{owner} builders accept a nested config contract. Copy the complete "
                f"parameter block from {catalog} and enable only one entry."
            ),
        }
        for name in registry
    ]


def build_reference() -> dict[str, Any]:
    return {
        "_meta": {
            "purpose": "Non-runnable YAML declaration reference for lab experiments.",
            "generated_by": "scripts/generate_lab_component_yaml_reference.py",
            "usage": [
                "Copy only the components you want into a real config.",
                "Set enabled: true only in the copied experiment.",
                "Replace <required> placeholders before validation.",
                "For nested model/target/signal contracts follow the linked catalog.",
            ],
            "catalogs": {
                "features": "docs/catalog/features.md",
                "helpers_and_normalizations": "docs/catalog/helpers.md",
                "models": "docs/catalog/models.md",
                "signals": "docs/catalog/signals.md",
                "targets": "docs/catalog/targets.md",
            },
        },
        "features": {
            "canonical": _feature_entries(FEATURE_REGISTRY, compatibility=False),
            "compatibility_only": _feature_entries(
                FEATURE_COMPATIBILITY_REGISTRY,
                compatibility=True,
            ),
        },
        "helpers": {
            "declaration_note": (
                "Place these under features[].transforms; params may also be expressed "
                "as items when the same helper is applied more than once."
            ),
            "transforms": _helper_entries(TRANSFORM_HELPERS, section="transforms"),
        },
        "normalizations": {
            "declaration_note": (
                "Place these under features[].normalizations. They execute before "
                "features[].transforms."
            ),
            "items": _helper_entries(NORMALIZATION_HELPERS, section="normalizations"),
        },
        "models": _nested_config_entries(
            MODEL_REGISTRY,
            owner="Model",
            catalog="docs/catalog/models.md",
        ),
        "signals": {
            "canonical": _signal_entries(SIGNAL_REGISTRY),
            "deprecated_aliases": _signal_entries(
                DEPRECATED_SIGNAL_ALIASES,
                deprecated=True,
            ),
        },
        "targets": _nested_config_entries(
            TARGET_REGISTRY,
            owner="Target",
            catalog="docs/catalog/targets.md",
        ),
    }


def main() -> None:
    payload = build_reference()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
