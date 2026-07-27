#!/usr/bin/env python3
"""Download a normalized, hashed Binance snapshot for funding-carry research."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.experiments.support.funding_carry import load_funding_carry_config
from src.src_data.binance_public import SUPPORTED_DATASETS, download_binance_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="Funding-carry pre-registration YAML.")
    parser.add_argument(
        "--datasets",
        nargs="+",
        choices=SUPPORTED_DATASETS,
        default=list(SUPPORTED_DATASETS),
        help="Public Binance datasets to include; defaults to the complete research snapshot.",
    )
    parser.add_argument(
        "--required-only",
        action="store_true",
        help="Download only spot klines, perpetual klines, and funding rates.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refetch and atomically replace a matching cached snapshot.",
    )
    args = parser.parse_args()

    config = load_funding_carry_config(args.config)
    datasets = (
        ["spot_klines", "perp_klines", "funding_rates"]
        if args.required_only
        else args.datasets
    )
    manifest = download_binance_snapshot(
        output_dir=config.data.snapshot_dir,
        symbols=config.data.symbols,
        start=config.data.start,
        end=config.data.end,
        interval=config.data.interval,
        datasets=datasets,
        refresh=args.refresh,
    )
    print(f"snapshot={config.data.snapshot_dir}")
    print(f"request_sha256={manifest['request_sha256']}")
    for key, metadata in sorted(manifest["files"].items()):
        print(f"{key}: rows={metadata['rows']} sha256={metadata['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
