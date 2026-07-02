from __future__ import annotations

import json
from pathlib import Path


LEGACY_MANIFEST_KEYS = {"report" + "_html", "experiment_report" + "_html"}


def test_generated_artifact_manifests_do_not_reference_legacy_document_formats() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    offenders: list[str] = []

    for manifest_path in repo_root.rglob("artifact_manifest.json"):
        if ".git" in manifest_path.parts:
            continue
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_text = json.dumps(payload, sort_keys=True)
        legacy_keys = LEGACY_MANIFEST_KEYS & set(_walk_keys(payload))
        if legacy_keys:
            offenders.append(f"{manifest_path}: keys={sorted(legacy_keys)}")
        if ".pptx" in manifest_text or "report" + ".html" in manifest_text:
            offenders.append(f"{manifest_path}: legacy artifact path")

    assert offenders == []


def test_repository_generated_outputs_do_not_include_legacy_document_formats() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    allowed_html_roots = {
        repo_root / "apps" / "trading_dashboard" / "frontend",
    }
    offenders: list[str] = []

    for path in repo_root.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() == ".pptx" and "reports" in path.parts:
            offenders.append(str(path.relative_to(repo_root)))
        if path.suffix.lower() == ".html" and ("logs" in path.parts or "reports" in path.parts):
            if not any(path.is_relative_to(root) for root in allowed_html_roots):
                offenders.append(str(path.relative_to(repo_root)))

    assert offenders == []


def _walk_keys(value: object) -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            keys.append(str(key))
            keys.extend(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(_walk_keys(child))
    return keys
