from __future__ import annotations

"""Reproducible Dukascopy BID/ASK acquisition for canonical research bars.

The provider endpoint returns one compressed UTC day of one-minute candles for
one quote side.  This module preserves each raw response byte-for-byte, decodes
only observed provider candles, requires exact BID/ASK minute coverage, and
then aggregates paired observations to 30-minute bars.  It never reconstructs
quotes from midpoint data and never forward-fills missing source observations.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from hashlib import sha256
import json
import math
from pathlib import Path
import time
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
import requests

DUKASCOPY_PROVIDER = "Dukascopy Bank"
DUKASCOPY_INSTRUMENT = "ETHUSD"
DUKASCOPY_INSTRUMENT_CODE = "ETH-USD"
DUKASCOPY_ENDPOINT_ROOT = "https://jetta.dukascopy.com/v1"
DUKASCOPY_ENDPOINT_CONTRACT = "daily-compressed-minute-candles-v1"
REFERENCE_DOWNLOADER = {
    "package": "dukascopy-node",
    "version": "1.50.0",
    "git_head": "031d47de2ea94fc695147b682f8dd95440913f23",
    "npm_integrity": (
        "sha512-o2Co/asUD/TXFNhblJUYkRseHMt/uvFrnhzOKWezLuiFJqbl4Zn2oJGL4/"
        "W+PY1b2YsI11+9+TO40qNQBAj8/w=="
    ),
}
QUOTE_SIDES = ("BID", "ASK")
OHLC_FIELDS = ("open", "high", "low", "close")
RAW_REQUIRED_KEYS = frozenset(
    {
        "timestamp",
        "multiplier",
        "open",
        "high",
        "low",
        "close",
        "shift",
        "times",
        "opens",
        "highs",
        "lows",
        "closes",
        "volumes",
    }
)
CANONICAL_COLUMNS = (
    "timestamp",
    "bid_open",
    "bid_high",
    "bid_low",
    "bid_close",
    "ask_open",
    "ask_high",
    "ask_low",
    "ask_close",
    "mid_open",
    "mid_high",
    "mid_low",
    "mid_close",
    "spread_absolute",
    "spread_fraction",
    "spread_bps",
    "bid_volume",
    "ask_volume",
    "volume",
    "observed_minute_count",
)
VOLUME_SEMANTICS = (
    "Dukascopy side-specific one-minute candle volume fields converted from the "
    "provider million-unit scale to units and summed within each 30-minute bar. "
    "bid_volume and ask_volume are retained separately; volume is their sum and "
    "is a two-sided quote/liquidity activity measure, not exchange matched-trade "
    "volume and not ETH base-asset trade volume."
)
QUOTE_SEMANTICS = {
    "source": "separate genuine Dukascopy BID and ASK one-minute candle observations",
    "aggregation": "paired observed UTC one-minute candles aggregated to left-labelled 30-minute bars",
    "mid_ohlc": (
        "fieldwise arithmetic midpoint of paired BID/ASK one-minute OHLC, then "
        "aggregated using open-first, high-max, low-min, close-last"
    ),
    "spread_reference": "30-minute closing quote",
    "spread_absolute": "ask_close - bid_close",
    "spread_fraction": "spread_absolute / mid_close",
    "spread_bps": "10000 * spread_fraction",
    "missing_observations": "never synthesized or forward-filled",
}


class DukascopyCanonicalError(RuntimeError):
    """Raised when source acquisition or canonicalization cannot be trusted."""


@dataclass(frozen=True)
class RawArtifact:
    day: str
    side: str
    path: str
    sha256: str
    byte_count: int
    observed_minute_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "side": self.side,
            "path": self.path,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
            "observed_minute_count": self.observed_minute_count,
        }


ByteTransport = Callable[[str], bytes]


def _finite_number(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DukascopyCanonicalError(f"{field} must be numeric, got {value!r}.")
    number = float(value)
    if not math.isfinite(number):
        raise DukascopyCanonicalError(f"{field} must be finite, got {value!r}.")
    return number


def _integer(value: Any, *, field: str, minimum: int | None = None) -> int:
    number = _finite_number(value, field=field)
    if not number.is_integer():
        raise DukascopyCanonicalError(f"{field} must be an integer, got {value!r}.")
    integer = int(number)
    if minimum is not None and integer < minimum:
        raise DukascopyCanonicalError(f"{field} must be >= {minimum}, got {integer}.")
    return integer


def _price_scale(multiplier: float) -> int:
    text = format(multiplier, ".15g").lower()
    coefficient, _, exponent_text = text.partition("e")
    decimals = len(coefficient.partition(".")[2])
    exponent = int(exponent_text or "0")
    return max(0, decimals - exponent)


def _payload_from_bytes(raw: bytes, *, source: str) -> Mapping[str, Any]:
    if not raw:
        raise DukascopyCanonicalError(f"Empty Dukascopy payload: {source}.")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DukascopyCanonicalError(
            f"Invalid Dukascopy JSON payload at {source}: {exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise DukascopyCanonicalError(
            f"Dukascopy payload at {source} must be a JSON object."
        )
    missing = sorted(RAW_REQUIRED_KEYS.difference(payload))
    if missing:
        raise DukascopyCanonicalError(
            f"Dukascopy payload at {source} is missing keys: {missing}."
        )
    return payload


def decode_daily_candles(
    payload: Mapping[str, Any],
    *,
    side: str,
) -> pd.DataFrame:
    """Decode observed provider candles without inserting synthetic flat rows."""

    normalized_side = str(side).strip().upper()
    if normalized_side not in QUOTE_SIDES:
        raise ValueError(f"side must be one of {QUOTE_SIDES}, got {side!r}.")
    missing = sorted(RAW_REQUIRED_KEYS.difference(payload))
    if missing:
        raise DukascopyCanonicalError(f"Dukascopy payload missing keys: {missing}.")

    arrays: dict[str, Sequence[Any]] = {}
    for key in ("times", "opens", "highs", "lows", "closes", "volumes"):
        value = payload[key]
        if not isinstance(value, list):
            raise DukascopyCanonicalError(f"Dukascopy field {key} must be a list.")
        arrays[key] = value
    length = len(arrays["times"])
    mismatches = {
        key: len(value) for key, value in arrays.items() if len(value) != length
    }
    if mismatches:
        raise DukascopyCanonicalError(
            "Dukascopy compressed columns have unequal lengths: "
            f"expected={length}, mismatches={mismatches}."
        )

    timestamp_ms = _integer(payload["timestamp"], field="timestamp", minimum=0)
    shift_ms = _integer(payload["shift"], field="shift", minimum=1)
    if shift_ms != 60_000:
        raise DukascopyCanonicalError(
            f"Expected one-minute Dukascopy shift=60000ms, found {shift_ms}."
        )
    multiplier = _finite_number(payload["multiplier"], field="multiplier")
    if multiplier <= 0.0:
        raise DukascopyCanonicalError("multiplier must be strictly positive.")
    if length == 0:
        prefix = normalized_side.lower()
        return pd.DataFrame(
            columns=[
                "timestamp",
                *(f"{prefix}_{field}" for field in OHLC_FIELDS),
                f"{prefix}_volume",
            ]
        )
    scale = _price_scale(multiplier)
    cumulative_units = {
        field: round(_finite_number(payload[field], field=field) / multiplier)
        for field in OHLC_FIELDS
    }

    rows: list[dict[str, Any]] = []
    previous_timestamp_ms: int | None = None
    for index in range(length):
        time_delta = _integer(
            arrays["times"][index], field=f"times[{index}]", minimum=0
        )
        timestamp_ms += time_delta * shift_ms
        if previous_timestamp_ms is not None and timestamp_ms <= previous_timestamp_ms:
            raise DukascopyCanonicalError(
                "Decoded Dukascopy timestamps are not strictly increasing at "
                f"index {index}: {timestamp_ms} <= {previous_timestamp_ms}."
            )
        previous_timestamp_ms = timestamp_ms
        row: dict[str, Any] = {
            "timestamp": pd.Timestamp(timestamp_ms, unit="ms", tz="UTC")
        }
        for field, delta_key in (
            ("open", "opens"),
            ("high", "highs"),
            ("low", "lows"),
            ("close", "closes"),
        ):
            delta = _integer(arrays[delta_key][index], field=f"{delta_key}[{index}]")
            cumulative_units[field] += delta
            row[f"{normalized_side.lower()}_{field}"] = round(
                cumulative_units[field] * multiplier, scale
            )
        provider_volume_millions = _finite_number(
            arrays["volumes"][index], field=f"volumes[{index}]"
        )
        if provider_volume_millions < 0.0:
            raise DukascopyCanonicalError(f"volumes[{index}] must be non-negative.")
        row[f"{normalized_side.lower()}_volume"] = (
            provider_volume_millions * 1_000_000.0
        )
        rows.append(row)

    frame = pd.DataFrame(rows)
    prefix = normalized_side.lower()
    geometry_invalid = (
        (frame[f"{prefix}_high"] < frame[f"{prefix}_open"])
        | (frame[f"{prefix}_high"] < frame[f"{prefix}_close"])
        | (frame[f"{prefix}_low"] > frame[f"{prefix}_open"])
        | (frame[f"{prefix}_low"] > frame[f"{prefix}_close"])
        | (frame[f"{prefix}_high"] < frame[f"{prefix}_low"])
    )
    if geometry_invalid.any():
        raise DukascopyCanonicalError(
            f"Decoded {normalized_side} source contains "
            f"{int(geometry_invalid.sum())} invalid OHLC rows."
        )
    return frame


def pair_bid_ask_minutes(bid: pd.DataFrame, ask: pd.DataFrame) -> pd.DataFrame:
    """Require one-to-one synchronous source coverage before computing midpoints."""

    merged = bid.merge(
        ask,
        on="timestamp",
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    bid_only = int(merged["_merge"].eq("left_only").sum())
    ask_only = int(merged["_merge"].eq("right_only").sum())
    if bid_only or ask_only:
        raise DukascopyCanonicalError(
            "Dukascopy BID/ASK minute coverage differs; canonicalization refuses "
            f"an inner join (bid_only={bid_only}, ask_only={ask_only})."
        )
    merged = merged.drop(columns="_merge").sort_values("timestamp", kind="mergesort")
    if merged.empty:
        raise DukascopyCanonicalError("Paired Dukascopy minute data is empty.")
    if merged["timestamp"].duplicated().any():
        raise DukascopyCanonicalError(
            "Paired Dukascopy minute timestamps are duplicated."
        )
    if not merged["timestamp"].is_monotonic_increasing:
        raise DukascopyCanonicalError(
            "Paired Dukascopy minute timestamps are unsorted."
        )

    crossed: dict[str, int] = {}
    for field in OHLC_FIELDS:
        count = int((merged[f"ask_{field}"] < merged[f"bid_{field}"]).sum())
        if count:
            crossed[field] = count
        merged[f"mid_{field}"] = (merged[f"bid_{field}"] + merged[f"ask_{field}"]) / 2.0
    if crossed:
        raise DukascopyCanonicalError(
            f"Dukascopy source contains crossed BID/ASK OHLC observations: {crossed}."
        )
    return merged.reset_index(drop=True)


def aggregate_paired_minutes_to_30m(paired: pd.DataFrame) -> pd.DataFrame:
    """Aggregate paired observed minute candles into canonical 30-minute bars."""

    required = {
        "timestamp",
        "bid_volume",
        "ask_volume",
        *(f"{side}_{field}" for side in ("bid", "ask", "mid") for field in OHLC_FIELDS),
    }
    missing = sorted(required.difference(paired.columns))
    if missing:
        raise DukascopyCanonicalError(
            f"Paired minute frame is missing required columns: {missing}."
        )
    frame = paired.copy()
    timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
    if (timestamps.dt.second != 0).any() or (timestamps.dt.microsecond != 0).any():
        raise DukascopyCanonicalError("Minute source contains off-minute timestamps.")
    frame["timestamp"] = timestamps
    frame["bar_timestamp"] = timestamps.dt.floor("30min")

    aggregations: dict[str, str] = {}
    for side in ("bid", "ask", "mid"):
        aggregations.update(
            {
                f"{side}_open": "first",
                f"{side}_high": "max",
                f"{side}_low": "min",
                f"{side}_close": "last",
            }
        )
    aggregations.update({"bid_volume": "sum", "ask_volume": "sum"})
    bars = (
        frame.groupby("bar_timestamp", sort=True, observed=True)
        .agg(aggregations)
        .reset_index()
        .rename(columns={"bar_timestamp": "timestamp"})
    )
    counts = frame.groupby("bar_timestamp", sort=True, observed=True).size()
    bars["observed_minute_count"] = counts.to_numpy(dtype=np.int64)
    bars["volume"] = bars["bid_volume"] + bars["ask_volume"]
    bars["spread_absolute"] = bars["ask_close"] - bars["bid_close"]
    bars["spread_fraction"] = bars["spread_absolute"] / bars["mid_close"]
    bars["spread_bps"] = 10_000.0 * bars["spread_fraction"]

    if (bars["observed_minute_count"] <= 0).any() or (
        bars["observed_minute_count"] > 30
    ).any():
        raise DukascopyCanonicalError(
            "Observed minute counts per 30-minute bar must lie in [1, 30]."
        )
    if (bars["spread_absolute"] < 0.0).any():
        raise DukascopyCanonicalError(
            "Canonical 30-minute output contains negative spread."
        )
    if not np.isfinite(
        bars.select_dtypes(include=[np.number]).to_numpy(dtype=float)
    ).all():
        raise DukascopyCanonicalError("Canonical 30-minute output contains NaN/Inf.")
    return bars[list(CANONICAL_COLUMNS)].reset_index(drop=True)


def canonicalize_bid_ask_minutes(
    bid: pd.DataFrame,
    ask: pd.DataFrame,
) -> pd.DataFrame:
    return aggregate_paired_minutes_to_30m(pair_bid_ask_minutes(bid, ask))


def iter_utc_days(start: date, end: date) -> Iterable[date]:
    """Yield UTC dates in the half-open interval ``[start, end)``."""

    if start >= end:
        raise ValueError("start must be earlier than end.")
    current = start
    while current < end:
        yield current
        current += timedelta(days=1)


def dukascopy_daily_url(day: date, side: str) -> str:
    normalized_side = str(side).strip().upper()
    if normalized_side not in QUOTE_SIDES:
        raise ValueError(f"side must be one of {QUOTE_SIDES}, got {side!r}.")
    return (
        f"{DUKASCOPY_ENDPOINT_ROOT}/candles/minute/"
        f"{DUKASCOPY_INSTRUMENT_CODE}/{normalized_side}/"
        f"{day.year}/{day.month}/{day.day}"
    )


class DukascopyDailyClient:
    """Rate-limit-aware client for immutable daily source payloads."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        max_retries: int = 8,
        retry_base_seconds: float = 1.0,
        request_pause_seconds: float = 0.05,
        transport: ByteTransport | None = None,
    ) -> None:
        if timeout_seconds <= 0.0:
            raise ValueError("timeout_seconds must be > 0.")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0.")
        if retry_base_seconds < 0.0 or request_pause_seconds < 0.0:
            raise ValueError("retry and request pauses must be >= 0.")
        self.timeout_seconds = float(timeout_seconds)
        self.max_retries = int(max_retries)
        self.retry_base_seconds = float(retry_base_seconds)
        self.request_pause_seconds = float(request_pause_seconds)
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": "systematic-trading-framework/dukascopy-canonical-v1"}
        )
        self._transport = transport

    def _request_bytes(self, url: str) -> bytes:
        if self._transport is not None:
            return self._transport(url)
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._session.get(url, timeout=self.timeout_seconds)
                if response.status_code == 429 or response.status_code >= 500:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after is not None:
                        try:
                            pause = max(float(retry_after), 0.0)
                        except ValueError:
                            pause = self.retry_base_seconds * (2**attempt)
                    else:
                        pause = self.retry_base_seconds * (2**attempt)
                    if attempt == self.max_retries:
                        response.raise_for_status()
                    time.sleep(min(pause, 60.0))
                    continue
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "")
                if "json" not in content_type.lower():
                    raise DukascopyCanonicalError(
                        f"Unexpected Dukascopy content type {content_type!r} for {url}."
                    )
                return response.content
            except (requests.RequestException, DukascopyCanonicalError) as exc:
                last_error = exc
                if attempt == self.max_retries:
                    break
                time.sleep(min(self.retry_base_seconds * (2**attempt), 60.0))
        raise DukascopyCanonicalError(
            f"Dukascopy request failed after {self.max_retries + 1} attempts: {url}: "
            f"{last_error}"
        ) from last_error

    def fetch_day(
        self,
        day: date,
        *,
        side: str,
        raw_root: Path,
    ) -> tuple[pd.DataFrame, RawArtifact]:
        normalized_side = str(side).strip().upper()
        url = dukascopy_daily_url(day, normalized_side)
        relative = Path(
            DUKASCOPY_INSTRUMENT,
            f"{day.year:04d}",
            f"{day.month:02d}",
            f"{day.day:02d}",
            f"{normalized_side}.json",
        )
        path = raw_root / relative
        if path.is_file() and path.stat().st_size > 0:
            raw = path.read_bytes()
        else:
            raw = self._request_bytes(url)
            payload = _payload_from_bytes(raw, source=url)
            decode_daily_candles(payload, side=normalized_side)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".json.part")
            temporary.write_bytes(raw)
            temporary.replace(path)
            if self.request_pause_seconds:
                time.sleep(self.request_pause_seconds)
        payload = _payload_from_bytes(raw, source=str(path))
        frame = decode_daily_candles(payload, side=normalized_side)
        artifact = RawArtifact(
            day=day.isoformat(),
            side=normalized_side,
            path=relative.as_posix(),
            sha256=sha256(raw).hexdigest(),
            byte_count=len(raw),
            observed_minute_count=len(frame),
        )
        return frame, artifact


