"""Generate exhaustive, registry-backed appendices for the component catalogs.

The hand-written parts of the catalogs explain the trading ideas in depth.  The
appendices generated here provide the mechanical completeness guarantee: every
registered name gets a prose paragraph and a copy-ready YAML declaration whose
parameters are derived from the callable signature or configuration access.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
import re
import sys
from typing import Any, Mapping

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.features.registry import FEATURE_COMPATIBILITY_REGISTRY, FEATURE_REGISTRY
from src.signals.registry import DEPRECATED_SIGNAL_ALIASES, SIGNAL_REGISTRY
from src.targets.registry import TARGET_REGISTRY

START = "<!-- BEGIN GENERATED EXHAUSTIVE REFERENCE -->"
END = "<!-- END GENERATED EXHAUSTIVE REFERENCE -->"


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


def _signature_params(fn: Any) -> tuple[dict[str, Any], bool]:
    params: dict[str, Any] = {}
    dynamic = False
    for name, parameter in inspect.signature(fn).parameters.items():
        if name in {"df", "target_cfg"}:
            continue
        if parameter.kind is inspect.Parameter.VAR_KEYWORD:
            dynamic = True
            continue
        if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            continue
        params[name] = _yaml_value(parameter.default)
    return params, dynamic


def _source_config_defaults(fn: Any) -> dict[str, Any]:
    """Collect literal ``cfg/params.get(key, default)`` contracts from source."""
    try:
        tree = ast.parse(inspect.getsource(fn))
    except (OSError, TypeError, IndentationError, SyntaxError):
        return {}
    found: dict[str, Any] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "get" or not node.args:
            continue
        try:
            key = ast.literal_eval(node.args[0])
        except (ValueError, TypeError):
            continue
        if not isinstance(key, str) or key in {"kind", "params"}:
            continue
        default: Any = "<required>"
        if len(node.args) > 1:
            try:
                default = ast.literal_eval(node.args[1])
            except (ValueError, TypeError):
                default = "<configured>"
        found.setdefault(key, _yaml_value(default))
    return found


def _doc_yaml_params(fn: Any, category: str) -> dict[str, Any]:
    """Recover the maintained example contract from a NumPy-style docstring."""
    doc = inspect.getdoc(fn) or ""
    marker = "YAML declaration::"
    if marker not in doc:
        return {}
    tail = doc.split(marker, 1)[1].lstrip()
    block = tail.split("\n\n", 1)[0].strip()
    try:
        payload = yaml.safe_load(block)
    except yaml.YAMLError:
        return {}
    if not isinstance(payload, dict):
        return {}
    owner = payload.get({"feature": "features", "signal": "signals", "target": "target"}[category])
    if category == "feature" and isinstance(owner, list) and owner:
        owner = owner[0]
    if not isinstance(owner, dict):
        return {}
    nested = owner.get("params")
    if isinstance(nested, dict):
        return dict(nested)
    return {
        str(key): value
        for key, value in owner.items()
        if key not in {"step", "kind", "enabled", "output_cols"}
    }


def _first_paragraph(fn: Any, name: str, category: str) -> str:
    doc = inspect.getdoc(fn) or ""
    paragraphs = [re.sub(r"\s+", " ", part).strip() for part in re.split(r"\n\s*\n", doc)]
    useful = [
        part
        for part in paragraphs
        if part
        and "YAML declaration" not in part
        and not part.startswith(("Required input", "Parameters", "Outputs"))
    ]
    text = useful[0] if useful else f"Registered {category} component `{name}`."
    if text.startswith("Apply the registered") and len(useful) > 1:
        text = useful[1]
    return text.rstrip(".") + "."


def _interpretation(category: str) -> str:
    if category == "feature":
        return (
            "Η πληροφορία του είναι point-in-time: οι υψηλότερες, χαμηλότερες ή "
            "προσημασμένες τιμές πρέπει να ερμηνεύονται σύμφωνα με τις output "
            "στήλες του builder και να χρησιμοποιούνται μόνο αφού κλείσει το bar."
        )
    if category == "signal":
        return (
            "Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, "
            "αρνητική short και μηδέν flat· candidate/score στήλες είναι "
            "διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση."
        )
    return (
        "Η τιμή είναι αποκλειστικά label μελλοντικού outcome για training ή "
        "evaluation· δεν επιτρέπεται να επιστρέψει ως feature ή signal, ενώ τα "
        "τελευταία rows χωρίς πλήρη ορίζοντα αναμένονται να είναι NaN."
    )


def _yaml_block(category: str, name: str, fn: Any) -> str:
    params, dynamic = _signature_params(fn)
    source_params = _source_config_defaults(fn)
    documented_params = _doc_yaml_params(fn, category)
    if category == "feature" and not params and name in SIGNAL_REGISTRY:
        # Compatibility entries are lazy wrappers; their real parameter
        # contract is the same callable exposed by the signal registry.
        signal_fn = SIGNAL_REGISTRY[name]
        params, dynamic = _signature_params(signal_fn)
        documented_params = _doc_yaml_params(signal_fn, "signal")
        source_params = _source_config_defaults(signal_fn)
    if category == "target":
        params = {**documented_params, **source_params}
        payload = {"target": {"kind": name, "params": params}}
    elif category == "signal":
        if dynamic:
            params.update(documented_params)
            params.update(source_params)
        payload = {"signals": {"kind": name, "params": params}}
    else:
        if dynamic:
            params.update(documented_params)
            params.update(source_params)
        payload = {"features": [{"step": name, "params": params}]}
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100).rstrip()


def _section(
    title: str,
    registry: Mapping[str, Any],
    category: str,
    *,
    status: str | None = None,
) -> str:
    lines = [f"## {title}", ""]
    for name, fn in registry.items():
        lines.extend(
            [
                f"### `{name}`",
                "",
                (
                    f"{_first_paragraph(fn, name, category)} "
                    f"{_interpretation(category)}"
                ),
                "",
            ]
        )
        if status:
            lines.extend([f"Κατάσταση: **{status}**.", ""])
        lines.extend(["Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:", "", "```yaml"])
        lines.extend(_yaml_block(category, name, fn).splitlines())
        lines.extend(["```", ""])
    return "\n".join(lines)


def _appendix(category: str) -> str:
    intro = (
        f"{START}\n\n"
        "# Πλήρης registry-backed αναφορά\n\n"
        "Η ενότητα αυτή παράγεται από τα ενεργά registries και τις υπογραφές του "
        "κώδικα. Έτσι κάθε διαθέσιμο component έχει αυτοτελή παράγραφο και "
        "copy-ready YAML. Τιμές όπως `<required>` πρέπει να αντικατασταθούν, ενώ "
        "`<configured>` δηλώνει runtime επιλογή που δεν έχει ασφαλές καθολικό default.\n\n"
    )
    if category == "feature":
        body = _section("Canonical features", FEATURE_REGISTRY, category)
        body += "\n" + _section(
            "Compatibility-only features",
            FEATURE_COMPATIBILITY_REGISTRY,
            category,
            status="compatibility-only",
        )
    elif category == "signal":
        body = _section("Canonical signals", SIGNAL_REGISTRY, category)
        body += "\n" + _section(
            "Deprecated signal aliases",
            DEPRECATED_SIGNAL_ALIASES,
            category,
            status="deprecated alias",
        )
    else:
        body = _section("Canonical targets", TARGET_REGISTRY, category)
    return intro + body + f"\n{END}\n"


def _replace_generated(path: Path, generated: str) -> None:
    text = path.read_text(encoding="utf-8")
    if START in text:
        text = text[: text.index(START)].rstrip() + "\n\n"
    path.write_text(text + generated, encoding="utf-8", newline="\n")


def main() -> None:
    for category in ("feature", "signal", "target"):
        path = ROOT / "docs" / "catalog" / f"{category}s.md"
        _replace_generated(path, _appendix(category))
        print(f"Updated {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
