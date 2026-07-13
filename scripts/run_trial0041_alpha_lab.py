#!/usr/bin/env python3
"""Run the deterministic ETHUSD Trial 0041 alpha-research laboratory.

The tool intentionally uses the framework's public config loader and experiment
runner.  It preserves the immutable historical baseline as a provenance copy,
screens only folds 0--9, freezes finalists, and then opens folds 10--16 once.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.experiments.support.trial0041_alpha_lab import (  # noqa: E402
    build_screening_leaderboard,
    generate_finalists,
    generate_lab_configs,
    run_diagnostics,
    run_locked_finalists,
    run_screening,
    validate_lab_configs,
    write_final_alpha_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stage",
        choices=("generate", "validate", "diagnostics", "screen", "finalists", "locked", "report", "all"),
        help="Research stage to run.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Re-run experiments even when a matching successful record is present.",
    )
    args = parser.parse_args(argv)
    resume = not args.no_resume

    if args.stage in {"generate", "all"}:
        info = generate_lab_configs()
        print(f"Generated {info['first_stage_count']} first-stage YAMLs; manifest={info['manifest']}")
    if args.stage in {"validate", "all"}:
        validation = validate_lab_configs(include_finalists=args.stage == "all")
        invalid = int((validation["status"] != "valid").sum()) if not validation.empty else 0
        print(f"Validated {len(validation)} YAMLs; invalid={invalid}")
        if invalid:
            return 2
    if args.stage in {"diagnostics", "all"}:
        diagnostics = run_diagnostics()
        print(f"Diagnostics complete; feature_rows={diagnostics['feature_rows']}")
    if args.stage in {"screen", "all"}:
        execution = run_screening(resume=resume)
        leaderboard = build_screening_leaderboard()
        print(f"Screening complete; successful={(execution['status'] == 'success').sum()} leaderboard_rows={len(leaderboard)}")
    if args.stage in {"finalists", "all"}:
        finalists = generate_finalists()
        print(f"Frozen finalists={len(finalists)}")
    if args.stage in {"locked", "all"}:
        locked = run_locked_finalists(resume=resume)
        print(f"Locked runs={len(locked)} stress_validated={int(locked['stress_validated'].sum()) if not locked.empty else 0}")
    if args.stage in {"report", "all"}:
        report = write_final_alpha_report()
        print(f"Wrote {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
