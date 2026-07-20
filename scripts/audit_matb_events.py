from __future__ import annotations

"""Causal pre-ML event-count audit for Multi-Asset Trend Breakout."""

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.features.multi_asset_trend_breakout import add_multi_asset_trend_breakout_features
from src.models.matb_event_samples import evaluate_matb_sample_gate


UNIVERSE = {
    "SPX500": "data/raw/dukascopy_30m_clean/spx500_30m.csv",
    "US100": "data/raw/dukascopy_30m_clean/us100_30m.csv",
    "GER40": "data/raw/dukascopy_30m_clean/ger40_30m.csv",
    "NIKKEI225": "data/raw/dukascopy_30m_clean/nikkei225_30m.csv",
    "XAUUSD": "data/raw/dukascopy_30m_clean/xauusd_30m.csv",
    "XAGUSD": "data/raw/dukascopy_30m_clean/xagusd_30m.csv",
    "USOIL": "data/raw/dukascopy_30m_clean/usoil_30m.csv",
    "BRENT": "data/raw/dukascopy_30m_clean/brent_30m.csv",
    "EURUSD": "data/raw/dukascopy_30m_clean/eurusd_30m.csv",
    "ETHUSD": "data/raw/dukascopy_30m_clean/ethusd_30m.csv",
}

ASSET_GROUPS = {
    "SPX500": "equity_indices",
    "US100": "equity_indices",
    "GER40": "equity_indices",
    "NIKKEI225": "equity_indices",
    "XAUUSD": "metals",
    "XAGUSD": "metals",
    "USOIL": "energy",
    "BRENT": "energy",
    "EURUSD": "fx",
    "ETHUSD": "crypto",
}

BID_ASK_COLUMNS = (
    "bid_open",
    "bid_high",
    "bid_low",
    "bid_close",
    "ask_open",
    "ask_high",
    "ask_low",
    "ask_close",
)


def _load_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["timestamp"])
    timestamps = pd.DatetimeIndex(frame.pop("timestamp"))
    frame.index = timestamps.tz_localize("UTC") if timestamps.tz is None else timestamps.tz_convert("UTC")
    frame.index.name = "timestamp"
    return frame.sort_index()


