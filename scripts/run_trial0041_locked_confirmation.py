#!/usr/bin/env python3
"""Run the deterministic, frozen ETHUSD Trial 0041 locked confirmation."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.experiments.support.trial0041_locked_confirmation import (  # noqa: E402
    create_manifest,
    generate_configs,
    run_confirmation,
    validate_configs,
    verify_manifest,
    write_host_git_provenance,
    write_reports,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("provenance", "generate", "freeze", "validate", "run", "report", "all"))
    parser.add_argument("--no-resume", action="store_true", help="Re-run configs even when a matching locked metrics artifact exists.")
    args = parser.parse_args(argv)
    if args.stage == "provenance":
        print(f"Wrote host git provenance to {write_host_git_provenance()}")
        return 0
    if args.stage in {"generate", "all"}:
        frame = generate_configs()
        print(f"Generated {len(frame)} frozen candidate configs.")
    if args.stage in {"freeze", "all"}:
        manifest = create_manifest()
        print(f"Frozen manifest with {len(manifest['configs'])} configs.")
    if args.stage in {"validate", "all"}:
        frame = validate_configs()
        invalid = int((frame["status"] != "valid").sum())
        print(f"Validated {len(frame)} configs; invalid={invalid}")
        if invalid:
            return 2
        if args.stage == "validate":
            verify_manifest()
    if args.stage in {"run", "all"}:
        frame = run_confirmation(resume=not args.no_resume)
        print(f"Locked execution complete: {len(frame)} runs.")
    if args.stage in {"report", "all"}:
        path = write_reports()
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