def source_bundle_sha256(artifacts: Sequence[RawArtifact]) -> str:
    payload = [
        {"path": item.path, "sha256": item.sha256}
        for item in sorted(artifacts, key=lambda value: (value.path, value.sha256))
    ]
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _audit_issue(
    issues: list[dict[str, Any]],
    code: str,
    severity: str,
    message: str,
    *,
    count: int | None = None,
    context: Mapping[str, Any] | None = None,
) -> None:
    issues.append(
        {
            "code": code,
            "severity": severity,
            "message": message,
            "count": count,
            "context": dict(context or {}),
        }
    )


def audit_canonical_30m_frame(frame: pd.DataFrame) -> dict[str, Any]:
    """Run ETHUSD-specific invariants beyond the generic quality contract."""

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame.")
    issues: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {
        "row_count": int(len(frame)),
        "columns": [str(column) for column in frame.columns],
    }
    duplicated_columns = sorted(
        {
            str(column)
            for column, duplicated in zip(
                frame.columns, frame.columns.duplicated(keep=False)
            )
            if duplicated
        }
    )
    if duplicated_columns:
        _audit_issue(
            issues,
            "DUPLICATE_COLUMNS",
            "CRITICAL",
            "Canonical ETHUSD schema contains duplicate columns.",
            count=len(duplicated_columns),
            context={"columns": duplicated_columns},
        )
    missing = sorted(set(CANONICAL_COLUMNS).difference(frame.columns))
    if missing:
        _audit_issue(
            issues,
            "MISSING_CANONICAL_COLUMNS",
            "CRITICAL",
            "Canonical ETHUSD columns are missing.",
            count=len(missing),
            context={"columns": missing},
        )
    if missing or duplicated_columns or frame.empty:
        if frame.empty:
            _audit_issue(
                issues,
                "EMPTY_CANONICAL_DATASET",
                "CRITICAL",
                "Canonical ETHUSD dataset contains no rows.",
            )
        return {
            "schema_version": 1,
            "status": "FAIL",
            "research_eligible": False,
            "metrics": metrics,
            "issues": issues,
        }

    timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    invalid_timestamps = int(timestamps.isna().sum())
    duplicate_timestamps = int(timestamps.duplicated(keep=False).sum())
    off_grid = int(
        (
            (timestamps.dt.minute % 30 != 0)
            | (timestamps.dt.second != 0)
            | (timestamps.dt.microsecond != 0)
        ).sum()
    )
    metrics.update(
        {
            "invalid_timestamp_count": invalid_timestamps,
            "duplicate_timestamp_count": duplicate_timestamps,
            "timestamps_sorted": bool(timestamps.is_monotonic_increasing),
            "off_30m_grid_count": off_grid,
            "first_timestamp": (
                None if timestamps.isna().all() else timestamps.min().isoformat()
            ),
            "last_timestamp": (
                None if timestamps.isna().all() else timestamps.max().isoformat()
            ),
        }
    )
    if (
        invalid_timestamps
        or duplicate_timestamps
        or off_grid
        or not timestamps.is_monotonic_increasing
    ):
        _audit_issue(
            issues,
            "INVALID_CANONICAL_TIMESTAMPS",
            "CRITICAL",
            "Canonical timestamps must be valid, unique, sorted UTC 30-minute labels.",
            context={
                "invalid": invalid_timestamps,
                "duplicates": duplicate_timestamps,
                "off_grid": off_grid,
                "sorted": bool(timestamps.is_monotonic_increasing),
            },
        )

    numeric_columns = [column for column in CANONICAL_COLUMNS if column != "timestamp"]
    numeric = pd.DataFrame(
        {
            column: pd.to_numeric(frame[column], errors="coerce")
            for column in numeric_columns
        }
    )
    non_numeric_counts = {
        column: int((frame[column].notna() & numeric[column].isna()).sum())
        for column in numeric_columns
    }
    non_numeric_counts = {
        key: value for key, value in non_numeric_counts.items() if value
    }
    nan_count = int(numeric.isna().sum().sum())
    inf_count = int(np.isinf(numeric.to_numpy(dtype=float)).sum())
    metrics.update(
        {
            "non_numeric_counts": non_numeric_counts,
            "nan_count": nan_count,
            "inf_count": inf_count,
        }
    )
    if non_numeric_counts or nan_count or inf_count:
        _audit_issue(
            issues,
            "INVALID_NUMERIC_VALUES",
            "CRITICAL",
            "Canonical numeric fields must be finite and non-missing.",
            context={
                "non_numeric_counts": non_numeric_counts,
                "nan_count": nan_count,
                "inf_count": inf_count,
            },
        )

    geometry_counts: dict[str, int] = {}
    for side in ("bid", "ask", "mid"):
        invalid = (
            (numeric[f"{side}_high"] < numeric[f"{side}_open"])
            | (numeric[f"{side}_high"] < numeric[f"{side}_close"])
            | (numeric[f"{side}_low"] > numeric[f"{side}_open"])
            | (numeric[f"{side}_low"] > numeric[f"{side}_close"])
            | (numeric[f"{side}_high"] < numeric[f"{side}_low"])
        )
        geometry_counts[side] = int(invalid.sum())
    metrics["invalid_ohlc_geometry_by_side"] = geometry_counts
    if any(geometry_counts.values()):
        _audit_issue(
            issues,
            "INVALID_SIDE_OHLC_GEOMETRY",
            "CRITICAL",
            "BID, ASK, and MID OHLC geometry must each be valid.",
            count=sum(geometry_counts.values()),
            context=geometry_counts,
        )

    quote_order_counts: dict[str, int] = {}
    for field in OHLC_FIELDS:
        invalid = (numeric[f"bid_{field}"] > numeric[f"mid_{field}"]) | (
            numeric[f"mid_{field}"] > numeric[f"ask_{field}"]
        )
        quote_order_counts[field] = int(invalid.sum())
    metrics["invalid_bid_mid_ask_order_by_field"] = quote_order_counts
    if any(quote_order_counts.values()):
        _audit_issue(
            issues,
            "INVALID_BID_MID_ASK_ORDER",
            "CRITICAL",
            "Every BID/MID/ASK OHLC field must satisfy bid <= mid <= ask.",
            count=sum(quote_order_counts.values()),
            context=quote_order_counts,
        )

    expected_absolute = numeric["ask_close"] - numeric["bid_close"]
    expected_fraction = expected_absolute / numeric["mid_close"]
    expected_bps = 10_000.0 * expected_fraction
    formula_counts = {
        "negative_spread": int((numeric["spread_absolute"] < 0.0).sum()),
        "spread_absolute_mismatch": int(
            (
                ~np.isclose(
                    numeric["spread_absolute"],
                    expected_absolute,
                    rtol=1e-10,
                    atol=1e-12,
                )
            ).sum()
        ),
        "spread_fraction_mismatch": int(
            (
                ~np.isclose(
                    numeric["spread_fraction"],
                    expected_fraction,
                    rtol=1e-10,
                    atol=1e-12,
                )
            ).sum()
        ),
        "spread_bps_mismatch": int(
            (
                ~np.isclose(numeric["spread_bps"], expected_bps, rtol=1e-10, atol=1e-10)
            ).sum()
        ),
    }
    metrics["spread_formula_counts"] = formula_counts
    if any(formula_counts.values()):
        _audit_issue(
            issues,
            "INVALID_SPREAD_FORMULAS",
            "CRITICAL",
            "Canonical spread units or formulas are inconsistent.",
            count=sum(formula_counts.values()),
            context=formula_counts,
        )

    volume_counts = {
        "negative_bid_volume": int((numeric["bid_volume"] < 0.0).sum()),
        "negative_ask_volume": int((numeric["ask_volume"] < 0.0).sum()),
        "negative_total_volume": int((numeric["volume"] < 0.0).sum()),
        "total_volume_mismatch": int(
            (
                ~np.isclose(
                    numeric["volume"],
                    numeric["bid_volume"] + numeric["ask_volume"],
                    rtol=1e-12,
                    atol=1e-9,
                )
            ).sum()
        ),
    }
    metrics["volume_contract_counts"] = volume_counts
    if any(volume_counts.values()):
        _audit_issue(
            issues,
            "INVALID_VOLUME_CONTRACT",
            "CRITICAL",
            "Side volumes must be non-negative and sum to total volume.",
            count=sum(volume_counts.values()),
            context=volume_counts,
        )

    observed = numeric["observed_minute_count"]
    non_integer_observed = int((observed % 1 != 0).sum())
    invalid_observed = int(((observed < 1) | (observed > 30)).sum())
    partial = observed < 30
    distribution = observed.value_counts().sort_index()
    metrics.update(
        {
            "non_integer_observed_minute_count": non_integer_observed,
            "invalid_observed_minute_count": invalid_observed,
            "partial_30m_bar_count": int(partial.sum()),
            "partial_30m_bar_rate": float(partial.mean()),
            "observed_minute_count_distribution": {
                str(int(key)): int(value) for key, value in distribution.items()
            },
        }
    )
    if non_integer_observed or invalid_observed:
        _audit_issue(
            issues,
            "INVALID_OBSERVED_MINUTE_COUNT",
            "CRITICAL",
            "Each canonical bar must contain 1 to 30 observed source minutes.",
            count=non_integer_observed + invalid_observed,
        )
    elif partial.any():
        _audit_issue(
            issues,
            "PARTIAL_SOURCE_MINUTE_COVERAGE",
            "WARNING",
            "Some 30-minute bars contain fewer than 30 observed provider minutes; no missing minutes were synthesized.",
            count=int(partial.sum()),
            context={"rate": float(partial.mean())},
        )

    deltas = timestamps.diff()
    gaps = deltas[deltas > pd.Timedelta(minutes=30)]
    metrics["gap_report"] = [
        {
            "previous_timestamp": timestamps.iloc[index - 1].isoformat(),
            "next_timestamp": timestamps.iloc[index].isoformat(),
            "gap_seconds": float(delta.total_seconds()),
            "estimated_missing_30m_intervals": int(
                delta / pd.Timedelta(minutes=30) - 1
            ),
        }
        for index, delta in gaps.items()
    ]

    critical = any(issue["severity"] == "CRITICAL" for issue in issues)
    warnings = any(issue["severity"] == "WARNING" for issue in issues)
    return {
        "schema_version": 1,
        "status": (
            "FAIL" if critical else ("PASS_WITH_WARNINGS" if warnings else "PASS")
        ),
        "research_eligible": not critical,
        "metrics": metrics,
        "issues": issues,
    }


