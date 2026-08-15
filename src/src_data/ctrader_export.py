from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from src.src_data.validation import validate_ohlcv
from src.utils.paths import PROJECT_ROOT, enforce_safe_absolute_path
from src.utils.run_metadata import compute_dataframe_fingerprint, file_sha256


BarTimestampConvention = Literal["bar_open"]


@dataclass(frozen=True)
class CTraderExport:
    """Canonical cTrader export plus the provenance needed to reproduce it."""

    frame: pd.DataFrame
    metadata: dict[str, Any]


def _resolve_export_path(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = (PROJECT_ROOT / candidate).resolve()
    candidate = enforce_safe_absolute_path(candidate)
    if not candidate.is_file():
        raise FileNotFoundError(f"cTrader export not found: {candidate}")
    if candidate.suffix.lower() != ".csv":
        raise ValueError("cTrader export path must point to a CSV file.")
    return candidate


def _normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.columns = [str(column).strip().lower() for column in out.columns]
    if len(set(out.columns)) != len(out.columns):
        raise ValueError("cTrader export has duplicate columns after normalization.")
    return out


def _utc_naive_index(values: pd.Series, *, source_timezone: str) -> pd.DatetimeIndex:
    parsed = pd.to_datetime(values, errors="raise")
    index = pd.DatetimeIndex(parsed)
    if index.tz is None:
        index = index.tz_localize(source_timezone)
    index = index.tz_convert("UTC").tz_localize(None)
    index.name = "timestamp"
    return index


def _base_metadata(
    *,
    path: Path,
    frame: pd.DataFrame,
    raw_rows: int,
    source_timezone: str,
    symbol: str,
) -> dict[str, Any]:
    return {
        "source": "ctrader_csv_export",
        "path": str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path),
        "file_sha256": file_sha256(path),
        "dataframe_fingerprint": compute_dataframe_fingerprint(frame),
        "symbol": symbol,
        "source_timezone": source_timezone,
        "output_timezone": "UTC",
        "canonical_index_timezone": "UTC-naive",
        "raw_rows": int(raw_rows),
        "canonical_rows": int(len(frame)),
        "timestamp_start": frame.index.min().isoformat() if not frame.empty else None,
        "timestamp_end": frame.index.max().isoformat() if not frame.empty else None,
    }


