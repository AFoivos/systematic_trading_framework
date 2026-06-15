#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.experiments.support.c2_scalp_grid import run_c2_scalp_grid


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the C2 scalp diagnostic grid.")
    parser.add_argument(
        "--config",
        default="config/experiments/c2_30m_regime_aware_momentum_v1.yaml",
        help="Experiment config used to build the C2 feature and signal frame.",
    )
    parser.add_argument(
        "--asset",
        default=None,
        help="Asset to run when the config resolves multiple assets.",
    )
    parser.add_argument(
        "--output-dir",
        default="logs/diagnostics",
        help="Directory where the timestamped diagnostic run directory will be created.",
    )
    parser.add_argument(
        "--run-name",
        default=None,
        help="Optional deterministic run directory name under --output-dir.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=8,
        help="Number of top rows to print.",
    )
    args = parser.parse_args()

    result = run_c2_scalp_grid(
        args.config,
        asset=args.asset,
        output_dir=args.output_dir,
        run_name=args.run_name,
    )
    results = result["results"].sort_values(
        ["net_pnl_per_trade", "net_pnl"],
        ascending=[False, False],
        na_position="last",
    )
    columns = [
        "name",
        "trade_count",
        "gross_pnl_per_trade",
        "cost_per_trade",
        "net_pnl_per_trade",
        "profit_factor",
        "hit_rate",
        "net_pnl",
        "passes_cost_diagnostic",
    ]
    print(f"Artifacts: {result['artifacts']['run_dir']}")
    print(results[columns].head(max(int(args.top), 1)).to_string(index=False))


if __name__ == "__main__":
    main()
