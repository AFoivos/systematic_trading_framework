#!/usr/bin/env python3
"""Run the causal Binance spot/perpetual funding-carry research harness."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.experiments.support.funding_carry import (
    evaluate_validation_acceptance,
    load_funding_carry_config,
    run_funding_carry,
    write_funding_carry_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="Funding-carry pre-registration YAML.")
    parser.add_argument(
        "--phase",
        default="development",
        help="Configured split name or 'all'; defaults to development.",
    )
    parser.add_argument(
        "--unlock-locked-test",
        action="store_true",
        help="Explicitly authorize evaluation of a split marked locked.",
    )
    parser.add_argument("--output-dir", type=Path, help="Optional fresh artifact directory.")
    parser.add_argument("--no-write", action="store_true", help="Print metrics without artifacts.")
    args = parser.parse_args()

    config = load_funding_carry_config(args.config)
    baseline = run_funding_carry(
        config,
        phase=args.phase,
        allow_locked_test=args.unlock_locked_test,
    )
    stress_runs = {1.0: baseline}
    if config.version >= 2:
        for multiplier in config.reporting.cost_stress_multipliers:
            if multiplier == 1.0:
                continue
            stress_runs[multiplier] = run_funding_carry(
                config,
                phase=args.phase,
                allow_locked_test=args.unlock_locked_test,
                cost_multiplier=multiplier,
            )
        baseline.cost_stress = {
            f"{multiplier:.4f}": {
                "cost_multiplier": multiplier,
                "segments": {
                    split_name: {
                        "portfolio": segment.portfolio_metrics,
                        "symbols": segment.symbol_metrics,
                    }
                    for split_name, segment in run.segments.items()
                },
            }
            for multiplier, run in sorted(stress_runs.items())
        }
    if config.acceptance.validation_split in baseline.segments:
        stressed = stress_runs.get(config.acceptance.cost_stress_multiplier)
        if stressed is None:
            stressed = run_funding_carry(
                config,
                phase=config.acceptance.validation_split,
                cost_multiplier=config.acceptance.cost_stress_multiplier,
            )
        baseline.acceptance = evaluate_validation_acceptance(config, baseline, stressed)

    for split_name, segment in baseline.segments.items():
        metrics = segment.portfolio_metrics
        print(
            f"{split_name}: return={float(metrics['cumulative_return']):.4%} "
            f"sharpe={float(metrics['sharpe']):.3f} "
            f"max_drawdown={float(metrics['max_drawdown']):.4%}"
        )
        for symbol, symbol_metrics in sorted(segment.symbol_metrics.items()):
            print(
                f"  {symbol}: return={float(symbol_metrics['cumulative_return']):.4%} "
                f"sharpe={float(symbol_metrics['sharpe']):.3f} "
                f"entries={int(float(symbol_metrics['entries']))}"
            )
    if baseline.acceptance is not None:
        print(f"validation_qualified={baseline.acceptance['qualified']}")
        observed = baseline.acceptance["observed"]
        print(
            f"cost_stress_{config.acceptance.cost_stress_multiplier:.2f}x: "
            f"return={float(observed['stressed_portfolio_cumulative_return']):.4%} "
            f"sharpe={float(observed['stressed_portfolio_sharpe']):.3f}"
        )
    if baseline.cost_stress is not None:
        for multiplier, payload in sorted(baseline.cost_stress.items()):
            selected = next(iter(payload["segments"].values()))["portfolio"]
            print(
                f"cost_grid_{float(multiplier):.2f}x: "
                f"return={float(selected['cumulative_return']):.4%} "
                f"sharpe={float(selected['sharpe']):.3f}"
            )

    if not args.no_write:
        output = write_funding_carry_artifacts(
            config,
            baseline,
            output_dir=args.output_dir,
        )
        print(f"artifacts={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
