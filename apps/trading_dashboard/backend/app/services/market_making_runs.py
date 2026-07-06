from __future__ import annotations

from pathlib import Path

from app.core.paths import DashboardPaths


MARKET_MAKING_MARKERS = {
    "summary.json",
    "orders.csv",
    "trades.csv",
    "pnl_timeseries.csv",
    "inventory_timeseries.csv",
    "orderbook_events.csv",
    "quote_events.csv",
}


def market_making_root(paths: DashboardPaths) -> Path:
    return paths.experiments_root / "market_making"


def discover_market_making_runs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    candidates = [root, *[path for path in root.rglob("*") if path.is_dir()]]
    runs: list[Path] = []
    for path in candidates:
        if path.name in {"datasets", "diagnostics"} or "comparison" in path.name:
            continue
        if any(part in {"datasets", "diagnostics"} for part in path.parts):
            continue
        try:
            names = {child.name for child in path.iterdir() if child.is_file()}
        except OSError:
            continue
        if MARKET_MAKING_MARKERS & names:
            runs.append(path)
    return sorted(set(runs), key=lambda path: path.stat().st_mtime, reverse=True)


def latest_market_making_run(paths: DashboardPaths) -> Path | None:
    runs = discover_market_making_runs(market_making_root(paths))
    return runs[0] if runs else None
