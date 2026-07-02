from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.market_making.diagnostics import (
    discover_market_making_runs,
    write_market_making_comparison,
    write_market_making_diagnostics,
)
from src.market_making.reporting import write_market_making_markdown_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a market-making paper run.")
    parser.add_argument("--run-dir", default="logs/experiments/market_making")
    parser.add_argument("--orderbook-events", default=None)
    parser.add_argument("--markout-horizons", default="1,5,10,30")
    parser.add_argument("--max-inventory", type=float, default=None)
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--no-report", action="store_true")
    parser.add_argument("--language", choices=["el", "en"], default="el")
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--reports-root", default="logs/experiments")
    args = parser.parse_args()

    horizons = [int(value) for value in args.markout_horizons.split(",") if value.strip()]
    if args.all:
        runs = discover_market_making_runs(args.reports_root)
        artifacts = write_market_making_comparison(runs, Path(args.reports_root) / "market_making_comparison")
        print(f"Analyzed {len(runs)} runs. Comparison: {artifacts['summary']}")
        return
    run_dir = discover_market_making_runs(args.reports_root)[0] if args.latest else Path(args.run_dir)
    diagnostics = write_market_making_diagnostics(
        run_dir,
        orderbook_events_path=args.orderbook_events,
        markout_horizons=horizons,
        max_inventory=args.max_inventory,
        make_plots=not args.no_plots,
    )
    if not args.no_report:
        report_path = write_market_making_markdown_report(run_dir, diagnostics)
        diagnostics["artifacts"]["report.md"] = str(report_path)
    run = diagnostics["run"]
    gaps = diagnostics["gaps"]
    print("Market-making diagnostics")
    print(f"run_dir: {run_dir}")
    print(f"net_pnl: {run.get('total_pnl')}")
    print(f"fills: {run.get('number_of_fills')}")
    print(f"quotes: {run.get('number_of_quotes')}")
    print(f"fill_ratio: {run.get('fill_ratio')}")
    print(f"drawdown: {run.get('max_drawdown')}")
    print(f"markout_available: {not gaps.get('markout_missing')}")
    print(f"quote_events_available: {not gaps.get('quote_events_missing')}")
    if diagnostics["warnings"]:
        print("warnings:")
        for warning in diagnostics["warnings"][:10]:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
