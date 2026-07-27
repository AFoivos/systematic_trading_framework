"""Build a synchronized FTMO BTCUSD/ETHUSD H1 research dataset from cTrader M1 bars."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = (
    "timestamp_utc",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_and_validate_m1(path: Path, symbol: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = set(REQUIRED_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"{symbol}: missing required columns: {sorted(missing)}")

    frame = frame.loc[:, REQUIRED_COLUMNS].copy()
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True, errors="raise")
    if frame["timestamp_utc"].duplicated().any():
        raise ValueError(f"{symbol}: duplicate M1 timestamps detected.")
    if frame.isna().any().any():
        raise ValueError(f"{symbol}: null values detected.")
    if not frame["timestamp_utc"].is_monotonic_increasing:
        frame = frame.sort_values("timestamp_utc").reset_index(drop=True)

    prices = frame[["open", "high", "low", "close"]]
    if (prices <= 0.0).any().any():
        raise ValueError(f"{symbol}: non-positive prices detected.")
    invalid_ohlc = (frame["high"] < prices.max(axis=1)) | (frame["low"] > prices.min(axis=1))
    if invalid_ohlc.any():
        raise ValueError(f"{symbol}: {int(invalid_ohlc.sum())} invalid OHLC rows detected.")
    if (frame["tick_volume"] < 0.0).any():
        raise ValueError(f"{symbol}: negative tick volume detected.")
    return frame


def resample_h1(frame: pd.DataFrame, symbol: str, min_minutes_per_hour: int) -> pd.DataFrame:
    indexed = frame.set_index("timestamp_utc")
    hourly = indexed.resample("1h", closed="left", label="right").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        tick_volume=("tick_volume", "sum"),
        source_minutes=("close", "count"),
    )
    hourly = hourly.loc[hourly["source_minutes"] >= min_minutes_per_hour].copy()
    hourly.columns = [f"{symbol}_{column}" for column in hourly.columns]
    return hourly


def prepare_dataset(
    btc_path: Path,
    eth_path: Path,
    *,
    min_minutes_per_hour: int = 45,
) -> tuple[pd.DataFrame, dict[str, object]]:
    if not 1 <= min_minutes_per_hour <= 60:
        raise ValueError("min_minutes_per_hour must be between 1 and 60.")

    btc_m1 = load_and_validate_m1(btc_path, "btc")
    eth_m1 = load_and_validate_m1(eth_path, "eth")
    btc_h1 = resample_h1(btc_m1, "btc", min_minutes_per_hour)
    eth_h1 = resample_h1(eth_m1, "eth", min_minutes_per_hour)
    joined = btc_h1.join(eth_h1, how="inner").dropna().sort_index()
    if joined.empty:
        raise ValueError("No synchronized complete H1 bars remain after filtering.")
    if joined.index.duplicated().any():
        raise ValueError("Duplicate synchronized H1 timestamps detected.")

    joined["btc_log_close"] = np.log(joined["btc_close"])
    joined["eth_log_close"] = np.log(joined["eth_close"])
    joined["btc_log_return_1h"] = joined["btc_log_close"].diff()
    joined["eth_log_return_1h"] = joined["eth_log_close"].diff()
    joined["log_price_ratio"] = joined["btc_log_close"] - joined["eth_log_close"]
    joined.index.name = "timestamp_utc"

    manifest: dict[str, object] = {
        "dataset": "ftmo_ctrader_btc_eth_h1_synchronized",
        "timestamp_semantics": "UTC hour-end; each row uses M1 bars in [timestamp-1h, timestamp)",
        "min_minutes_per_hour": min_minutes_per_hour,
        "btc_m1_rows": len(btc_m1),
        "eth_m1_rows": len(eth_m1),
        "btc_h1_complete_rows": len(btc_h1),
        "eth_h1_complete_rows": len(eth_h1),
        "synchronized_h1_rows": len(joined),
        "start_utc": joined.index.min().isoformat(),
        "end_utc": joined.index.max().isoformat(),
        "btc_only_complete_hours": len(btc_h1.index.difference(eth_h1.index)),
        "eth_only_complete_hours": len(eth_h1.index.difference(btc_h1.index)),
    }
    return joined, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw/ctrader_ftmo"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/ftmo_relative_value"),
    )
    parser.add_argument("--min-minutes-per-hour", type=int, default=45)
    args = parser.parse_args()

    btc_path = args.raw_dir / "btcusd_m1.csv"
    eth_path = args.raw_dir / "ethusd_m1.csv"
    for path in (btc_path, eth_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    dataset, manifest = prepare_dataset(
        btc_path,
        eth_path,
        min_minutes_per_hour=args.min_minutes_per_hour,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = args.output_dir / "btc_eth_h1.csv"
    manifest_path = args.output_dir / "manifest.json"
    dataset.to_csv(dataset_path, float_format="%.10g")

    manifest.update(
        {
            "inputs": {
                "btcusd_m1": {"path": str(btc_path), "sha256": _sha256(btc_path)},
                "ethusd_m1": {"path": str(eth_path), "sha256": _sha256(eth_path)},
            },
            "output": {"path": str(dataset_path), "sha256": _sha256(dataset_path)},
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote={dataset_path} rows={len(dataset)} "
        f"range={manifest['start_utc']}..{manifest['end_utc']}"
    )


if __name__ == "__main__":
    main()

