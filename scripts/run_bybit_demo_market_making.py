from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from pathlib import Path
import signal
import sys
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.market_making.live_engine import BybitLiveMarketMakingEngine
from src.utils.dotenv import load_project_dotenv


def load_yaml(path: str | Path) -> dict[str, Any]:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    if not resolved.is_file():
        raise FileNotFoundError(f"configuration file not found: {resolved}")
    payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"configuration root must be a mapping: {resolved}")
    return payload


async def run(args: argparse.Namespace) -> tuple[Path, ...]:
    load_project_dotenv(PROJECT_ROOT / ".env")
    config = deepcopy(load_yaml(args.config))
    strategy_config = load_yaml(args.strategy_config)
    session = config.setdefault("session", {})
    execution = config.setdefault("execution", {})
    execution["mode"] = args.mode
    if args.reporting_interval_seconds is not None:
        session["reporting_interval_seconds"] = args.reporting_interval_seconds
    if args.aligned_windows is not None:
        session["aligned_windows"] = args.aligned_windows
    if args.flatten_at_boundary:
        session["flatten_at_boundary"] = True
    engine = BybitLiveMarketMakingEngine(
        config=config,
        strategy_config=strategy_config,
        mode=args.mode,
        duration_seconds=args.duration_seconds,
        max_windows=args.max_windows,
        aligned_windows=args.aligned_windows,
        flatten_at_boundary=args.flatten_at_boundary or None,
        cancel_all_on_exit=args.cancel_all_on_exit,
    )
    loop = asyncio.get_running_loop()

    def stop() -> None:
        loop.create_task(engine.request_stop())

    for name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, stop)
        except (NotImplementedError, RuntimeError):
            signal.signal(sig, lambda *_: stop())
    return await engine.run()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run BTCUSDT market making on Bybit public data with dry-run or Demo execution."
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--strategy-config", required=True)
    parser.add_argument("--mode", choices=("live_dry_run", "demo_submit"), default="live_dry_run")
    parser.add_argument("--duration-seconds", type=int)
    parser.add_argument("--reporting-interval-seconds", type=int)
    window_group = parser.add_mutually_exclusive_group()
    window_group.add_argument("--aligned-windows", dest="aligned_windows", action="store_true")
    window_group.add_argument("--rolling-window", dest="aligned_windows", action="store_false")
    parser.set_defaults(aligned_windows=None)
    parser.add_argument("--flatten-at-boundary", action="store_true")
    parser.add_argument("--max-windows", type=int)
    exit_group = parser.add_mutually_exclusive_group()
    exit_group.add_argument("--cancel-all-on-exit", dest="cancel_all_on_exit", action="store_true")
    exit_group.add_argument("--no-cancel-all-on-exit", dest="cancel_all_on_exit", action="store_false")
    parser.set_defaults(cancel_all_on_exit=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.duration_seconds is not None and args.duration_seconds <= 0:
        raise SystemExit("--duration-seconds must be > 0.")
    if args.reporting_interval_seconds is not None and args.reporting_interval_seconds <= 0:
        raise SystemExit("--reporting-interval-seconds must be > 0.")
    if args.max_windows is not None and args.max_windows <= 0:
        raise SystemExit("--max-windows must be > 0.")
    outputs = asyncio.run(run(args))
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
