"""Coverage audit for the global-session-relay 30-minute research universe.

This is intentionally a data-quality utility, not a strategy backtest.  Its public helpers
accept in-memory frames so unit tests and notebooks can reuse the calculations without I/O.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.features.panel.global_session_relay import DEFAULT_CLUSTERS, DEFAULT_SESSIONS

DEFAULT_ASSETS = [
    "AUS200", "BRENT", "ETHUSD", "EU50", "EURUSD", "FRA40", "GER40", "NIKKEI225", "SPX500",
    "UK100", "US30", "US100", "USOIL", "XAGUSD", "XAUUSD",
]


def _minutes(value: str, *, allow_24: bool = False) -> int:
    hour, minute = (int(part) for part in value.split(":"))
    if allow_24 and hour == 24 and minute == 0:
        return 1440
    return hour * 60 + minute


def load_cleaned_asset_frame(input_dir: Path, asset: str) -> tuple[pd.DataFrame, bool]:
    path = input_dir / f"{asset.lower()}_30m.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing configured Dukascopy CSV for {asset}: {path}")
    raw = pd.read_csv(path)
    raw.columns = [str(column).strip().lower() for column in raw.columns]
    if "timestamp" not in raw:
        raise ValueError(f"{path} is missing timestamp column.")
    parsed = pd.to_datetime(raw["timestamp"], errors="raise")
    timezone_aware = getattr(parsed.dt, "tz", None) is not None
    frame = raw.copy()
    frame.index = pd.DatetimeIndex(parsed)
    frame.index.name = "timestamp"
    return frame, bool(timezone_aware)


def asset_coverage_row(asset: str, frame: pd.DataFrame, *, timezone_aware_input: bool, interval_minutes: int) -> dict[str, Any]:
    index = pd.DatetimeIndex(frame.index).sort_values()
    gaps = index.to_series().diff().dt.total_seconds().div(60.0).dropna()
    expected_slots = int((index[-1] - index[0]).total_seconds() // (interval_minutes * 60) + 1) if len(index) else 0
    spread = pd.to_numeric(frame.get("spread_bps", pd.Series(dtype=float)), errors="coerce")
    return {
        "asset": asset,
        "first_timestamp": index.min() if len(index) else pd.NaT,
        "last_timestamp": index.max() if len(index) else pd.NaT,
        "row_count": int(len(frame)),
        "duplicate_timestamp_count": int(index.duplicated().sum()),
        "timezone_aware_input": bool(timezone_aware_input),
        "median_gap_minutes": float(gaps.median()) if not gaps.empty else np.nan,
        "p90_gap_minutes": float(gaps.quantile(0.90)) if not gaps.empty else np.nan,
        "p99_gap_minutes": float(gaps.quantile(0.99)) if not gaps.empty else np.nan,
        "maximum_gap_minutes": float(gaps.max()) if not gaps.empty else np.nan,
        "expected_30m_slots_between_first_last": expected_slots,
        "observed_slot_ratio": float(len(frame) / expected_slots) if expected_slots else np.nan,
        "spread_bps_median": float(spread.median()) if spread.notna().any() else np.nan,
        "spread_bps_p90": float(spread.quantile(0.90)) if spread.notna().any() else np.nan,
        "spread_bps_p99": float(spread.quantile(0.99)) if spread.notna().any() else np.nan,
    }


def asset_gap_diagnostics(asset: str, frame: pd.DataFrame, *, interval_minutes: int) -> pd.DataFrame:
    index = pd.DatetimeIndex(frame.index).sort_values()
    result = pd.DataFrame({"timestamp": index, "previous_timestamp": index.to_series().shift(1).to_numpy()})
    result["asset"] = asset
    result["gap_minutes"] = (result["timestamp"] - result["previous_timestamp"]).dt.total_seconds() / 60.0
    result["is_gap"] = result["gap_minutes"] > float(interval_minutes)
    return result.loc[result["is_gap"], ["asset", "previous_timestamp", "timestamp", "gap_minutes", "is_gap"]]


def asset_session_diagnostics(asset: str, frame: pd.DataFrame) -> dict[str, Any]:
    spec = DEFAULT_SESSIONS[asset]
    index = pd.DatetimeIndex(frame.index)
    utc = index.tz_localize("UTC") if index.tz is None else index.tz_convert("UTC")
    local = utc.tz_convert(ZoneInfo(spec["timezone"]))
    minute = local.hour * 60 + local.minute
    opening, closing = _minutes(spec["open"]), _minutes(spec["close"], allow_24=True)
    inside = (minute >= opening) & (minute < closing) if opening < closing else ((minute >= opening) | (minute < closing))
    return {
        "asset": asset,
        "timezone": spec["timezone"],
        "session_open": spec["open"],
        "session_close": spec["close"],
        "row_count": int(len(frame)),
        "primary_session_row_count": int(np.sum(inside)),
        "primary_session_ratio": float(np.mean(inside)) if len(inside) else np.nan,
    }


def pairwise_overlap_rows(frames: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    names = sorted(frames)
    for left_index, asset_a in enumerate(names):
        index_a = pd.DatetimeIndex(frames[asset_a].index)
        for asset_b in names[left_index + 1 :]:
            index_b = pd.DatetimeIndex(frames[asset_b].index)
            common = index_a.intersection(index_b)
            start = max(index_a.min(), index_b.min())
            end = min(index_a.max(), index_b.max())
            a_in_range = int(((index_a >= start) & (index_a <= end)).sum()) if start <= end else 0
            b_in_range = int(((index_b >= start) & (index_b <= end)).sum()) if start <= end else 0
            rows.append({
                "asset_a": asset_a, "asset_b": asset_b, "overlap_start": start if start <= end else pd.NaT,
                "overlap_end": end if start <= end else pd.NaT, "same_timestamp_rows": int(len(common)),
                "asset_a_rows_in_overlap": a_in_range, "asset_b_rows_in_overlap": b_in_range,
                "asset_a_overlap_ratio": float(len(common) / a_in_range) if a_in_range else np.nan,
                "asset_b_overlap_ratio": float(len(common) / b_in_range) if b_in_range else np.nan,
            })
    return pd.DataFrame(rows)


def cluster_coverage_rows(frames: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for cluster, spec in DEFAULT_CLUSTERS.items():
        assets = [asset for asset in spec["assets"] if asset in frames]
        union = pd.DatetimeIndex([])
        for asset in assets:
            union = union.union(pd.DatetimeIndex(frames[asset].index))
        active = pd.DataFrame({asset: union.isin(frames[asset].index) for asset in assets}, index=union)
        eligible = active.sum(axis=1) >= int(spec["minimum_active_assets"])
        if bool(spec["require_all_assets"]):
            eligible &= active.sum(axis=1) == len(spec["assets"])
        found = eligible[eligible]
        rows.append({
            "cluster": cluster, "eligible_start": found.index.min() if not found.empty else pd.NaT,
            "eligible_end": found.index.max() if not found.empty else pd.NaT,
            "eligible_timestamp_count": int(found.sum()), "minimum_active_assets": int(spec["minimum_active_assets"]),
            "require_all_assets": bool(spec["require_all_assets"]), "configured_assets": ",".join(spec["assets"]),
        })
    return pd.DataFrame(rows)


def module_coverage_rows(cluster_coverage: pd.DataFrame, frames: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    lookup = cluster_coverage.set_index("cluster")["eligible_timestamp_count"].to_dict()
    europe_sources = [asset for asset in DEFAULT_CLUSTERS["europe"]["assets"] if asset in frames]
    usa_targets = [asset for asset in DEFAULT_CLUSTERS["usa"]["assets"] if asset in frames]
    asia_sources = [asset for asset in DEFAULT_CLUSTERS["asia"]["assets"] if asset in frames]
    europe_targets = [asset for asset in DEFAULT_CLUSTERS["europe"]["assets"] if asset in frames]
    macro_present = {"ETHUSD", "XAUUSD", "BRENT"}.issubset(frames)
    return pd.DataFrame([
        {"module": "intra_europe", "eligible_timestamp_count": int(lookup.get("europe", 0))},
        {"module": "intra_usa", "eligible_timestamp_count": int(lookup.get("usa", 0))},
        {"module": "intra_energy", "eligible_timestamp_count": int(lookup.get("energy", 0))},
        {"module": "intra_metals", "eligible_timestamp_count": int(lookup.get("metals", 0))},
        {"module": "asia_to_europe", "eligible_timestamp_count": int(min([len(frames[a]) for a in asia_sources + europe_targets], default=0))},
        {"module": "europe_to_usa", "eligible_timestamp_count": int(min([len(frames[a]) for a in europe_sources + usa_targets], default=0))},
        {"module": "macro_context", "eligible_timestamp_count": int(min([len(frames[a]) for a in ("ETHUSD", "XAUUSD", "BRENT")], default=0)) if macro_present else 0},
    ])


def run_coverage_audit(
    *, input_dir: Path, output_dir: Path, assets: Sequence[str] = DEFAULT_ASSETS, interval_minutes: int = 30
) -> dict[str, Any]:
    frames: dict[str, pd.DataFrame] = {}
    coverage_rows: list[dict[str, Any]] = []
    gap_frames: list[pd.DataFrame] = []
    session_rows: list[dict[str, Any]] = []
    for asset in assets:
        frame, timezone_aware = load_cleaned_asset_frame(input_dir, asset)
        frames[asset] = frame
        coverage_rows.append(asset_coverage_row(asset, frame, timezone_aware_input=timezone_aware, interval_minutes=interval_minutes))
        gap_frames.append(asset_gap_diagnostics(asset, frame, interval_minutes=interval_minutes))
        session_rows.append(asset_session_diagnostics(asset, frame))
    output_dir.mkdir(parents=True, exist_ok=True)
    coverage = pd.DataFrame(coverage_rows)
    gaps = pd.concat(gap_frames, ignore_index=True) if gap_frames else pd.DataFrame()
    sessions = pd.DataFrame(session_rows)
    pairs = pairwise_overlap_rows(frames)
    clusters = cluster_coverage_rows(frames)
    modules = module_coverage_rows(clusters, frames)
    tables = {
        "asset_coverage.csv": coverage, "asset_gap_diagnostics.csv": gaps,
        "asset_session_diagnostics.csv": sessions, "pairwise_overlap.csv": pairs,
        "cluster_coverage.csv": clusters, "module_coverage.csv": modules,
    }
    for name, table in tables.items():
        table.to_csv(output_dir / name, index=False)
    summary = {
        "assets": list(assets), "interval_minutes": int(interval_minutes), "asset_count": len(frames),
        "total_rows": int(sum(len(frame) for frame in frames.values())), "gap_count": int(len(gaps)),
        "cluster_coverage": clusters.to_dict(orient="records"), "module_coverage": modules.to_dict(orient="records"),
    }
    with (output_dir / "coverage_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, default=str)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", default="data/raw/dukascopy_30m_clean")
    parser.add_argument("--output-dir", default="reports/global_session_relay_coverage")
    parser.add_argument("--assets", default=",".join(DEFAULT_ASSETS), help="Comma-separated asset symbols.")
    parser.add_argument("--interval-minutes", type=int, default=30)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    assets = [asset.strip() for asset in args.assets.split(",") if asset.strip()]
    run_coverage_audit(
        input_dir=Path(args.input_dir), output_dir=Path(args.output_dir), assets=assets,
        interval_minutes=args.interval_minutes,
    )


if __name__ == "__main__":
    main()
