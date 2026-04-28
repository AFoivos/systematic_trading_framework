#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import pandas as pd


ASSETS = ("xauusd", "us100", "us30", "spx500", "ger40")
SIDES = ("bid", "ask")
TIMESTAMP_CANDIDATES = (
    "timestamp",
    "Timestamp",
    "datetime",
    "Datetime",
    "date",
    "Date",
    "time",
    "Time",
    "local_time",
    "Local time",
)


def _quarterly_paths(input_root: Path, asset: str, side: str) -> list[Path]:
    pattern = f"{asset}_30m_{side}.csv"
    return sorted(path for path in input_root.glob("*_Q[1-4]/" + pattern) if path.is_file())


def _timestamp_column(df: pd.DataFrame, path: Path) -> str:
    for candidate in TIMESTAMP_CANDIDATES:
        if candidate in df.columns:
            return candidate
    raise ValueError(f"{path} has no supported timestamp column. Columns: {list(df.columns)}")


def _read_quarterly_csv(path: Path) -> pd.DataFrame | None:
    if path.stat().st_size == 0:
        warnings.warn(f"Skipping empty file: {path}", RuntimeWarning, stacklevel=2)
        return None

    try:
        df = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001
        warnings.warn(f"Skipping unreadable file {path}: {exc}", RuntimeWarning, stacklevel=2)
        return None

    if df.empty:
        warnings.warn(f"Skipping CSV with zero rows: {path}", RuntimeWarning, stacklevel=2)
        return None

    try:
        ts_col = _timestamp_column(df, path)
        parsed = pd.to_datetime(df[ts_col], errors="raise", utc=True)
    except Exception as exc:  # noqa: BLE001
        warnings.warn(f"Skipping file with unparseable timestamps {path}: {exc}", RuntimeWarning, stacklevel=2)
        return None

    out = df.copy()
    out["timestamp"] = parsed.dt.tz_convert("UTC").dt.tz_localize(None)
    if ts_col != "timestamp":
        out = out.drop(columns=[ts_col])
    ordered_columns = ["timestamp"] + [col for col in out.columns if col != "timestamp"]

    return out[ordered_columns]


def merge_asset_side(input_root: Path, output_dir: Path, asset: str, side: str) -> Path:
    paths = _quarterly_paths(input_root, asset, side)
    if not paths:
        raise FileNotFoundError(f"{asset}_{side}: zero available quarterly files under {input_root}")

    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = _read_quarterly_csv(path)
        if frame is not None:
            frames.append(frame)

    if not frames:
        raise FileNotFoundError(f"{asset}_{side}: zero readable quarterly files under {input_root}")

    merged = pd.concat(frames, ignore_index=True, sort=False)
    merged = merged.sort_values("timestamp", kind="mergesort")
    merged = merged.drop_duplicates(subset=["timestamp"], keep="last").reset_index(drop=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{asset}_30m_{side}.csv"
    merged.to_csv(output_path, index=False, date_format="%Y-%m-%d %H:%M:%S")

    first_ts = merged["timestamp"].iloc[0].strftime("%Y-%m-%d %H:%M:%S")
    last_ts = merged["timestamp"].iloc[-1].strftime("%Y-%m-%d %H:%M:%S")
    print(f"{asset}_{side}: wrote {len(merged)} rows to {output_path} | first={first_ts} | last={last_ts}")
    return output_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge quarterly Dukascopy 30m BID/ASK CSV files.")
    parser.add_argument("--input-root", default="data/raw/dukascopy_quarterly")
    parser.add_argument("--output-dir", default="data/raw/dukascopy_30m")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_root = Path(args.input_root)
    output_dir = Path(args.output_dir)

    for asset in ASSETS:
        for side in SIDES:
            merge_asset_side(input_root, output_dir, asset, side)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