def run_event_audit(
    *,
    repository_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    asset_rows: list[dict[str, Any]] = []
    asset_year_rows: list[dict[str, Any]] = []
    event_rows: list[pd.DataFrame] = []

    for asset, relative_path in UNIVERSE.items():
        source = repository_root / relative_path
        if not source.exists():
            raise FileNotFoundError(f"MATB audit source is missing: {source}")
        raw = _load_frame(source)
        featured = add_multi_asset_trend_breakout_features(raw)
        candidates = featured.loc[featured["matb_candidate"].eq(1), ["matb_side"]].copy()
        candidates["asset"] = asset
        candidates["asset_group"] = ASSET_GROUPS[asset]
        candidates["year"] = candidates.index.year.astype(int)
        candidates["side"] = candidates["matb_side"].map({1: "long", -1: "short"})
        event_rows.append(candidates.reset_index())

        by_year = (
            candidates.groupby("year", observed=True)["matb_side"]
            .agg(
                long_candidates=lambda values: int(values.eq(1).sum()),
                short_candidates=lambda values: int(values.eq(-1).sum()),
                total_candidates="size",
            )
            .reset_index()
        )
        for row in by_year.to_dict(orient="records"):
            asset_year_rows.append({"asset": asset, "asset_group": ASSET_GROUPS[asset], **row})

        gaps = raw.index.to_series().diff().gt(pd.Timedelta(minutes=30))
        missing_quote_fields = [column for column in BID_ASK_COLUMNS if column not in raw.columns]
        median_spread = (
            float(pd.to_numeric(raw["spread_bps"], errors="coerce").median())
            if "spread_bps" in raw.columns
            else None
        )
        year_counts = {
            str(int(row["year"])): int(row["total_candidates"])
            for row in by_year.to_dict(orient="records")
        }
        asset_rows.append(
            {
                "scope": "asset",
                "asset": asset,
                "asset_group": ASSET_GROUPS[asset],
                "input_rows": int(len(raw)),
                "first_timestamp": raw.index.min().isoformat(),
                "last_timestamp": raw.index.max().isoformat(),
                "missing_bar_gap_count": int(gaps.sum()),
                "long_candidates": int(candidates["matb_side"].eq(1).sum()),
                "short_candidates": int(candidates["matb_side"].eq(-1).sum()),
                "total_candidates": int(len(candidates)),
                "candidates_per_year": json.dumps(year_counts, sort_keys=True),
                "median_spread_bps": median_spread,
                "missing_bid_ask_field_count": int(len(missing_quote_fields)),
                "missing_bid_ask_fields": ",".join(missing_quote_fields),
            }
        )

    events = pd.concat(event_rows, ignore_index=True) if event_rows else pd.DataFrame()
    total_candidates = int(len(events))
    asset_counts = events.groupby("asset", observed=True).size() if total_candidates else pd.Series(dtype=float)
    group_counts = events.groupby("asset_group", observed=True).size() if total_candidates else pd.Series(dtype=float)
    portfolio_year_counts = (
        {str(int(key)): int(value) for key, value in events.groupby("year", observed=True).size().items()}
        if total_candidates
        else {}
    )
    portfolio_group_counts = (
        {str(key): int(value) for key, value in group_counts.items()} if total_candidates else {}
    )
    asset_rows.append(
        {
            "scope": "portfolio",
            "asset": "__PORTFOLIO__",
            "asset_group": "all",
            "input_rows": int(sum(row["input_rows"] for row in asset_rows)),
            "first_timestamp": min(row["first_timestamp"] for row in asset_rows),
            "last_timestamp": max(row["last_timestamp"] for row in asset_rows),
            "missing_bar_gap_count": int(sum(row["missing_bar_gap_count"] for row in asset_rows)),
            "long_candidates": int(events["matb_side"].eq(1).sum()) if total_candidates else 0,
            "short_candidates": int(events["matb_side"].eq(-1).sum()) if total_candidates else 0,
            "total_candidates": total_candidates,
            "candidates_per_year": json.dumps(portfolio_year_counts, sort_keys=True),
            "median_spread_bps": None,
            "missing_bid_ask_field_count": int(
                sum(row["missing_bid_ask_field_count"] for row in asset_rows)
            ),
            "missing_bid_ask_fields": "",
            "candidates_per_group": json.dumps(portfolio_group_counts, sort_keys=True),
            "maximum_asset_sample_share": (
                float(asset_counts.max() / total_candidates) if total_candidates else None
            ),
            "maximum_group_sample_share": (
                float(group_counts.max() / total_candidates) if total_candidates else None
            ),
        }
    )

    by_group_side = (
        events.groupby(["asset_group", "side"], observed=True)
        .size()
        .rename("total_candidates")
        .reset_index()
        .sort_values(["asset_group", "side"])
        if total_candidates
        else pd.DataFrame(columns=["asset_group", "side", "total_candidates"])
    )
    asset_year = pd.DataFrame(asset_year_rows).sort_values(["asset", "year"])
    audit = pd.DataFrame(asset_rows)

    output_dir.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output_dir / "matb_event_audit.csv", index=False)
    asset_year.to_csv(output_dir / "matb_events_by_asset_year.csv", index=False)
    by_group_side.to_csv(output_dir / "matb_events_by_group_side.csv", index=False)
    asset_year.to_csv(output_dir / "candidate_counts_by_asset_year.csv", index=False)
    by_group_side.to_csv(output_dir / "candidate_counts_by_group_side.csv", index=False)
    gate_events = events.rename(columns={"timestamp": "event_start_timestamp"}).copy()
    gate_events["event_end_timestamp"] = gate_events["event_start_timestamp"]
    gate_events["side"] = gate_events["matb_side"]
    sample_gate = evaluate_matb_sample_gate(gate_events).to_dict()
    sample_gate["audit_stage"] = "pre_target_global_gate"
    sample_gate["fold_checks_evaluated"] = False
    sample_gate["fold_checks_reason"] = (
        "Global immutable gates already fail; ML fold construction and model fitting are "
        "prohibited. Deterministic strategy-path target diagnostics remain permitted."
    )
    (output_dir / "matb_ml_sample_gate.json").write_text(
        json.dumps(sample_gate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "total_candidates": total_candidates,
        "total_long": int(events["matb_side"].eq(1).sum()) if total_candidates else 0,
        "total_short": int(events["matb_side"].eq(-1).sum()) if total_candidates else 0,
        "maximum_asset_sample_share": (
            float(asset_counts.max() / total_candidates) if total_candidates else None
        ),
        "maximum_group_sample_share": (
            float(group_counts.max() / total_candidates) if total_candidates else None
        ),
        "ml_sample_gate": sample_gate["status"],
        "output_dir": str(output_dir),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="logs/experiments/matb/audit",
        help="Directory for MATB event-audit CSV files.",
    )
    args = parser.parse_args()
    result = run_event_audit(
        repository_root=REPOSITORY_ROOT,
        output_dir=(REPOSITORY_ROOT / args.output_dir).resolve(),
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
