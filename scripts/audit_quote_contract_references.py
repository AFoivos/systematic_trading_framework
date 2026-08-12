#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

SCAN_ROOTS = ("src", "scripts", "config", "tests", "apps", "docs")
TEXT_SUFFIXES = {
    ".cs",
    ".css",
    ".csv",
    ".html",
    ".ipynb",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mjs",
    ".py",
    ".rst",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_FILENAMES = {"Dockerfile"}
TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(spread_absolute|spread_fraction|spread_bps|spread|bid|ask|mid)(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def _category(path: Path, token: str) -> str:
    normalized = path.as_posix()
    lowered = token.lower()
    if normalized.endswith("frameworkCatalog.generated.json"):
        return "GENERATED_CATALOG_REFERENCE"
    if normalized.startswith("tests/"):
        return "TEST_CONTRACT_REFERENCE"
    if "/best_runs/" in normalized:
        return "HISTORICAL_ARTIFACT_LEGACY_SEMANTICS"
    if normalized.startswith(
        ("src/market_making/", "src/market_data/")
    ) or normalized.startswith(
        ("config/execution/", "config/experiments/legacy/market_making/")
    ):
        return "CANONICAL_TRUE_BPS_MARKET_MICROSTRUCTURE"
    if normalized in {
        "src/src_data/quote_contract.py",
        "scripts/prepare_dukascopy_30m_bid_ask_mid.py",
        "scripts/prepare_dukascopy_ftmo_mid.py",
        "scripts/migrate_legacy_spread_contract.py",
    }:
        return "CANONICAL_QUOTE_CONTRACT_OR_PRODUCER"
    if lowered == "spread_fraction":
        return "CANONICAL_FRACTION_REFERENCE"
    if lowered == "spread_absolute":
        return "CANONICAL_ABSOLUTE_REFERENCE"
    if lowered == "spread_bps":
        return "CANONICAL_BPS_OR_EXPLICIT_LEGACY_REFERENCE"
    if lowered in {"bid", "ask", "mid"}:
        return "QUOTE_PRICE_FIELD_REFERENCE"
    return "CONTEXTUAL_SPREAD_REFERENCE_UNIT_NOT_IMPLIED"


def _iter_files(root: Path) -> Iterable[Path]:
    for directory_name in SCAN_ROOTS:
        directory = root / directory_name
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or (
                path.suffix.lower() not in TEXT_SUFFIXES
                and path.name not in TEXT_FILENAMES
            ):
                continue
            if any(
                part in {"__pycache__", "node_modules", ".git"} for part in path.parts
            ):
                continue
            yield path


def audit_references(root: str | Path) -> dict[str, object]:
    base = Path(root).resolve()
    occurrences: list[dict[str, object]] = []
    for path in _iter_files(base):
        relative = path.relative_to(base)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for match in TOKEN_PATTERN.finditer(line):
                token = match.group(1)
                occurrences.append(
                    {
                        "path": relative.as_posix(),
                        "line": line_number,
                        "column": match.start(1) + 1,
                        "token": token,
                        "category": _category(relative, token),
                        "text": line.strip(),
                    }
                )
    categories = Counter(str(item["category"]) for item in occurrences)
    tokens = Counter(str(item["token"]).lower() for item in occurrences)
    return {
        "schema_version": 1,
        "scan_roots": list(SCAN_ROOTS),
        "occurrence_count": len(occurrences),
        "file_count": len({str(item["path"]) for item in occurrences}),
        "counts_by_category": dict(sorted(categories.items())),
        "counts_by_token": dict(sorted(tokens.items())),
        "occurrences": occurrences,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify every repository quote/spread token occurrence."
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--output-json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = audit_references(args.root)
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output_json:
        target = Path(args.output_json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
