#!/usr/bin/env python3
from __future__ import annotations

"""Acquire genuine Dukascopy ETHUSD BID/ASK and build canonical 30m bars.

The requested interval is half-open: ``--start`` is included and ``--end`` is
excluded.  Raw daily JSON responses are cached byte-for-byte so interrupted
runs resume without silently changing already acquired source artifacts.
"""

import argparse
from dataclasses import asdict
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Sequence

import pandas as pd

from src.src_data.dukascopy_canonical import (
    CANONICAL_COLUMNS,
    DUKASCOPY_ENDPOINT_CONTRACT,
    DUKASCOPY_ENDPOINT_ROOT,
    DUKASCOPY_INSTRUMENT,
    DUKASCOPY_INSTRUMENT_CODE,
    DUKASCOPY_PROVIDER,
    QUOTE_SEMANTICS,
    REFERENCE_DOWNLOADER,
    VOLUME_SEMANTICS,
    DukascopyCanonicalError,
    DukascopyDailyClient,
    RawArtifact,
    canonicalize_bid_ask_minutes,
    iter_utc_days,
    source_bundle_sha256,
)

DEFAULT_START = "2020-01-01"
DEFAULT_END = "2026-06-10"
DEFAULT_OUTPUT = Path(
    "data/raw/dukascopy_ethusd_30m_canonical_v1/ethusd_30m_canonical.csv"
)
DEFAULT_RAW_ROOT = Path("data/raw/dukascopy_ethusd_30m_canonical_v1/source")
DEFAULT_MANIFEST = Path(
    "data/raw/dukascopy_ethusd_30m_canonical_v1/acquisition_manifest.json"
)


def _parse_date(value: str, *, field: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"{field} must use YYYY-MM-DD, got {value!r}."
        ) from exc
    return parsed


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_canonical_csv(
    frame: pd.DataFrame,
    *,
    path: Path,
    overwrite: bool,
) -> str:
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"Canonical output already exists; pass --overwrite-output only after "
            f"reviewing it: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    serializable = frame.copy()
    serializable["timestamp"] = pd.to_datetime(
        serializable["timestamp"], utc=True, errors="raise"
    ).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    serializable.to_csv(
        temporary,
        index=False,
        columns=list(CANONICAL_COLUMNS),
        float_format="%.12g",
        lineterminator="\n",
    )
    temporary.replace(path)
    return _sha256_file(path)


def _bundle_fingerprints(artifacts: Sequence[RawArtifact]) -> dict[str, str]:
    bid = [item for item in artifacts if item.side == "BID"]
    ask = [item for item in artifacts if item.side == "ASK"]
    return {
        "raw_bundle_sha256": source_bundle_sha256(artifacts),
        "bid_bundle_sha256": source_bundle_sha256(bid),
        "ask_bundle_sha256": source_bundle_sha256(ask),
    }


