from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.src_data.providers.base import MarketDataProvider

_INTERVAL_RE = re.compile(r"^\s*(\d+)\s*([A-Za-z]+)\s*$")
_MINUTE_UNITS = {"m", "min", "mins", "minute", "minutes"}
_HOUR_UNITS = {"h", "hr", "hrs", "hour", "hours"}
_DAY_UNITS = {"d", "day", "days"}
_WEEK_UNITS = {"wk", "w", "week", "weeks"}
_MONTH_UNITS = {"mo", "mon", "month", "months"}


def _build_retry_session() -> requests.Session:
    """
    Build a requests session with conservative retries for transient API failures.
    """
    session = requests.Session()
    retry = Retry(
        total=4,
        read=4,
        connect=4,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _normalize_interval(interval: str) -> str:
    """
    Map project interval aliases such as `1d` into Twelve Data interval names such as `1day`.
    """
    value = str(interval).strip().lower()
    match = _INTERVAL_RE.match(value)
    if not match:
        raise ValueError(f"Unsupported Twelve Data interval format: {interval!r}")

    count = int(match.group(1))
    unit = match.group(2).lower()
    if count <= 0:
        raise ValueError("Interval multiplier must be positive.")

    if unit in _MINUTE_UNITS:
        return f"{count}min"
    if unit in _HOUR_UNITS:
        return f"{count}h"
    if unit in _DAY_UNITS:
        return f"{count}day"
    if unit in _WEEK_UNITS:
        return f"{count}week"
    if unit in _MONTH_UNITS:
        return f"{count}month"
    raise ValueError(f"Unsupported Twelve Data interval unit: {unit!r}")


def _normalize_symbol(symbol: str) -> str:
    """
    Normalize common FX pair aliases to the `EUR/USD` form expected by Twelve Data.
    """
    raw = str(symbol).strip().upper()
    if raw.endswith("=X"):
        raw = raw[:-2]

    if "/" in raw:
        base, quote, *rest = raw.split("/")
        if not rest and len(base) == 3 and len(quote) == 3 and base.isalpha() and quote.isalpha():
            return f"{base}/{quote}"
        return raw

    if len(raw) == 6 and raw.isalpha():
        return f"{raw[:3]}/{raw[3:]}"

    return raw


def _normalize_boundary(value: str | None) -> pd.Timestamp | None:
    if value is None:
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts


@dataclass
class TwelveDataProvider(MarketDataProvider):
    """
    Wrapper around the Twelve Data time_series endpoint with the project's canonical OHLCV schema.

    Requires an API key (pass explicitly or set TWELVEDATA_API_KEY env var).
    """

    api_key: Optional[str] = None
    outputsize: int = 5000

    def get_ohlcv(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from Twelve Data and normalize it to the canonical project schema.
        """
        key = self.api_key or os.getenv("TWELVEDATA_API_KEY")
        if not key:
            raise ValueError("Twelve Data API key not provided (env TWELVEDATA_API_KEY)")

        params = {
            "symbol": _normalize_symbol(symbol),
            "interval": _normalize_interval(interval),
            "apikey": key,
            "timezone": "UTC",
            "outputsize": int(self.outputsize),
        }

        start_ts = _normalize_boundary(start)
        end_ts = _normalize_boundary(end)
        if start_ts is not None:
            params["start_date"] = str(start_ts)
        if end_ts is not None:
            params["end_date"] = str(end_ts)

        session = _build_retry_session()
        try:
            resp = session.get("https://api.twelvedata.com/time_series", params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        finally:
            session.close()

        if data.get("status") == "error":
            raise ValueError(
                "Twelve Data error: "
                f"{data.get('message') or data.get('code') or data}"
            )

        values = data.get("values")
        if not isinstance(values, list) or not values:
            raise ValueError(f"No data returned from Twelve Data for symbol={symbol}")

        df = pd.DataFrame(values).copy()
        if "datetime" not in df.columns:
            raise ValueError("Twelve Data response missing 'datetime' column.")
        missing = [col for col in ("open", "high", "low", "close") if col not in df.columns]
        if missing:
            raise ValueError(
                f"Missing expected columns from Twelve Data response: {missing}. "
                f"Available columns: {list(df.columns)}"
            )

        idx = pd.DatetimeIndex(pd.to_datetime(df["datetime"], errors="raise", utc=True))
        idx = idx.tz_convert("UTC").tz_localize(None)
        df.index = idx

        out = pd.DataFrame(index=idx)
        for col in ("open", "high", "low", "close"):
            out[col] = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)

        if "volume" in df.columns:
            out["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        else:
            out["volume"] = 0.0

        out = out.sort_index()
        out = out[~out.index.duplicated(keep="last")]
        out = out.dropna(subset=["open", "high", "low", "close"])

        if start_ts is not None:
            out = out[out.index >= start_ts]
        if end_ts is not None:
            out = out[out.index < end_ts]

        if out.empty:
            raise ValueError(f"No data returned from Twelve Data for symbol={symbol}")

        return out[["open", "high", "low", "close", "volume"]]


__all__ = [
    "TwelveDataProvider",
    "_build_retry_session",
]
