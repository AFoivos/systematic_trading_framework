from __future__ import annotations

from typing import Literal, Optional, Sequence

import pandas as pd

from src.src_data.providers.yahoo import YahooFinanceProvider
from src.src_data.providers.alphavantage import AlphaVantageFXProvider
from src.src_data.providers.twelvedata import TwelveDataProvider


def load_ohlcv(
    symbol: str,
    start: str | None = None,
    end: str | None = None,
    interval: str = "1d",
    source: Literal["yahoo", "alpha", "twelve_data", "twelve"] = "yahoo",
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
    source : Literal["yahoo", "alpha", "twelve_data", "twelve"]
        "yahoo" (default), "alpha" για Alpha Vantage FX, ή "twelve_data"/"twelve"
        για Twelve Data time series.
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
    source: Literal["yahoo", "alpha", "twelve_data", "twelve"] = "yahoo",
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
    if len(set(normalized_symbols)) != len(normalized_symbols):
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
