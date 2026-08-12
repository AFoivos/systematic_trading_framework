#!/usr/bin/env python3
from __future__ import annotations

"""Run generic and ETHUSD-specific quality gates on canonical Dukascopy data."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import pandas as pd

from src.src_data.dukascopy_canonical import (
    VOLUME_SEMANTICS,
    audit_acquisition_manifest,
    audit_canonical_30m_frame,
)
from src.src_data.quality import DataQualityContract, run_data_quality_checks

DEFAULT_DATASET = Path(
    "data/raw/dukascopy_ethusd_30m_canonical_v1/ethusd_30m_canonical.csv"
)
DEFAULT_ACQUISITION_MANIFEST = Path(
    "data/raw/dukascopy_ethusd_30m_canonical_v1/acquisition_manifest.json"
)
DEFAULT_CONTRACT = Path(
    "config/research/alpha_discovery/ethusd_30m_canonical_v1.contract.json"
)
DEFAULT_JSON = Path("data/raw/dukascopy_ethusd_30m_canonical_v1/quality_report.json")
DEFAULT_MARKDOWN = Path("data/raw/dukascopy_ethusd_30m_canonical_v1/quality_report.md")


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def build_report(
    *,
    dataset_path: Path,
    acquisition_manifest_path: Path,
    contract_path: Path,
    repository_root: Path,
) -> dict[str, Any]:
    contract_payload = json.loads(contract_path.read_text(encoding="utf-8"))
    contract = DataQualityContract.from_dict(contract_payload)
    if contract.volume_semantics != VOLUME_SEMANTICS:
        raise ValueError(
            "Quality contract volume semantics differ from the canonical provider adapter."
        )
    frame = pd.read_csv(dataset_path)
    generic = run_data_quality_checks(frame, contract).to_dict()
    canonical = audit_canonical_30m_frame(frame)
    source = audit_acquisition_manifest(
        acquisition_manifest_path,
        repository_root=repository_root,
    )
    eligible = bool(
        generic["research_eligible"]
        and canonical["research_eligible"]
        and source["research_eligible"]
    )
    has_warning = any(
        component["status"] == "PASS_WITH_WARNINGS"
        or any(issue["severity"] == "WARNING" for issue in component["issues"])
        for component in (generic, canonical, source)
    )
    status = (
        "FAIL" if not eligible else ("PASS_WITH_WARNINGS" if has_warning else "PASS")
    )
    return {
        "schema_version": 1,
        "dataset_id": "ETHUSD-30M-CANONICAL-V1-SOURCE",
        "status": status,
        "research_eligible": eligible,
        "dataset_path": dataset_path.as_posix(),
        "dataset_sha256": _file_sha256(dataset_path),
        "contract_path": contract_path.as_posix(),
        "contract_sha256": _file_sha256(contract_path),
        "acquisition_manifest_path": acquisition_manifest_path.as_posix(),
        "acquisition_manifest_sha256": _file_sha256(acquisition_manifest_path),
        "generic_quality": generic,
        "canonical_quality": canonical,
        "source_integrity": source,
    }


def _markdown(report: Mapping[str, Any]) -> str:
    generic = report["generic_quality"]
    canonical = report["canonical_quality"]
    source = report["source_integrity"]
    generic_metrics = generic["metrics"]
    canonical_metrics = canonical["metrics"]
    source_metrics = source["metrics"]
    lines = [
        "# ETHUSD-30M-CANONICAL-V1 source quality report",
        "",
        f"- Overall status: **{report['status']}**",
        f"- Research eligible: **{str(report['research_eligible']).lower()}**",
        f"- Dataset SHA-256: `{report['dataset_sha256']}`",
        f"- Rows: `{generic_metrics.get('row_count')}`",
        f"- Coverage: `{generic_metrics.get('first_timestamp')}` to `{generic_metrics.get('last_timestamp')}`",
        f"- Timestamp gaps: `{generic_metrics.get('gap_count')}`",
        f"- Estimated missing 30m intervals: `{generic_metrics.get('estimated_missing_interval_count')}`",
        f"- Maximum gap multiple: `{generic_metrics.get('maximum_gap_multiple')}`",
        f"- Partial observed-minute bars: `{canonical_metrics.get('partial_30m_bar_count')}` "
        f"(`{canonical_metrics.get('partial_30m_bar_rate'):.6%}`)",
        f"- Spread semantics: `{generic_metrics.get('spread_bps_semantics')}`",
        f"- Raw artifacts audited: `{source_metrics.get('audited_raw_artifact_count')}`",
        f"- Raw source fingerprint match: `{source_metrics.get('source_fingerprints_match')}`",
        f"- Canonical fingerprint match: `{source_metrics.get('canonical_sha256_match')}`",
        "",
        "## Issues",
        "",
    ]
    issues: list[tuple[str, Mapping[str, Any]]] = []
    for component_name, component in (
        ("generic", generic),
        ("canonical", canonical),
        ("source", source),
    ):
        issues.extend((component_name, issue) for issue in component["issues"])
    if not issues:
        lines.append("No issues detected.")
    else:
        for component, issue in issues:
            count = "" if issue.get("count") is None else f" (count={issue['count']})"
            lines.append(
                f"- **{issue['severity']} — {component}:{issue['code']}**: "
                f"{issue['message']}{count}"
            )
    lines.extend(
        [
            "",
            "## Gap report",
            "",
            "Gaps are preserved as missing coverage and were not forward-filled or reconstructed.",
            "",
        ]
    )
    for item in canonical_metrics.get("gap_report", []):
        lines.append(
            f"- `{item['previous_timestamp']}` -> `{item['next_timestamp']}`: "
            f"{item['estimated_missing_30m_intervals']} missing 30m intervals"
        )
    return "\n".join(lines) + "\n"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--acquisition-manifest", type=Path, default=DEFAULT_ACQUISITION_MANIFEST
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        dataset_path=args.dataset,
        acquisition_manifest_path=args.acquisition_manifest,
        contract_path=args.contract,
        repository_root=args.repository_root,
    )
    _atomic_text(
        args.json_output,
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
    )
    _atomic_text(args.markdown_output, _markdown(report))
    print(
        json.dumps(
            {
                "status": report["status"],
                "research_eligible": report["research_eligible"],
                "dataset_sha256": report["dataset_sha256"],
                "json_output": args.json_output.as_posix(),
                "markdown_output": args.markdown_output.as_posix(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["research_eligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