def acquire(
    *,
    start: date,
    end: date,
    raw_root: Path,
    output_path: Path,
    manifest_path: Path,
    timeout_seconds: float,
    max_retries: int,
    retry_base_seconds: float,
    request_pause_seconds: float,
    progress_every: int,
    overwrite_output: bool,
) -> dict[str, Any]:
    days = list(iter_utc_days(start, end))
    client = DukascopyDailyClient(
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        retry_base_seconds=retry_base_seconds,
        request_pause_seconds=request_pause_seconds,
    )
    bars: list[pd.DataFrame] = []
    artifacts: list[RawArtifact] = []
    incomplete_bar_count = 0
    empty_source_days: list[str] = []

    for position, day in enumerate(days, start=1):
        bid, bid_artifact = client.fetch_day(day, side="BID", raw_root=raw_root)
        ask, ask_artifact = client.fetch_day(day, side="ASK", raw_root=raw_root)
        expected_day = pd.Timestamp(day, tz="UTC")
        next_day = expected_day + pd.Timedelta(days=1)
        for side, frame in (("BID", bid), ("ASK", ask)):
            timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
            if ((timestamps < expected_day) | (timestamps >= next_day)).any():
                raise DukascopyCanonicalError(
                    f"{day} {side} payload contains timestamps outside its UTC day."
                )
        if bid.empty != ask.empty:
            raise DukascopyCanonicalError(
                f"{day}: only one Dukascopy quote side is empty "
                f"(bid_empty={bid.empty}, ask_empty={ask.empty})."
            )
        if bid.empty and ask.empty:
            empty_source_days.append(day.isoformat())
            artifacts.extend((bid_artifact, ask_artifact))
            if position == 1 or position % progress_every == 0 or position == len(days):
                print(
                    f"acquired_days={position}/{len(days)} day={day.isoformat()} "
                    f"canonical_bars={sum(len(item) for item in bars)} "
                    "matched_empty_day=true",
                    flush=True,
                )
            continue
        day_bars = canonicalize_bid_ask_minutes(bid, ask)
        incomplete_bar_count += int((day_bars["observed_minute_count"] < 30).sum())
        bars.append(day_bars)
        artifacts.extend((bid_artifact, ask_artifact))
        if position == 1 or position % progress_every == 0 or position == len(days):
            print(
                f"acquired_days={position}/{len(days)} day={day.isoformat()} "
                f"canonical_bars={sum(len(item) for item in bars)}",
                flush=True,
            )

    canonical = pd.concat(bars, ignore_index=True)
    canonical = canonical.sort_values("timestamp", kind="mergesort").reset_index(
        drop=True
    )
    if canonical.empty:
        raise DukascopyCanonicalError("Full canonical dataset is empty.")
    if canonical["timestamp"].duplicated().any():
        raise DukascopyCanonicalError(
            "Full canonical dataset has duplicate timestamps."
        )
    if not canonical["timestamp"].is_monotonic_increasing:
        raise DukascopyCanonicalError("Full canonical dataset is not timestamp sorted.")

    canonical_sha256 = _write_canonical_csv(
        canonical,
        path=output_path,
        overwrite=overwrite_output,
    )
    fingerprints = _bundle_fingerprints(artifacts)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "dataset_id": "ETHUSD-30M-CANONICAL-V1-SOURCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provider": DUKASCOPY_PROVIDER,
        "instrument": DUKASCOPY_INSTRUMENT,
        "provider_instrument_code": DUKASCOPY_INSTRUMENT_CODE,
        "endpoint_root": DUKASCOPY_ENDPOINT_ROOT,
        "endpoint_contract": DUKASCOPY_ENDPOINT_CONTRACT,
        "endpoint_template": (
            f"{DUKASCOPY_ENDPOINT_ROOT}/candles/minute/"
            f"{DUKASCOPY_INSTRUMENT_CODE}/{{BID|ASK}}/{{year}}/{{month}}/{{day}}"
        ),
        "requested_interval": {
            "start_inclusive": start.isoformat(),
            "end_exclusive": end.isoformat(),
        },
        "source_timeframe": "1min",
        "output_timeframe": "30min",
        "timezone": "UTC",
        "raw_storage_root": raw_root.as_posix(),
        "canonical_path": output_path.as_posix(),
        "canonical_sha256": canonical_sha256,
        "source_fingerprints": fingerprints,
        "reference_decoder": dict(REFERENCE_DOWNLOADER),
        "schema": list(CANONICAL_COLUMNS),
        "column_units": {
            "timestamp": "UTC",
            **{
                f"{side}_{field}": "USD_per_ETH"
                for side in ("bid", "ask", "mid")
                for field in ("open", "high", "low", "close")
            },
            "spread_absolute": "USD_per_ETH",
            "spread_fraction": "fraction",
            "spread_bps": "basis_points",
            "bid_volume": "Dukascopy_provider_units",
            "ask_volume": "Dukascopy_provider_units",
            "volume": "Dukascopy_two_sided_provider_units",
            "observed_minute_count": "count",
        },
        "quote_semantics": dict(QUOTE_SEMANTICS),
        "volume_semantics": VOLUME_SEMANTICS,
        "row_count": int(len(canonical)),
        "first_timestamp": pd.Timestamp(canonical["timestamp"].iloc[0]).isoformat(),
        "last_timestamp": pd.Timestamp(canonical["timestamp"].iloc[-1]).isoformat(),
        "incomplete_30m_bar_count": incomplete_bar_count,
        "matched_empty_source_day_count": len(empty_source_days),
        "matched_empty_source_days": empty_source_days,
        "gap_policy": {
            "maximum_expected_gap": "72h",
            "maximum_expected_30m_multiple": 144,
            "rationale": (
                "Fixed domain allowance for historical Dukascopy CFD weekend and "
                "year-end market closures; gaps remain explicit and are never filled."
            ),
        },
        "raw_artifact_count": len(artifacts),
        "raw_artifacts": [asdict(item) for item in artifacts],
    }
    if manifest_path.exists() and not overwrite_output:
        raise FileExistsError(
            f"Acquisition manifest already exists; pass --overwrite-output only after "
            f"reviewing it: {manifest_path}"
        )
    _atomic_write_json(manifest_path, manifest)
    return manifest


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Acquire separate genuine Dukascopy BID/ASK minute candles and build "
            "the canonical ETHUSD 30-minute research dataset."
        )
    )
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--max-retries", type=int, default=8)
    parser.add_argument("--retry-base-seconds", type=float, default=1.0)
    parser.add_argument("--request-pause-seconds", type=float, default=0.05)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--overwrite-output", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    start = _parse_date(args.start, field="start")
    end = _parse_date(args.end, field="end")
    if args.progress_every <= 0:
        raise ValueError("--progress-every must be > 0.")
    manifest = acquire(
        start=start,
        end=end,
        raw_root=args.raw_root,
        output_path=args.output,
        manifest_path=args.manifest,
        timeout_seconds=args.timeout_seconds,
        max_retries=args.max_retries,
        retry_base_seconds=args.retry_base_seconds,
        request_pause_seconds=args.request_pause_seconds,
        progress_every=args.progress_every,
        overwrite_output=args.overwrite_output,
    )
    print(
        json.dumps(
            {
                "dataset_id": manifest["dataset_id"],
                "row_count": manifest["row_count"],
                "first_timestamp": manifest["first_timestamp"],
                "last_timestamp": manifest["last_timestamp"],
                "canonical_sha256": manifest["canonical_sha256"],
                "source_fingerprints": manifest["source_fingerprints"],
                "incomplete_30m_bar_count": manifest["incomplete_30m_bar_count"],
                "matched_empty_source_day_count": manifest[
                    "matched_empty_source_day_count"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
