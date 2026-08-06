#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import timezone
import json
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="CSV containing time/open/high/low/close/volume")
    parser.add_argument("--url", default="http://127.0.0.1:8765/predict")
    parser.add_argument("--bars", type=int, default=1500)
    parser.add_argument("--token", default="")
    args = parser.parse_args()

    frame = pd.read_csv(args.csv)
    time_col = next((c for c in ("time", "timestamp", "datetime", "date") if c in frame.columns), None)
    if time_col is None:
        raise SystemExit("CSV needs a time/timestamp/datetime/date column")
    frame = frame.tail(args.bars)
    bars = []
    for _, row in frame.iterrows():
        timestamp = pd.Timestamp(row[time_col])
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        else:
            timestamp = timestamp.tz_convert("UTC")
        bars.append({
            "time": timestamp.isoformat(),
            "open": float(row["open"]), "high": float(row["high"]),
            "low": float(row["low"]), "close": float(row["close"]),
            "volume": float(row.get("volume", row.get("tick_volume", 0.0))),
        })
    payload = json.dumps({
        "request_id": "smoke-test", "symbol": "ETHUSD", "timeframe": "M30",
        "allow_stale": True, "bars": bars,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if args.token:
        headers["X-Model06-Token"] = args.token
    request = Request(args.url, data=payload, headers=headers, method="POST")
    with urlopen(request, timeout=30) as response:
        print(response.read().decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
