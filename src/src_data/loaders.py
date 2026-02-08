from __future__ import annotations

from typing import Literal, Optional

import pandas as pd

from src.data.providers.yahoo import YahooFinanceProvider
from src.data.providers.alphavantage import AlphaVantageFXProvider


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