def load_ctrader_bar_export(
    path: str | Path,
    *,
    timeframe: str,
    expected_symbol: str = "ETHUSD",
    source_timezone: str = "UTC",
    timestamp_convention: BarTimestampConvention = "bar_open",
    drop_incomplete_tail: bool = True,
) -> CTraderExport:
    """Load one cTrader OHLC export into the project's canonical UTC-naive schema.

    cTrader bar timestamps are treated as bar-open timestamps.  The last exported
    row is removed by default because the collector can snapshot an active bar;
    this deterministic rule avoids relying on wall-clock time or future ticks.
    """

    if timestamp_convention != "bar_open":
        raise ValueError("Only timestamp_convention='bar_open' is supported.")
    if not str(timeframe).strip():
        raise ValueError("timeframe must be a non-empty string.")

    resolved = _resolve_export_path(path)
    raw = _normalize_columns(pd.read_csv(resolved))
    required = {"symbol", "time", "open", "high", "low", "close", "tick_volume"}
    missing = sorted(required.difference(raw.columns))
    if missing:
        raise ValueError(f"cTrader bar export is missing required columns: {missing}")
    if raw.empty:
        raise ValueError("cTrader bar export is empty.")

    symbols = raw["symbol"].astype(str).str.strip().str.upper()
    expected = str(expected_symbol).strip().upper()
    observed = sorted(symbols.unique().tolist())
    if observed != [expected]:
        raise ValueError(f"Expected only symbol {expected!r}, observed {observed!r}.")

    frame = raw[["time", "open", "high", "low", "close", "tick_volume"]].copy()
    frame.index = _utc_naive_index(frame.pop("time"), source_timezone=source_timezone)
    for column in ("open", "high", "low", "close", "tick_volume"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    frame["volume"] = frame["tick_volume"].astype(float)
    frame = frame[["open", "high", "low", "close", "volume", "tick_volume"]]

    if not frame.index.is_monotonic_increasing:
        raise ValueError("cTrader bar timestamps must be monotonic increasing.")
    if frame.index.has_duplicates:
        raise ValueError("cTrader bar export contains duplicate timestamps.")
    if drop_incomplete_tail:
        if len(frame) < 2:
            raise ValueError("Cannot drop an incomplete tail from fewer than two bars.")
        frame = frame.iloc[:-1].copy()

    validate_ohlcv(frame, allow_missing_volume=False)
    if not np.isfinite(frame["tick_volume"].to_numpy(dtype=float)).all():
        raise ValueError("cTrader bar export contains non-finite tick_volume values.")
    if (frame["tick_volume"] < 0).any():
        raise ValueError("cTrader bar export contains negative tick_volume values.")

    metadata = _base_metadata(
        path=resolved,
        frame=frame,
        raw_rows=len(raw),
        source_timezone=source_timezone,
        symbol=expected,
    )
    metadata.update(
        {
            "kind": "bar",
            "timeframe": str(timeframe).upper(),
            "timestamp_convention": timestamp_convention,
            "drop_incomplete_tail": bool(drop_incomplete_tail),
            "dropped_tail_rows": int(bool(drop_incomplete_tail)),
            "volume_semantics": "cTrader tick count; not exchange volume",
        }
    )
    return CTraderExport(frame=frame, metadata=metadata)


def load_ctrader_tick_export(
    path: str | Path,
    *,
    expected_symbol: str = "ETHUSD",
    source_timezone: str = "UTC",
) -> CTraderExport:
    """Load historical cTrader bid/ask ticks without deduplication or interpolation."""

    resolved = _resolve_export_path(path)
    raw = _normalize_columns(pd.read_csv(resolved))
    required = {"symbol", "time", "bid", "ask"}
    missing = sorted(required.difference(raw.columns))
    if missing:
        raise ValueError(f"cTrader tick export is missing required columns: {missing}")
    if raw.empty:
        raise ValueError("cTrader tick export is empty.")

    symbols = raw["symbol"].astype(str).str.strip().str.upper()
    expected = str(expected_symbol).strip().upper()
    observed = sorted(symbols.unique().tolist())
    if observed != [expected]:
        raise ValueError(f"Expected only symbol {expected!r}, observed {observed!r}.")

    trailing = [column for column in ("mid", "spread") if column in raw.columns]
    frame = raw[["time", "bid", "ask", *trailing]].copy()
    frame.index = _utc_naive_index(frame.pop("time"), source_timezone=source_timezone)
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="raise")

    if not frame.index.is_monotonic_increasing:
        raise ValueError("cTrader tick timestamps must be monotonic increasing.")
    if frame.index.has_duplicates:
        raise ValueError("cTrader tick export contains duplicate timestamps.")
    if not np.isfinite(frame[["bid", "ask"]].to_numpy(dtype=float)).all():
        raise ValueError("cTrader tick export contains non-finite bid/ask values.")
    if (frame[["bid", "ask"]] <= 0.0).any().any():
        raise ValueError("cTrader tick export contains non-positive bid/ask values.")
    if (frame["ask"] < frame["bid"]).any():
        raise ValueError("cTrader tick export contains crossed quotes (ask < bid).")

    calculated_mid = (frame["bid"] + frame["ask"]) / 2.0
    calculated_spread = frame["ask"] - frame["bid"]
    if "mid" in frame.columns and not np.allclose(
        frame["mid"].to_numpy(dtype=float),
        calculated_mid.to_numpy(dtype=float),
        rtol=0.0,
        atol=5e-6,
    ):
        raise ValueError("cTrader tick mid column is inconsistent with bid/ask.")
    if "spread" in frame.columns and not np.allclose(
        frame["spread"].to_numpy(dtype=float),
        calculated_spread.to_numpy(dtype=float),
        rtol=0.0,
        atol=5e-6,
    ):
        raise ValueError("cTrader tick spread column is inconsistent with bid/ask.")
    frame["mid"] = calculated_mid
    frame["spread"] = calculated_spread
    frame["spread_bps"] = frame["spread"] / frame["mid"] * 10_000.0
    frame = frame[["bid", "ask", "mid", "spread", "spread_bps"]]

    metadata = _base_metadata(
        path=resolved,
        frame=frame,
        raw_rows=len(raw),
        source_timezone=source_timezone,
        symbol=expected,
    )
    metadata.update(
        {
            "kind": "tick",
            "timestamp_convention": "event_time",
            "duplicate_policy": "raise",
            "interpolation_policy": "none",
        }
    )
    return CTraderExport(frame=frame, metadata=metadata)


__all__ = ["CTraderExport", "load_ctrader_bar_export", "load_ctrader_tick_export"]
