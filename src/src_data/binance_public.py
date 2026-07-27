from __future__ import annotations

"""Point-in-time downloader for Binance public spot and USD-M futures data.

The adapter uses only unauthenticated REST endpoints.  Klines are indexed by
their *close* timestamp because the OHLC values are not known at the open
timestamp.  This availability-time convention is important for causal joins
with funding settlements.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import time
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import pandas as pd
import requests

from src.utils.paths import enforce_safe_absolute_path
from src.utils.run_metadata import file_sha256


JsonTransport = Callable[[str, Mapping[str, Any]], Any]

SUPPORTED_DATASETS = (
    "spot_klines",
    "perp_klines",
    "mark_price_klines",
    "index_price_klines",
    "premium_index_klines",
    "funding_rates",
)
SUPPORTED_INTERVALS = frozenset(
    {
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
        "1h",
        "2h",
        "4h",
        "6h",
        "8h",
        "12h",
        "1d",
    }
)


@dataclass(frozen=True)
class _Endpoint:
    market: str
    path: str
    symbol_param: str
    timestamp_field: str
    is_kline: bool


_ENDPOINTS: dict[str, _Endpoint] = {
    "spot_klines": _Endpoint("spot", "/api/v3/klines", "symbol", "open_time", True),
    "perp_klines": _Endpoint("futures", "/fapi/v1/klines", "symbol", "open_time", True),
    "mark_price_klines": _Endpoint(
        "futures", "/fapi/v1/markPriceKlines", "symbol", "open_time", True
    ),
    "index_price_klines": _Endpoint(
        "futures", "/fapi/v1/indexPriceKlines", "pair", "open_time", True
    ),
    "premium_index_klines": _Endpoint(
        "futures", "/fapi/v1/premiumIndexKlines", "symbol", "open_time", True
    ),
    "funding_rates": _Endpoint(
        "futures", "/fapi/v1/fundingRate", "symbol", "fundingTime", False
    ),
}


def _utc_timestamp(value: str | pd.Timestamp, *, field: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError(f"{field} must be a valid timestamp.")
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp


def _epoch_ms(value: pd.Timestamp) -> int:
    return int(value.timestamp() * 1_000)


def _iso_utc(value: pd.Timestamp) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _request_hash(value: Mapping[str, Any]) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_symbol(symbol: str) -> str:
    normalized = str(symbol).strip().upper()
    if not normalized or not normalized.isalnum():
        raise ValueError(f"Invalid Binance symbol: {symbol!r}.")
    return normalized


class BinancePublicClient:
    """Download paginated public Binance data without API credentials."""

    def __init__(
        self,
        *,
        spot_base_url: str = "https://api.binance.com",
        futures_base_url: str = "https://fapi.binance.com",
        timeout_seconds: float = 30.0,
        pause_seconds: float = 0.05,
        transport: JsonTransport | None = None,
    ) -> None:
        if timeout_seconds <= 0.0:
            raise ValueError("timeout_seconds must be > 0.")
        if pause_seconds < 0.0:
            raise ValueError("pause_seconds must be >= 0.")
        self.spot_base_url = spot_base_url.rstrip("/")
        self.futures_base_url = futures_base_url.rstrip("/")
        self.timeout_seconds = float(timeout_seconds)
        self.pause_seconds = float(pause_seconds)
        self._session = requests.Session()
        self._transport = transport or self._request_json

    def _request_json(self, url: str, params: Mapping[str, Any]) -> Any:
        response = self._session.get(url, params=dict(params), timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and "code" in payload:
            raise RuntimeError(f"Binance API error from {url}: {payload}")
        return payload

    def endpoint_url(self, dataset: str) -> str:
        if dataset not in _ENDPOINTS:
            raise ValueError(
                f"Unsupported dataset {dataset!r}; expected one of {SUPPORTED_DATASETS}."
            )
        endpoint = _ENDPOINTS[dataset]
        base = self.spot_base_url if endpoint.market == "spot" else self.futures_base_url
        return f"{base}{endpoint.path}"

    def fetch(
        self,
        *,
        dataset: str,
        symbol: str,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        interval: str = "30m",
        limit: int = 1_000,
    ) -> pd.DataFrame:
        """Fetch one dataset in the half-open interval ``[start, end)``."""
        if dataset not in _ENDPOINTS:
            raise ValueError(
                f"Unsupported dataset {dataset!r}; expected one of {SUPPORTED_DATASETS}."
            )
        if interval not in SUPPORTED_INTERVALS:
            raise ValueError(f"Unsupported Binance interval: {interval!r}.")
        if not 1 <= int(limit) <= 1_000:
            raise ValueError("limit must be between 1 and 1000.")

        normalized_symbol = _normalize_symbol(symbol)
        start_ts = _utc_timestamp(start, field="start")
        end_ts = _utc_timestamp(end, field="end")
        if start_ts >= end_ts:
            raise ValueError("start must be earlier than end.")

        endpoint = _ENDPOINTS[dataset]
        cursor = _epoch_ms(start_ts)
        end_ms = _epoch_ms(end_ts)
        rows: list[Any] = []
        while cursor < end_ms:
            params: dict[str, Any] = {
                endpoint.symbol_param: normalized_symbol,
                "startTime": cursor,
                "endTime": end_ms - 1,
                "limit": int(limit),
            }
            if endpoint.is_kline:
                params["interval"] = interval
            page = self._transport(self.endpoint_url(dataset), params)
            if not isinstance(page, list):
                raise RuntimeError(
                    f"Binance {dataset} response must be a list, got {type(page).__name__}."
                )
            if not page:
                break

            rows.extend(page)
            last_ms = self._page_timestamp_ms(page[-1], endpoint=endpoint)
            if last_ms < cursor:
                raise RuntimeError(
                    f"Binance {dataset} pagination did not advance: {last_ms} < {cursor}."
                )
            next_cursor = last_ms + 1
            if next_cursor <= cursor:
                raise RuntimeError(f"Binance {dataset} pagination cursor stalled at {cursor}.")
            cursor = next_cursor
            if len(page) < int(limit):
                break
            if self.pause_seconds:
                time.sleep(self.pause_seconds)

        if endpoint.is_kline:
            return _normalize_klines(rows, start=start_ts, end=end_ts)
        return _normalize_funding(rows, start=start_ts, end=end_ts)

    @staticmethod
    def _page_timestamp_ms(row: Any, *, endpoint: _Endpoint) -> int:
        try:
            value = row[0] if endpoint.is_kline else row[endpoint.timestamp_field]
            return int(value)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError(
                f"Malformed Binance row for timestamp field {endpoint.timestamp_field!r}: {row!r}"
            ) from exc


def _normalize_klines(
    rows: Sequence[Any],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    columns = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_volume",
        "trade_count",
        "taker_base_volume",
        "taker_quote_volume",
        "unused",
    ]
    if not rows:
        return pd.DataFrame(columns=columns[:-1]).set_index(
            pd.DatetimeIndex([], name="timestamp", tz="UTC")
        )
    if any(not isinstance(row, Sequence) or len(row) < 7 for row in rows):
        raise RuntimeError("Malformed Binance kline response: every row must have >= 7 fields.")

    padded = [list(row[:12]) + [None] * max(0, 12 - len(row)) for row in rows]
    frame = pd.DataFrame([row[:12] for row in padded], columns=columns)
    frame["open_time"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True, errors="raise")
    frame["close_time"] = pd.to_datetime(frame["close_time"], unit="ms", utc=True, errors="raise")
    for column in (
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "taker_base_volume",
        "taker_quote_volume",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["trade_count"] = pd.to_numeric(frame["trade_count"], errors="coerce").astype("Int64")
    frame = frame.drop(columns="unused").set_index("close_time")
    frame.index.name = "timestamp"
    frame = frame.loc[(frame.index >= start) & (frame.index < end)].sort_index()
    _validate_kline_frame(frame)
    return frame


def _validate_kline_frame(frame: pd.DataFrame) -> None:
    if frame.index.has_duplicates:
        raise ValueError("Binance kline response contains duplicate close timestamps.")
    if not frame.index.is_monotonic_increasing:
        raise ValueError("Binance kline close timestamps must be monotonic increasing.")
    if frame.empty:
        return
    prices = frame[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if not np.isfinite(prices).all() or (prices <= 0.0).any():
        raise ValueError("Binance kline OHLC values must be finite and positive.")
    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("Binance kline high is inconsistent with OHLC values.")
    if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("Binance kline low is inconsistent with OHLC values.")


def _normalize_funding(
    rows: Sequence[Any],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    if not rows:
        empty = pd.DataFrame(columns=["symbol", "funding_rate", "mark_price"])
        empty.index = pd.DatetimeIndex([], name="timestamp", tz="UTC")
        return empty
    if any(not isinstance(row, Mapping) for row in rows):
        raise RuntimeError("Malformed Binance funding response: every row must be a mapping.")

    frame = pd.DataFrame(rows)
    required = {"symbol", "fundingTime", "fundingRate"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise RuntimeError(f"Binance funding response is missing fields: {missing}.")
    frame["timestamp"] = pd.to_datetime(frame["fundingTime"], unit="ms", utc=True, errors="raise")
    frame["funding_rate"] = pd.to_numeric(frame["fundingRate"], errors="raise")
    frame["mark_price"] = pd.to_numeric(frame.get("markPrice"), errors="coerce")
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    frame = frame[["timestamp", "symbol", "funding_rate", "mark_price"]].set_index("timestamp")
    frame = frame.loc[(frame.index >= start) & (frame.index < end)].sort_index()
    if frame.index.has_duplicates:
        raise ValueError("Binance funding response contains duplicate settlement timestamps.")
    if not np.isfinite(frame["funding_rate"].to_numpy(dtype=float)).all():
        raise ValueError("Binance funding rates must be finite.")
    return frame


def _resolve_snapshot_dir(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path(__file__).resolve().parents[2] / candidate
    return enforce_safe_absolute_path(candidate.resolve())


def _atomic_write_csv(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    frame.to_csv(temporary, index=True, index_label="timestamp", date_format="%Y-%m-%dT%H:%M:%S.%fZ")
    temporary.replace(path)


def _atomic_write_json(payload: Mapping[str, Any], path: Path) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    temporary.replace(path)


def _valid_cached_manifest(snapshot_dir: Path, request: Mapping[str, Any]) -> dict[str, Any] | None:
    manifest_path = snapshot_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("request_sha256") != _request_hash(request):
        return None
    for metadata in manifest.get("files", {}).values():
        relative_path = Path(str(metadata.get("path", "")))
        candidate = (snapshot_dir / relative_path).resolve()
        try:
            candidate.relative_to(snapshot_dir.resolve())
        except ValueError as exc:
            raise ValueError(f"Unsafe path in Binance snapshot manifest: {relative_path}") from exc
        if not candidate.is_file() or file_sha256(candidate) != metadata.get("sha256"):
            return None
    return manifest


def download_binance_snapshot(
    *,
    output_dir: str | Path,
    symbols: Sequence[str],
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    interval: str = "30m",
    datasets: Sequence[str] = SUPPORTED_DATASETS,
    refresh: bool = False,
    client: BinancePublicClient | None = None,
) -> dict[str, Any]:
    """Download and fingerprint an immutable, normalized Binance snapshot."""
    normalized_symbols = sorted({_normalize_symbol(symbol) for symbol in symbols})
    if not normalized_symbols:
        raise ValueError("symbols must contain at least one Binance symbol.")
    normalized_datasets = list(dict.fromkeys(str(value) for value in datasets))
    unsupported = sorted(set(normalized_datasets) - set(SUPPORTED_DATASETS))
    if unsupported:
        raise ValueError(f"Unsupported Binance datasets: {unsupported}.")
    if not normalized_datasets:
        raise ValueError("datasets must contain at least one dataset.")
    if interval not in SUPPORTED_INTERVALS:
        raise ValueError(f"Unsupported Binance interval: {interval!r}.")

    start_ts = _utc_timestamp(start, field="start")
    end_ts = _utc_timestamp(end, field="end")
    if start_ts >= end_ts:
        raise ValueError("start must be earlier than end.")
    snapshot_dir = _resolve_snapshot_dir(output_dir)
    request = {
        "schema_version": 1,
        "provider": "binance_public_rest",
        "symbols": normalized_symbols,
        "datasets": normalized_datasets,
        "interval": interval,
        "start_inclusive_utc": _iso_utc(start_ts),
        "end_exclusive_utc": _iso_utc(end_ts),
        "timestamp_semantics": "kline_close_time_and_funding_settlement_time",
    }
    if not refresh:
        cached = _valid_cached_manifest(snapshot_dir, request)
        if cached is not None:
            return cached
        if (snapshot_dir / "manifest.json").exists():
            raise FileExistsError(
                "Existing Binance snapshot does not match the requested contract or failed "
                f"hash verification: {snapshot_dir}. Use refresh=True or a new output directory."
            )

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    downloader = client or BinancePublicClient()
    files: dict[str, Any] = {}
    for symbol in normalized_symbols:
        symbol_dir = snapshot_dir / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)
        for dataset in normalized_datasets:
            frame = downloader.fetch(
                dataset=dataset,
                symbol=symbol,
                start=start_ts,
                end=end_ts,
                interval=interval,
            )
            if frame.empty:
                raise ValueError(
                    f"Binance returned no rows for {symbol} {dataset} in "
                    f"[{_iso_utc(start_ts)}, {_iso_utc(end_ts)})."
                )
            relative_path = Path(symbol) / f"{dataset}.csv"
            data_path = snapshot_dir / relative_path
            _atomic_write_csv(frame, data_path)
            files[f"{symbol}/{dataset}"] = {
                "path": relative_path.as_posix(),
                "sha256": file_sha256(data_path),
                "bytes": int(data_path.stat().st_size),
                "rows": int(len(frame)),
                "timestamp_start": _iso_utc(pd.Timestamp(frame.index.min())),
                "timestamp_end": _iso_utc(pd.Timestamp(frame.index.max())),
                "endpoint": downloader.endpoint_url(dataset),
            }

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "request": request,
        "request_sha256": _request_hash(request),
        "files": files,
    }
    _atomic_write_json(manifest, snapshot_dir / "manifest.json")
    return manifest


def load_binance_snapshot_frame(
    snapshot_dir: str | Path,
    *,
    symbol: str,
    dataset: str,
    verify_hash: bool = True,
) -> pd.DataFrame:
    """Load one normalized frame and optionally verify its manifest hash."""
    root = _resolve_snapshot_dir(snapshot_dir)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Binance snapshot manifest does not exist: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    key = f"{_normalize_symbol(symbol)}/{dataset}"
    metadata = manifest.get("files", {}).get(key)
    if not isinstance(metadata, Mapping):
        raise ValueError(f"Binance snapshot does not contain {key!r}.")
    path = (root / str(metadata.get("path", ""))).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Unsafe file path for Binance snapshot entry {key!r}.") from exc
    if not path.is_file():
        raise FileNotFoundError(f"Binance snapshot file does not exist: {path}")
    if verify_hash and file_sha256(path) != metadata.get("sha256"):
        raise ValueError(f"SHA-256 mismatch for Binance snapshot file: {path}")

    frame = pd.read_csv(path)
    if "timestamp" not in frame.columns:
        raise ValueError(f"Binance snapshot file is missing timestamp: {path}")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
    frame = frame.set_index("timestamp").sort_index()
    if frame.empty or frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError(f"Invalid timestamp contract in Binance snapshot file: {path}")
    return frame


__all__ = [
    "BinancePublicClient",
    "SUPPORTED_DATASETS",
    "SUPPORTED_INTERVALS",
    "download_binance_snapshot",
    "load_binance_snapshot_frame",
]
