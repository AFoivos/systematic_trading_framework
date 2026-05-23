#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any, Literal

import pandas as pd


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
REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")
PRICE_COLUMNS = ("open", "high", "low", "close")


def _timestamp_column(df: pd.DataFrame, path: Path) -> str:
    for candidate in TIMESTAMP_CANDIDATES:
        if candidate in df.columns:
            return candidate
    raise ValueError(f"{path} has no supported timestamp column. Columns: {list(df.columns)}")


def _normalize_timestamp(values: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(values, errors="raise", utc=True)
    return parsed.dt.tz_convert("UTC").dt.tz_localize(None)


def _monthly_paths(input_root: Path, file_name: str) -> list[Path]:
    return sorted(path for path in input_root.glob(f"????-??/{file_name}") if path.is_file())


def _read_monthly_csv(path: Path) -> pd.DataFrame | None:
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

    ts_col = _timestamp_column(df, path)
    out = df.copy()
    out["timestamp"] = _normalize_timestamp(out[ts_col])
    if ts_col != "timestamp":
        out = out.drop(columns=[ts_col])

    out.columns = [str(col).strip().lower() for col in out.columns]
    missing = [col for col in REQUIRED_COLUMNS if col not in out.columns]
    if missing:
        raise ValueError(f"{path} missing required columns: {missing}")

    out = out[list(REQUIRED_COLUMNS)]
    for col in REQUIRED_COLUMNS:
        if col != "timestamp":
            out[col] = pd.to_numeric(out[col], errors="raise")

    return out


def _is_expected_fx_timestamp(ts: pd.Timestamp) -> bool:
    weekday = ts.weekday()
    if weekday in {0, 1, 2, 3}:
        return True
    if weekday == 4:
        return ts.hour < 22
    if weekday == 6:
        return ts.hour >= 22
    return False


def _expected_index(
    start: pd.Timestamp,
    end: pd.Timestamp,
    *,
    freq: str,
    calendar: Literal["fx_24x5", "all"],
) -> pd.DatetimeIndex:
    if end <= start:
        return pd.DatetimeIndex([], name="timestamp")

    step = pd.Timedelta(freq)
    expected = pd.date_range(start=start, end=end - step, freq=freq, name="timestamp")
    if calendar == "all" or expected.empty:
        return expected

    keep = [_is_expected_fx_timestamp(ts) for ts in expected]
    return expected[keep]


def _compact_missing_ranges(
    missing: pd.DatetimeIndex,
    *,
    freq: str,
    max_ranges: int,
) -> tuple[list[dict[str, Any]], int]:
    if missing.empty:
        return [], 0

    step = pd.Timedelta(freq)
    ranges: list[dict[str, Any]] = []
    run_start = missing[0]
    previous = missing[0]
    count = 1

    for ts in missing[1:]:
        if ts - previous == step:
            previous = ts
            count += 1
            continue
        ranges.append({"start": run_start.isoformat(), "end": previous.isoformat(), "missing_count": count})
        run_start = ts
        previous = ts
        count = 1

    ranges.append({"start": run_start.isoformat(), "end": previous.isoformat(), "missing_count": count})
    omitted = max(0, len(ranges) - max_ranges)
    return ranges[:max_ranges], omitted


def detect_missing_intervals(
    df: pd.DataFrame,
    *,
    freq: str,
    calendar: Literal["fx_24x5", "all"],
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
    max_examples: int = 50,
    max_ranges: int = 100,
) -> dict[str, Any]:
    if df.empty:
        raise ValueError("Cannot detect gaps on an empty dataframe.")

    start_ts = pd.Timestamp(start) if start is not None else pd.Timestamp(df["timestamp"].iloc[0])
    end_ts = pd.Timestamp(end) if end is not None else pd.Timestamp(df["timestamp"].iloc[-1]) + pd.Timedelta(freq)
    expected = _expected_index(start_ts, end_ts, freq=freq, calendar=calendar)
    actual = pd.DatetimeIndex(df["timestamp"].drop_duplicates(), name="timestamp")
    actual = actual[(actual >= start_ts) & (actual < end_ts)]
    missing = expected.difference(actual)
    unexpected = actual.difference(expected)
    missing_ranges, omitted_missing_ranges = _compact_missing_ranges(missing, freq=freq, max_ranges=max_ranges)

    return {
        "start": start_ts.isoformat(),
        "end_exclusive": end_ts.isoformat(),
        "freq": freq,
        "calendar": calendar,
        "expected_count": int(len(expected)),
        "actual_count": int(len(actual)),
        "missing_count": int(len(missing)),
        "unexpected_count": int(len(unexpected)),
        "missing_examples": [ts.isoformat() for ts in missing[:max_examples]],
        "unexpected_examples": [ts.isoformat() for ts in unexpected[:max_examples]],
        "missing_ranges": missing_ranges,
        "omitted_missing_ranges": omitted_missing_ranges,
    }


def validate_data(df: pd.DataFrame, *, freq: str, calendar: Literal["fx_24x5", "all"]) -> dict[str, Any]:
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Merged dataset missing required columns: {missing}")
    if df.empty:
        raise ValueError("Merged dataset is empty.")
    if not df["timestamp"].is_monotonic_increasing:
        raise ValueError("Merged timestamps are not sorted.")
    if df["timestamp"].duplicated().any():
        raise ValueError("Merged timestamps contain duplicates.")

    for col in REQUIRED_COLUMNS:
        if col == "timestamp":
            continue
        if df[col].isna().any():
            raise ValueError(f"Merged dataset contains NaNs in {col}.")

    if (df["low"] > df["high"]).any():
        raise ValueError("Merged dataset contains rows with low > high.")
    if ((df["open"] < df["low"]) | (df["open"] > df["high"])).any():
        raise ValueError("Merged dataset contains rows with open outside [low, high].")
    if ((df["close"] < df["low"]) | (df["close"] > df["high"])).any():
        raise ValueError("Merged dataset contains rows with close outside [low, high].")
    if (df["volume"] < 0).any():
        raise ValueError("Merged dataset contains negative volume.")

    step_ns = pd.Timedelta(freq).value
    timestamp_ns = df["timestamp"].astype("int64")
    off_grid = (timestamp_ns % step_ns) != 0
    if off_grid.any():
        raise ValueError(f"Merged dataset contains {int(off_grid.sum())} off-grid timestamps for freq={freq}.")

    gap_report = detect_missing_intervals(df, freq=freq, calendar=calendar)
    return {
        "rows": int(len(df)),
        "first_timestamp": df["timestamp"].iloc[0].isoformat(),
        "last_timestamp": df["timestamp"].iloc[-1].isoformat(),
        "gap_report": gap_report,
    }


def merge_monthly_files(
    *,
    input_root: Path,
    output_path: Path,
    gap_report_path: Path,
    file_name: str,
    freq: str,
    calendar: Literal["fx_24x5", "all"],
    output_format: Literal["csv", "parquet"],
) -> Path:
    paths = _monthly_paths(input_root, file_name)
    if not paths:
        raise FileNotFoundError(f"Zero monthly files found under {input_root} matching */{file_name}")

    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = _read_monthly_csv(path)
        if frame is not None:
            frames.append(frame)

    if not frames:
        raise FileNotFoundError(f"Zero readable monthly files found under {input_root}")

    merged = pd.concat(frames, ignore_index=True, sort=False)
    before_dedup = len(merged)
    merged = merged.sort_values("timestamp", kind="mergesort")
    merged = merged.drop_duplicates(subset=["timestamp"], keep="last").reset_index(drop=True)
    validation = validate_data(merged, freq=freq, calendar=calendar)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "parquet":
        merged.to_parquet(output_path, index=False, compression="snappy")
    else:
        merged.to_csv(output_path, index=False, date_format="%Y-%m-%d %H:%M:%S")

    gap_report = {
        "input_root": str(input_root),
        "file_name": file_name,
        "output_path": str(output_path),
        "output_format": output_format,
        "source_files": [str(path) for path in paths],
        "source_file_count": len(paths),
        "rows_before_dedup": int(before_dedup),
        "rows_after_dedup": int(len(merged)),
        "duplicate_rows_removed": int(before_dedup - len(merged)),
        "validation": validation,
    }
    gap_report_path.parent.mkdir(parents=True, exist_ok=True)
    with gap_report_path.open("w", encoding="utf-8") as handle:
        json.dump(gap_report, handle, indent=2, sort_keys=True)

    print(
        f"wrote {len(merged)} rows to {output_path} | "
        f"first={validation['first_timestamp']} | "
        f"last={validation['last_timestamp']} | "
        f"missing={validation['gap_report']['missing_count']} | "
        f"gap_report={gap_report_path}"
    )
    return output_path


def _infer_output_format(path: Path, explicit: str | None) -> Literal["csv", "parquet"]:
    if explicit is not None:
        if explicit not in {"csv", "parquet"}:
            raise ValueError("--output-format must be 'csv' or 'parquet'.")
        return explicit  # type: ignore[return-value]
    if path.suffix.lower() in {".parquet", ".pq"}:
        return "parquet"
    return "csv"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge monthly EURUSD Dukascopy M15 CSV chunks.")
    parser.add_argument("--input-root", default="data/raw/dukascopy/eurusd/m15/monthly")
    parser.add_argument("--file-name", default="eurusd_m15.csv")
    parser.add_argument("--output-path", default="data/processed/eurusd_m15_3y.csv")
    parser.add_argument("--gap-report-path", default=None)
    parser.add_argument("--freq", default="15min")
    parser.add_argument("--calendar", choices=("fx_24x5", "all"), default="fx_24x5")
    parser.add_argument("--output-format", choices=("csv", "parquet"), default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_root = Path(args.input_root)
    output_path = Path(args.output_path)
    gap_report_path = Path(args.gap_report_path) if args.gap_report_path else output_path.with_name(
        f"{output_path.stem}_gap_report.json"
    )
    output_format = _infer_output_format(output_path, args.output_format)
    merge_monthly_files(
        input_root=input_root,
        output_path=output_path,
        gap_report_path=gap_report_path,
        file_name=args.file_name,
        freq=args.freq,
        calendar=args.calendar,
        output_format=output_format,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
