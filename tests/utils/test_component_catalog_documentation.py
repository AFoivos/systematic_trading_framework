"""Έλεγχοι πληρότητας για τους ελληνικούς component catalogs."""

from __future__ import annotations

from pathlib import Path
import inspect
import re

import yaml

from src.features.registry import FEATURE_COMPATIBILITY_REGISTRY, FEATURE_REGISTRY
from src.features.helpers.registry import NORMALIZATION_HELPERS, TRANSFORM_HELPERS
from src.signals.registry import DEPRECATED_SIGNAL_ALIASES, SIGNAL_REGISTRY
from src.targets.registry import TARGET_REGISTRY


CATALOGS = {
    "features.md": set(FEATURE_REGISTRY) | set(FEATURE_COMPATIBILITY_REGISTRY),
    "signals.md": set(SIGNAL_REGISTRY) | set(DEPRECATED_SIGNAL_ALIASES),
    "targets.md": set(TARGET_REGISTRY),
    "helpers.md": set(TRANSFORM_HELPERS) | set(NORMALIZATION_HELPERS),
}


def _entries(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^### `([^`]+)`\n", text, flags=re.MULTILINE))
    result = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result.append((match.group(1), text[match.end() : end]))
    return result


def test_catalogs_cover_every_registered_component_in_greek() -> None:
    for filename, expected_names in CATALOGS.items():
        text = (Path("docs/catalog") / filename).read_text(encoding="utf-8")
        entries = _entries(text)
        names = {name for name, _ in entries}

        assert names == expected_names
        assert len(entries) == len(expected_names)
        assert "Τι μετρά και τι πληροφορία δίνει." in text
        assert "Είσοδοι και έξοδοι." in text
        assert "Χρονική ορθότητα και αποφυγή διαρροής." in text
        assert "Πλήρες YAML παράδειγμα:" in text

        for name, body in entries:
            assert re.search(r"[Α-Ωα-ωΆΈΉΊΌΎΏάέήίόύώϊϋΐΰ]", body), name
            assert body.count("**Τι μετρά και τι πληροφορία δίνει.**") == 1, name
            assert body.count("**Είσοδοι και έξοδοι.**") == 1, name
            assert body.count("**Χρονική ορθότητα και αποφυγή διαρροής.**") == 1, name
            assert body.count("**Παράμετροι.**") == 1, name
            blocks = re.findall(r"```yaml\n(.*?)\n```", body, flags=re.DOTALL)
            assert len(blocks) == 1, name
            payload = yaml.safe_load(blocks[0])
            assert isinstance(payload, dict), name
            if filename == "helpers.md":
                feature = payload["features"][0]
                group = (
                    "transforms"
                    if name in TRANSFORM_HELPERS
                    else "normalizations"
                )
                owner = feature[group][name]
                assert feature["step"] == "<feature_step>"
                fn = (
                    TRANSFORM_HELPERS[name]
                    if name in TRANSFORM_HELPERS
                    else NORMALIZATION_HELPERS[name]
                )
                expected_params = {
                    parameter_name
                    for parameter_name, parameter in inspect.signature(fn).parameters.items()
                    if parameter_name != "df"
                    and parameter.kind
                    not in {
                        inspect.Parameter.VAR_POSITIONAL,
                        inspect.Parameter.VAR_KEYWORD,
                    }
                }
                assert set(owner["params"]) == expected_params, name
            else:
                owner = (
                    payload["features"][0]
                    if filename == "features.md"
                    else payload["signals"]
                    if filename == "signals.md"
                    else payload["target"]
                )
                assert owner["step" if filename == "features.md" else "kind"] == name
            assert isinstance(owner["params"], dict) and owner["params"], name


def test_catalogs_do_not_contain_known_english_boilerplate() -> None:
    forbidden = (
        "What it measures",
        "Required input columns",
        "Leakage policy",
        "Apply the registered",
        "This feature uses configured",
        "This signal uses configured",
        "This target uses configured",
        "Canonical features",
        "Canonical signals",
        "Canonical targets",
    )
    for filename in CATALOGS:
        text = (Path("docs/catalog") / filename).read_text(encoding="utf-8")
        for phrase in forbidden:
            assert phrase not in text, (filename, phrase)
