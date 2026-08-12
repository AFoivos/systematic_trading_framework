#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd

from src.src_data.quote_contract import (
    QuoteColumnNames,
    SpreadSemantics,
    add_canonical_quote_columns,
    classify_spread_bps_semantics,
)
from src.utils.run_metadata import file_sha256

_CLOSE_QUOTE_COLUMNS = QuoteColumnNames(
    bid="bid_close",
    ask="ask_close",
    mid="close",
    spread_absolute="spread_absolute",
    spread_fraction="spread_fraction",
    spread_bps="spread_bps",
)


def audit_legacy_csv(path: str | Path) -> dict[str, object]:
    source = Path(path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Legacy quote CSV not found: {source}")
    frame = pd.read_csv(source)
    semantics = classify_spread_bps_semantics(frame, columns=_CLOSE_QUOTE_COLUMNS)
    return {
        "path": str(source),
        "sha256": file_sha256(source),
        "row_count": int(len(frame)),
        "columns": [str(column) for column in frame.columns],
        "spread_bps_semantics": semantics.value,
        "research_classifications": (
            ["REGENERATE_REQUIRED", "LEGACY_AMBIGUOUS_UNITS"]
            if semantics is SpreadSemantics.LEGACY_FRACTION
            else []
        ),
    }


def migrate_legacy_csv(
    source_path: str | Path,
    *,
    output_path: str | Path,
) -> tuple[Path, Path]:
    """Write a non-destructive unit-corrected copy plus a blocking sidecar.

    This does not prove the historical BID/ASK merge and deliberately marks the
    output REGENERATE_REQUIRED. Only regeneration from original side files may
    later become a validated research snapshot.
    """

    source = Path(source_path).resolve()
    output = Path(output_path).resolve()
    if source == output:
        raise ValueError("Migration output must differ from the legacy source path.")
    if output.exists():
        raise FileExistsError(f"Migration refuses to overwrite: {output}")
    sidecar = output.with_suffix(output.suffix + ".migration.json")
    if sidecar.exists():
        raise FileExistsError(f"Migration refuses to overwrite sidecar: {sidecar}")
    frame = pd.read_csv(source)
    semantics = classify_spread_bps_semantics(frame, columns=_CLOSE_QUOTE_COLUMNS)
    if semantics is not SpreadSemantics.LEGACY_FRACTION:
        raise ValueError(
            "Migration requires verified LEGACY_FRACTION semantics; "
            f"found {semantics.value}."
        )
    migrated = frame.copy()
    migrated["spread_bps_legacy_fraction"] = pd.to_numeric(
        migrated["spread_bps"], errors="raise"
    )
    migrated = migrated.drop(columns=["spread_bps"])
    migrated = add_canonical_quote_columns(
        migrated,
        columns=_CLOSE_QUOTE_COLUMNS,
    )
    if "spread_close" in migrated.columns:
        observed_spread_close = pd.to_numeric(migrated["spread_close"], errors="coerce")
        spread_tolerance = 1e-12 + 1e-10 * migrated["spread_absolute"].abs()
        if (
            observed_spread_close.isna().any()
            or not (observed_spread_close - migrated["spread_absolute"])
            .abs()
            .le(spread_tolerance)
            .all()
        ):
            raise ValueError(
                "Legacy spread_close conflicts with ask_close - bid_close; "
                "migration refuses to overwrite it."
            )
        migrated["spread_close"] = migrated["spread_absolute"]
    output.parent.mkdir(parents=True, exist_ok=True)
    nonce = uuid4().hex
    temporary_output = output.with_name(f".{output.name}.{nonce}.tmp")
    temporary_sidecar = sidecar.with_name(f".{sidecar.name}.{nonce}.tmp")
    try:
        migrated.to_csv(temporary_output, index=False)
        payload = {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_path": str(source),
            "source_sha256": file_sha256(source),
            "output_path": str(output),
            "output_sha256": file_sha256(temporary_output),
            "legacy_column_preserved_as": "spread_bps_legacy_fraction",
            "canonical_columns": ["spread_absolute", "spread_fraction", "spread_bps"],
            "classification": "REGENERATE_REQUIRED",
            "research_eligible": False,
            "reason": (
                "Unit-only migration cannot reconstruct or verify the missing original "
                "Dukascopy BID/ASK inputs and their join coverage."
            ),
        }
        temporary_sidecar.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary_output.rename(output)
        temporary_sidecar.rename(sidecar)
    except Exception:
        temporary_output.unlink(missing_ok=True)
        temporary_sidecar.unlink(missing_ok=True)
        raise
    return output, sidecar


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit or non-destructively migrate a legacy Dukascopy spread_bps CSV."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit = subparsers.add_parser("audit")
    audit.add_argument("paths", nargs="+")
    audit.add_argument("--output-json")
    migrate = subparsers.add_parser("migrate")
    migrate.add_argument("source_path")
    migrate.add_argument("output_path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "audit":
        payload = [audit_legacy_csv(path) for path in args.paths]
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.output_json:
            target = Path(args.output_json)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
        return 0
    output, sidecar = migrate_legacy_csv(
        args.source_path,
        output_path=args.output_path,
    )
    print(json.dumps({"output": str(output), "sidecar": str(sidecar)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
