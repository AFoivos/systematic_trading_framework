#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
import tracemalloc

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.features.systems import add_kds_features, add_lmds_features, add_rlvs_features


def _synthetic_m1(rows: int) -> pd.DataFrame:
    index = pd.date_range("2020-01-01", periods=rows, freq="min", tz="UTC")
    position = np.arange(rows, dtype=float)
    volatility = 1.5e-5 * (
        1.0
        + 0.50 * (np.sin(position / 25_000.0) + 1.0)
        + 0.75 * (position >= rows * 0.70)
    )
    log_return = (
        1.0e-7
        + volatility * np.sin(position * 0.77)
        + 0.35 * volatility * np.cos(position * 0.13)
    )
    close = 1.10 * np.exp(np.cumsum(log_return))
    open_ = np.r_[close[0], close[:-1]]
    half_range = close * (1.5e-5 + volatility)
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + half_range,
            "low": np.minimum(open_, close) - half_range,
            "close": close,
            "spread_bps": 0.7 + 0.2 * (1.0 + np.sin(position / 1_000.0)),
            "tick_volume": 100.0 + (position % 100.0),
        },
        index=index,
    )


def run_benchmark(rows: int, *, preset: str) -> dict[str, object]:
    frame = _synthetic_m1(rows)
    component_seconds: dict[str, float] = {}
    tracemalloc.start()
    total_start = time.perf_counter()

    start = time.perf_counter()
    featured = add_kds_features(frame, preset=preset)
    component_seconds["kds"] = time.perf_counter() - start

    start = time.perf_counter()
    featured = add_rlvs_features(featured, preset=preset)
    component_seconds["rlvs"] = time.perf_counter() - start

    start = time.perf_counter()
    featured = add_lmds_features(featured, preset=preset)
    component_seconds["lmds"] = time.perf_counter() - start

    total_seconds = time.perf_counter() - total_start
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    expensive = sorted(
        component_seconds,
        key=component_seconds.__getitem__,
        reverse=True,
    )
    return {
        "rows": rows,
        "preset": preset,
        "runtime_seconds": total_seconds,
        "rows_per_second": rows / total_seconds,
        "peak_memory_mb": peak_bytes / (1024.0**2),
        "component_seconds": component_seconds,
        "expensive_components": expensive,
        "output_columns": len(featured.columns),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Performance benchmark for causal market-state systems.")
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument(
        "--include-million",
        action="store_true",
        help="Also run 1,000,000 rows; memory and runtime can be substantial.",
    )
    parser.add_argument(
        "--preset",
        choices=("conservative", "balanced", "responsive"),
        default="balanced",
    )
    args = parser.parse_args()
    if args.rows < 1_000:
        parser.error("--rows must be >= 1000.")

    sizes = [args.rows]
    if args.include_million and 1_000_000 not in sizes:
        sizes.append(1_000_000)
    results = [run_benchmark(size, preset=args.preset) for size in sizes]
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
