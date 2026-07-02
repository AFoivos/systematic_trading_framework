from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.venues.kraken.futures_demo import KrakenFuturesDemoAdapter


def load_config(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


async def run(config: dict[str, Any]) -> None:
    execution = config.get("execution", {})
    if execution.get("mode") != "kraken_futures_demo":
        raise SystemExit("Kraken demo runner requires execution.mode: kraken_futures_demo.")
    if execution.get("allow_demo_orders") is not True:
        raise SystemExit("Kraken demo runner requires allow_demo_orders: true.")
    adapter = KrakenFuturesDemoAdapter(
        mode="kraken_futures_demo",
        allow_demo_orders=True,
    )
    await adapter.connect()
    await adapter.subscribe_order_book(execution.get("symbol", "PI_XBTUSD"))
    await adapter.disconnect()
    raise SystemExit(
        "Kraken Futures demo connectivity scaffold is ready, but REST order placement is not wired in this pass."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Kraken Futures demo market-making scaffold.")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    asyncio.run(run(load_config(args.config)))


if __name__ == "__main__":
    main()