def audit_acquisition_manifest(
    manifest_path: str | Path,
    *,
    repository_root: str | Path,
) -> dict[str, Any]:
    """Re-hash every raw side artifact and the canonical output from a manifest."""

    path = Path(manifest_path).expanduser().resolve()
    root = Path(repository_root).expanduser().resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    issues: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}
    raw_root = (root / str(payload.get("raw_storage_root", ""))).resolve()
    canonical_path = (root / str(payload.get("canonical_path", ""))).resolve()
    for resolved, label in (
        (raw_root, "raw_storage_root"),
        (canonical_path, "canonical_path"),
    ):
        try:
            resolved.relative_to(root)
        except ValueError:
            _audit_issue(
                issues,
                "NON_PORTABLE_SOURCE_PATH",
                "CRITICAL",
                f"{label} escapes the repository root.",
                context={"path": str(resolved)},
            )

    raw_items = payload.get("raw_artifacts")
    if not isinstance(raw_items, list):
        raw_items = []
        _audit_issue(
            issues,
            "MISSING_RAW_ARTIFACT_MANIFEST",
            "CRITICAL",
            "Acquisition manifest raw_artifacts must be a list.",
        )
    artifacts: list[RawArtifact] = []
    observed_by_day: dict[str, dict[str, int]] = {}
    missing_files = 0
    mutated_files = 0
    invalid_payloads = 0
    duplicate_paths = 0
    seen_paths: set[str] = set()
    for raw_item in raw_items:
        try:
            artifact = RawArtifact(
                day=str(raw_item["day"]),
                side=str(raw_item["side"]),
                path=str(raw_item["path"]),
                sha256=str(raw_item["sha256"]),
                byte_count=int(raw_item["byte_count"]),
                observed_minute_count=int(raw_item["observed_minute_count"]),
            )
        except (KeyError, TypeError, ValueError):
            invalid_payloads += 1
            continue
        if artifact.path in seen_paths:
            duplicate_paths += 1
        seen_paths.add(artifact.path)
        artifact_path = (raw_root / artifact.path).resolve()
        try:
            artifact_path.relative_to(raw_root)
        except ValueError:
            invalid_payloads += 1
            continue
        if not artifact_path.is_file():
            missing_files += 1
            continue
        raw = artifact_path.read_bytes()
        if (
            len(raw) != artifact.byte_count
            or sha256(raw).hexdigest() != artifact.sha256
        ):
            mutated_files += 1
            continue
        try:
            decoded = decode_daily_candles(
                _payload_from_bytes(raw, source=str(artifact_path)),
                side=artifact.side,
            )
        except (DukascopyCanonicalError, ValueError):
            invalid_payloads += 1
            continue
        if len(decoded) != artifact.observed_minute_count:
            invalid_payloads += 1
            continue
        artifacts.append(artifact)
        observed_by_day.setdefault(artifact.day, {})[artifact.side] = len(decoded)

    unmatched_days = {
        day: sides
        for day, sides in observed_by_day.items()
        if set(sides) != set(QUOTE_SIDES) or (sides["BID"] == 0) != (sides["ASK"] == 0)
    }
    metrics.update(
        {
            "declared_raw_artifact_count": payload.get("raw_artifact_count"),
            "audited_raw_artifact_count": len(artifacts),
            "missing_raw_file_count": missing_files,
            "mutated_raw_file_count": mutated_files,
            "invalid_raw_payload_count": invalid_payloads,
            "duplicate_raw_path_count": duplicate_paths,
            "unmatched_bid_ask_day_count": len(unmatched_days),
            "unmatched_bid_ask_days": unmatched_days,
        }
    )
    source_problems = (
        missing_files
        + mutated_files
        + invalid_payloads
        + duplicate_paths
        + len(unmatched_days)
    )
    if source_problems or payload.get("raw_artifact_count") != len(artifacts):
        _audit_issue(
            issues,
            "RAW_SOURCE_INTEGRITY_FAILURE",
            "CRITICAL",
            "Raw Dukascopy source artifacts failed integrity or BID/ASK pairing checks.",
            count=source_problems,
            context=metrics,
        )

    observed_fingerprints = {
        "raw_bundle_sha256": source_bundle_sha256(artifacts),
        "bid_bundle_sha256": source_bundle_sha256(
            [item for item in artifacts if item.side == "BID"]
        ),
        "ask_bundle_sha256": source_bundle_sha256(
            [item for item in artifacts if item.side == "ASK"]
        ),
    }
    expected_fingerprints = payload.get("source_fingerprints", {})
    metrics["observed_source_fingerprints"] = observed_fingerprints
    metrics["source_fingerprints_match"] = (
        observed_fingerprints == expected_fingerprints
    )
    if observed_fingerprints != expected_fingerprints:
        _audit_issue(
            issues,
            "SOURCE_BUNDLE_FINGERPRINT_MISMATCH",
            "CRITICAL",
            "Recomputed BID/ASK source bundle fingerprints differ from the manifest.",
            context={
                "expected": expected_fingerprints,
                "observed": observed_fingerprints,
            },
        )

    canonical_sha256 = None
    if canonical_path.is_file():
        digest = sha256()
        with canonical_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        canonical_sha256 = digest.hexdigest()
    metrics.update(
        {
            "canonical_path": str(canonical_path),
            "canonical_sha256": canonical_sha256,
            "canonical_sha256_match": canonical_sha256
            == payload.get("canonical_sha256"),
        }
    )
    if canonical_sha256 is None or canonical_sha256 != payload.get("canonical_sha256"):
        _audit_issue(
            issues,
            "CANONICAL_OUTPUT_FINGERPRINT_MISMATCH",
            "CRITICAL",
            "Canonical output bytes differ from the acquisition manifest.",
        )

    critical = any(issue["severity"] == "CRITICAL" for issue in issues)
    return {
        "schema_version": 1,
        "status": "FAIL" if critical else "PASS",
        "research_eligible": not critical,
        "metrics": metrics,
        "issues": issues,
    }


__all__ = [
    "CANONICAL_COLUMNS",
    "DUKASCOPY_ENDPOINT_CONTRACT",
    "DUKASCOPY_ENDPOINT_ROOT",
    "DUKASCOPY_INSTRUMENT",
    "DUKASCOPY_INSTRUMENT_CODE",
    "DUKASCOPY_PROVIDER",
    "DukascopyCanonicalError",
    "DukascopyDailyClient",
    "OHLC_FIELDS",
    "QUOTE_SEMANTICS",
    "QUOTE_SIDES",
    "REFERENCE_DOWNLOADER",
    "RawArtifact",
    "VOLUME_SEMANTICS",
    "aggregate_paired_minutes_to_30m",
    "audit_acquisition_manifest",
    "audit_canonical_30m_frame",
    "canonicalize_bid_ask_minutes",
    "decode_daily_candles",
    "dukascopy_daily_url",
    "iter_utc_days",
    "pair_bid_ask_minutes",
    "source_bundle_sha256",
]
