from __future__ import annotations

from typing import Literal, Optional, Sequence

import pandas as pd

from src.src_data.providers.yahoo import YahooFinanceProvider
from src.src_data.providers.alphavantage import AlphaVantageFXProvider
from src.src_data.providers.twelvedata import TwelveDataProvider


def _canonical_symbol_for_source(symbol: str, source: str) -> str:
    raw = str(symbol).strip().upper()
    if source in {"twelve_data", "twelve"}:
        if raw.endswith("=X"):
            raw = raw[:-2]
        if "/" in raw:
            parts = raw.split("/")
            if len(parts) == 2 and all(len(part) == 3 and part.isalpha() for part in parts):
                return f"{parts[0]}/{parts[1]}"
            return raw
        if len(raw) == 6 and raw.isalpha():
            return f"{raw[:3]}/{raw[3:]}"
        return raw
    if source == "alpha":
        return raw.replace("=X", "")
    return raw


def load_ohlcv(
    symbol: str,
    start: str | None = None,
    end: str | None = None,
    interval: str = "1d",
    source: Literal["yahoo", "alpha", "twelve_data", "twelve", "dukascopy_csv"] = "yahoo",
    api_key: Optional[str] = None,
) -> pd.DataFrame:
    """
    Parameters
    ----------
    symbol : str
        Ticker (π.χ. "SPY", "AAPL", "BTC-USD").
    start : str | None
        Start date (π.χ. "2010-01-01").
    end : str | None
        End date (π.χ. "2025-01-01").
    interval : str
        "1d", "1h", "5m", κλπ (όπως τα υποστηρίζει το yfinance).
    source : Literal["yahoo", "alpha", "twelve_data", "twelve", "dukascopy_csv"]
        "yahoo" (default), "alpha" για Alpha Vantage FX, ή "twelve_data"/"twelve"
        για Twelve Data time series. Το "dukascopy_csv" είναι explicit external CSV source
        και υποστηρίζεται μόνο μέσω data.storage.load_path, όχι από provider adapter.
    api_key : str | None
        Απαιτείται για source="alpha" (ή env ALPHAVANTAGE_API_KEY) και προαιρετικά για
        source="twelve_data"/"twelve" (ή env TWELVEDATA_API_KEY).

    Returns
    -------
    pd.DataFrame
        OHLCV με:
        - index: DatetimeIndex
        - columns: ["open", "high", "low", "close", "volume"]
    """
    if source == "yahoo":
        provider = YahooFinanceProvider()
    elif source == "alpha":
        provider = AlphaVantageFXProvider(api_key=api_key)
    elif source in {"twelve_data", "twelve"}:
        provider = TwelveDataProvider(api_key=api_key)
    elif source == "dukascopy_csv":
        raise ValueError(
            "data.source='dukascopy_csv' requires data.storage.load_path; provider loading is not supported."
        )
    else:
        raise ValueError(f"Unknown data source: {source}")

    df = provider.get_ohlcv(
        symbol=symbol,
        start=start,
        end=end,
        interval=interval,
    )
    return df


def load_ohlcv_panel(
    symbols: Sequence[str],
    start: str | None = None,
    end: str | None = None,
    interval: str = "1d",
    source: Literal["yahoo", "alpha", "twelve_data", "twelve", "dukascopy_csv"] = "yahoo",
    api_key: Optional[str] = None,
) -> dict[str, pd.DataFrame]:
    """
    Load OHLCV panel for the data ingestion and storage layer and normalize it into the shape
    expected by the rest of the project. The helper centralizes path or provider handling so
    callers do not duplicate I/O logic.
    """
    if not symbols:
        raise ValueError("symbols cannot be empty.")
    normalized_symbols = [str(symbol) for symbol in symbols]
    canonical_symbols = [_canonical_symbol_for_source(symbol, source) for symbol in normalized_symbols]
    if len(set(canonical_symbols)) != len(canonical_symbols):
        raise ValueError("symbols contains duplicates.")

    panel: dict[str, pd.DataFrame] = {}
    for symbol in normalized_symbols:
        panel[symbol] = load_ohlcv(
            symbol=symbol,
            start=start,
            end=end,
            interval=interval,
            source=source,
            api_key=api_key,
        )
    return panel
