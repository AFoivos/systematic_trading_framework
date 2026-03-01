from __future__ import annotations

from typing import Literal, Optional, Sequence

import pandas as pd

from src.src_data.providers.yahoo import YahooFinanceProvider
from src.src_data.providers.alphavantage import AlphaVantageFXProvider


def load_ohlcv(
    symbol: str,
    start: str | None = None,
    end: str | None = None,
    interval: str = "1d",
    source: Literal["yahoo", "alpha"] = "yahoo",
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
    source : Literal["yahoo", "alpha"]
        "yahoo" (default) ή "alpha" για Alpha Vantage FX.
    api_key : str | None
        Απαιτείται για source="alpha" (ή env ALPHAVANTAGE_API_KEY).

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
    source: Literal["yahoo", "alpha"] = "yahoo",
    api_key: Optional[str] = None,
) -> dict[str, pd.DataFrame]:
    """
    Load OHLCV panel for the data ingestion and storage layer and normalize it into the shape
    expected by the rest of the project. The helper centralizes path or provider handling so
    callers do not duplicate I/O logic.
    """
    if not symbols:
        raise ValueError("symbols cannot be empty.")

    panel: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        panel[str(symbol)] = load_ohlcv(
            symbol=str(symbol),
            start=start,
            end=end,
            interval=interval,
            source=source,
            api_key=api_key,
        )
    return panel
