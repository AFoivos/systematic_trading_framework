from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.market_making.moment_dataset import build_market_making_moment_dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a quote-level market-making MOMENT research dataset.")
    parser.add_argument("--orderbook-events", required=True)
    parser.add_argument("--quote-events", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--horizons", default="1,5,10,30")
    parser.add_argument("--maker-fee-bps", type=float, default=0.0)
    parser.add_argument("--max-inventory", type=float, default=None)
    args = parser.parse_args(argv)

    horizons = [int(value) for value in args.horizons.split(",") if value.strip()]
    dataset = build_market_making_moment_dataset(
        orderbook_events_path=args.orderbook_events,
        quote_events_paths=args.quote_events,
        output_path=args.output,
        horizons=horizons,
        maker_fee_bps=args.maker_fee_bps,
        max_inventory=args.max_inventory,
    )
    print(f"Wrote {len(dataset)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
