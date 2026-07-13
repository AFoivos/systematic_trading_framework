#!/usr/bin/env python3
"""Run the isolated fresh FTMO alpha-research YAML configurations.

This script intentionally does not invoke historical experiment configurations,
Optuna studies, logs, saved predictions, or reports.  It reads only the YAMLs
passed explicitly on the command line and their pinned raw CSV inputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

# ``python scripts/run_fresh_alpha_discovery.py`` puts ``scripts/`` rather
# than the repository root on sys.path.  Resolve the package root explicitly
# so the documented direct command is reproducible without PYTHONPATH setup.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.experiments.support.fresh_alpha_discovery import (
    load_fresh_strategy_config,
    run_fresh_strategy,
)


def _json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "configs",
        nargs="+",
        type=Path,
        help="Fresh-alpha YAML configuration paths only.",
    )
    parser.add_argument(
        "--phase",
        choices=("development", "validation", "all"),
        default="all",
        help="Chronological research stage to execute.",
    )
    parser.add_argument(
        "--skip-baselines",
        action="store_true",
        help="Skip expensive baseline and robustness calculations.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path for fully reproducible numeric results.",
    )
    args = parser.parse_args()

    outputs: dict[str, Any] = {}
    for config_path in args.configs:
        config = load_fresh_strategy_config(config_path)
        result = run_fresh_strategy(
            config,
            phase=args.phase,
            include_baselines=not args.skip_baselines,
        )
        outputs[config.strategy_id] = result
        selected = result.get("validation") or result.get("development")
        if selected:
            summary = selected["summary"]
            print(
                f"{config.strategy_id}: annualized_return={summary['annualized_return']:.4%} "
                f"sharpe={summary['sharpe']:.3f} "
                f"calmar={summary['calmar']:.3f} "
                f"trades={summary['trade_count']:.0f}"
            )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as handle:
            json.dump(outputs, handle, indent=2, default=_json_default, sort_keys=True)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
