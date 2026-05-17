#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import pandas as pd


REQUIRED_PRICE_COLUMNS = ("timestamp", "open", "high", "low", "close")
OUTPUT_COLUMNS = (
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "bid_open",
    "bid_high",
    "bid_low",
    "bid_close",
    "ask_open",
    "ask_high",
    "ask_low",
    "ask_close",
    "spread_close",
    "spread_bps",
)


def _read_side_csv(path: Path, *, side: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {side.upper()} file: {path}")

    df = pd.read_csv(path)
    missing = [col for col in REQUIRED_PRICE_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"{path} missing required columns: {missing}")

    out = df.copy()
    parsed = pd.to_datetime(out["timestamp"], errors="raise")
    if getattr(parsed.dt, "tz", None) is not None:
        parsed = parsed.dt.tz_convert("UTC").dt.tz_localize(None)
    out["timestamp"] = parsed

    keep = list(REQUIRED_PRICE_COLUMNS)
    if "volume" in out.columns:
        keep.append("volume")
    out = out[keep]
    for col in keep:
        if col != "timestamp":
            out[col] = pd.to_numeric(out[col], errors="coerce")

    out = out.sort_values("timestamp", kind="mergesort")
    out = out.drop_duplicates(subset=["timestamp"], keep="last")
    rename = {col: f"{side}_{col}" for col in keep if col != "timestamp"}
    return out.rename(columns=rename).reset_index(drop=True)


def _merge_bid_ask(
    bid: pd.DataFrame,
    ask: pd.DataFrame,
    *,
    label: str,
    max_bad_spread_rate: float,
) -> pd.DataFrame:
    joined = bid.merge(ask, on="timestamp", how="inner", validate="one_to_one")
    if joined.empty:
        raise ValueError(f"{label}: joined BID/ASK dataframe is empty.")

    for side in ("bid", "ask"):
        for col in ("open", "high", "low", "close"):
            joined[f"{side}_{col}"] = pd.to_numeric(joined[f"{side}_{col}"], errors="coerce")

    bad_spread = joined["ask_close"] < joined["bid_close"]
    bad_count = int(bad_spread.sum())
    if bad_count:
        bad_rate = bad_count / float(len(joined))
        msg = f"{label}: ask_close < bid_close on {bad_count}/{len(joined)} rows ({bad_rate:.4%})."
        if bad_rate > max_bad_spread_rate:
            raise ValueError(msg)
        warnings.warn(msg, RuntimeWarning, stacklevel=2)

    out = pd.DataFrame({"timestamp": joined["timestamp"]})
    for col in ("open", "high", "low", "close"):
        out[col] = (joined[f"bid_{col}"] + joined[f"ask_{col}"]) / 2.0

    bid_volume = joined["bid_volume"] if "bid_volume" in joined.columns else None
    ask_volume = joined["ask_volume"] if "ask_volume" in joined.columns else None
    if bid_volume is not None and ask_volume is not None:
        out["volume"] = pd.concat([bid_volume, ask_volume], axis=1).mean(axis=1, skipna=True).fillna(0.0)
    elif bid_volume is not None:
        out["volume"] = bid_volume.fillna(0.0)
    else:
        out["volume"] = 0.0

    for side in ("bid", "ask"):
        for col in ("open", "high", "low", "close"):
            out[f"{side}_{col}"] = joined[f"{side}_{col}"]

    out["spread_close"] = out["ask_close"] - out["bid_close"]
    out["spread_bps"] = out["spread_close"] / out["close"].where(out["close"] != 0.0)
    out = out[list(OUTPUT_COLUMNS)].sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    if out[["open", "high", "low", "close"]].isna().any().any():
        raise ValueError(f"{label}: canonical mid OHLC contains missing values after BID/ASK merge.")
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare one Dukascopy BID/ASK pair into an FTMO-style mid OHLCV CSV.")
    parser.add_argument("--bid-path", required=True)
    parser.add_argument("--ask-path", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--asset", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--max-bad-spread-rate", type=float, default=0.001)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_bad_spread_rate < 0.0:
        raise ValueError("--max-bad-spread-rate must be >= 0.")

    bid = _read_side_csv(Path(args.bid_path), side="bid")
    ask = _read_side_csv(Path(args.ask_path), side="ask")
    label = f"{args.asset}_{args.timeframe}"
    out = _merge_bid_ask(bid, ask, label=label, max_bad_spread_rate=float(args.max_bad_spread_rate))

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False, date_format="%Y-%m-%d %H:%M:%S")
    avg_spread_bps = float(out["spread_bps"].mean(skipna=True))
    print(f"{label}: wrote {len(out)} rows to {output_path} | avg spread_bps={avg_spread_bps:.8f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
