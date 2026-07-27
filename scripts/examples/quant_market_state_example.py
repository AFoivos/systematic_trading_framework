#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.features.systems import HARVolatilityForecaster, add_quant_market_state_features


def _synthetic_m1(rows: int) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=rows, freq="min", tz="UTC")
    position = np.arange(rows, dtype=float)
    local_scale = 1.5e-5 * (1.0 + 0.65 * (position >= rows * 0.60))
    log_return = (
        2.0e-6
        + local_scale * np.sin(position / 7.0)
        + 0.5 * local_scale * np.cos(position / 19.0)
    )
    close = 1.10 * np.exp(np.cumsum(log_return))
    open_ = np.r_[close[0], close[:-1]]
    half_range = close * (2.0e-5 + local_scale)
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + half_range,
            "low": np.minimum(open_, close) - half_range,
            "close": close,
            "spread_bps": 0.8 + 0.15 * (1.0 + np.sin(position / 31.0)),
            "tick_volume": 100.0 + (position % 80.0),
        },
        index=index,
    )


def _load_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    timestamp_column = next(
        (column for column in ("timestamp", "time", "datetime") if column in frame.columns),
        None,
    )
    if timestamp_column is None:
        raise ValueError("CSV must contain timestamp, time, or datetime.")
    timestamps = pd.to_datetime(frame.pop(timestamp_column), utc=True, errors="raise")
    frame.index = pd.DatetimeIndex(timestamps)
    return frame


def run_example(
    *,
    csv_path: Path | None,
    rows: int,
    preset: str,
) -> tuple[pd.DataFrame, pd.Series]:
    raw = _load_csv(csv_path) if csv_path is not None else _synthetic_m1(rows)
    featured = add_quant_market_state_features(raw, preset=preset)

    split = max(300, int(len(featured) * 0.70))
    if split >= len(featured):
        raise ValueError("Example needs enough rows for separate HAR train and validation folds.")
    har = HARVolatilityForecaster(horizon=15, windows=(5, 15, 60, 240))
    har.fit(featured.iloc[:split])
    # Pass the full causal feature history to transform so the first validation
    # row can use trailing training-fold observations without any refit.
    har_validation_forecast = har.transform(featured).iloc[split:]
    return featured, har_validation_forecast


def main() -> int:
    parser = argparse.ArgumentParser(
        description="End-to-end causal KDS/RLVS/LMDS example for M1 OHLC or bid/ask CSV data."
    )
    parser.add_argument("--csv", type=Path, default=None, help="Optional input CSV.")
    parser.add_argument("--rows", type=int, default=5_000, help="Synthetic rows when --csv is omitted.")
    parser.add_argument(
        "--preset",
        choices=("conservative", "balanced", "responsive"),
        default="balanced",
    )
    args = parser.parse_args()
    if args.rows < 400:
        parser.error("--rows must be >= 400.")

    featured, har_forecast = run_example(
        csv_path=args.csv,
        rows=args.rows,
        preset=args.preset,
    )
    selected = [
        "qms_trend",
        "qms_trend_confidence",
        "qms_volatility",
        "qms_volatility_shock",
        "qms_momentum",
        "qms_momentum_quality",
        "qms_trend_momentum_alignment",
        "qms_state_uncertainty",
    ]
    print(featured[selected].tail(5).to_string())
    print(
        f"\nrows={len(featured):,} system_columns={len(featured.columns)} "
        f"har_validation_forecasts={int(har_forecast.notna().sum()):,}"
    )
    print("All displayed bar-t features assume execution no earlier than the next executable bar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
